"""Tests for the resolution of shareable sub-factories (``specs/factory-fixtures.md`` §4.1)."""

from __future__ import annotations

from dataclasses import dataclass

import factory
import pytest

from pytest_factoryboy import register, register_factory
from pytest_factoryboy.engine import (
    UNSET,
    Unset,
    defaults_for,
    record_default_fixtures,
    recorded_fixture,
)
from pytest_factoryboy.fixture import Box


@dataclass
class Target:
    name: str


@dataclass
class Holder:
    target: Target


class TargetFactory(factory.Factory):
    class Meta:
        model = Target

    name = "target"


class HolderFactory(factory.Factory):
    class Meta:
        model = Holder

    target = factory.SubFactory(TargetFactory)


def test_record_default_fixtures_first_writer_wins() -> None:
    class LocalFactory(factory.Factory):
        class Meta:
            model = Target

    record_default_fixtures(LocalFactory, model_name="first", subfactory="first", relatedfactory="first")
    record_default_fixtures(LocalFactory, model_name="second", subfactory="second", relatedfactory=None)

    defaults = defaults_for(LocalFactory)

    assert defaults is not None
    assert defaults.model_name == "first"
    assert defaults.subfactory == "first"
    assert defaults.relatedfactory == "first"


def test_record_default_fixtures_keeps_unset_kinds() -> None:
    class LocalFactory(factory.Factory):
        class Meta:
            model = Target

    record_default_fixtures(LocalFactory, subfactory=None)

    defaults = defaults_for(LocalFactory)

    assert defaults is not None
    assert defaults.subfactory is None
    assert defaults.relatedfactory is UNSET
    assert defaults.model_name is None


def test_defaults_are_recorded_per_class() -> None:
    """A subclass does not inherit what its base recorded: it shares nothing."""

    class LocalBaseFactory(factory.Factory):
        class Meta:
            model = Target

    record_default_fixtures(LocalBaseFactory, model_name="local", subfactory="local")

    class LocalChildFactory(LocalBaseFactory):
        pass

    assert defaults_for(LocalChildFactory) is None
    assert isinstance(recorded_fixture(factory.SubFactory(LocalChildFactory), related=False), Unset)


# --- opt-out: a recorded ``None`` builds a new object --------------------------------


class OptedOutTargetFactory(TargetFactory):
    pass


class OptedOutHolderFactory(HolderFactory):
    target = factory.SubFactory(OptedOutTargetFactory)


# ``register_factory`` runs first, so its setting wins over the one ``register`` records.
register_factory(OptedOutTargetFactory, _default_subfactory_fixture=None)
register(OptedOutTargetFactory, "opted_out_target")
register(OptedOutHolderFactory, "opted_out_holder")


def test_opt_out_builds_a_new_object(opted_out_holder, opted_out_holder_factory, opted_out_target) -> None:
    assert opted_out_holder.target is not opted_out_target
    assert opted_out_holder_factory().target is not opted_out_target


def test_opt_out_builds_a_new_object_per_call(opted_out_holder_factory) -> None:
    assert opted_out_holder_factory().target is not opted_out_holder_factory().target


# --- an explicit fixture name --------------------------------------------------------


class NamedTargetFactory(TargetFactory):
    pass


class NamedHolderFactory(HolderFactory):
    target = factory.SubFactory(NamedTargetFactory)


@pytest.fixture
def shared_target() -> Target:
    """A hand-written fixture, used as the explicit default."""
    return Target(name="hand-written")


register_factory(NamedTargetFactory, _default_subfactory_fixture="shared_target")
register(NamedHolderFactory, "named_holder")


def test_explicit_fixture_is_shared(named_holder, named_holder_factory, shared_target) -> None:
    assert named_holder.target is shared_target
    assert named_holder_factory().target is shared_target


# --- first writer wins ---------------------------------------------------------------


class TwinTargetFactory(TargetFactory):
    pass


class TwinHolderFactory(HolderFactory):
    target = factory.SubFactory(TwinTargetFactory)


register(TwinTargetFactory, "primary_twin")
register(TwinTargetFactory, "secondary_twin")
register(TwinHolderFactory, "twin_holder")


def test_first_registration_wins(twin_holder, twin_holder_factory, primary_twin, secondary_twin) -> None:
    assert twin_holder.target is primary_twin
    assert twin_holder_factory().target is primary_twin
    assert twin_holder.target is not secondary_twin


# --- unregistered targets fall back to the model-name inflection ---------------------


@dataclass
class Gadget:
    name: str


class GadgetFactory(factory.Factory):
    class Meta:
        model = Gadget

    name = "gadget"


class FallbackHolderFactory(HolderFactory):
    target = factory.SubFactory(TargetFactory)


class GadgetFallbackHolderFactory(HolderFactory):
    target = factory.SubFactory(GadgetFactory)


@pytest.fixture
def target() -> Target:
    """A hand-written fixture matching the inflected model name."""
    return Target(name="hand-written")


register(FallbackHolderFactory, "fallback_holder")
register(GadgetFallbackHolderFactory, "gadget_fallback_holder")


def test_unregistered_target_shares_an_inflected_fixture(fallback_holder_factory, target) -> None:
    with pytest.warns(DeprecationWarning, match="TargetFactory has no default subfactory fixture"):
        holder = fallback_holder_factory()

    assert holder.target is target


def test_unregistered_target_builds_a_new_object(gadget_fallback_holder_factory) -> None:
    with pytest.warns(DeprecationWarning, match="GadgetFactory has no default subfactory fixture"):
        holder = gadget_fallback_holder_factory()

    assert isinstance(holder.target, Gadget)
    assert holder.target.name == "gadget"


def test_explicit_setting_is_recorded_even_when_registration_raises() -> None:
    """The setting is honoured regardless of the order of registrations."""

    class LocalTargetFactory(TargetFactory):
        pass

    locals_ = Box({})
    register_factory(LocalTargetFactory, _caller_locals=locals_)

    with pytest.raises(ValueError, match="already registered"):
        register_factory(LocalTargetFactory, _default_subfactory_fixture=None, _caller_locals=locals_)

    defaults = defaults_for(LocalTargetFactory)

    assert defaults is not None
    assert defaults.subfactory is None


def test_registration_warns_for_an_unregistered_target() -> None:
    class LocalTargetFactory(TargetFactory):
        pass

    class LocalHolderFactory(HolderFactory):
        target = factory.SubFactory(LocalTargetFactory)

    with pytest.warns(DeprecationWarning, match="LocalTargetFactory has no default subfactory fixture"):
        register(LocalHolderFactory, _caller_locals=Box({}))


def test_registration_warns_for_a_target_registered_without_a_default() -> None:
    class LocalTargetFactory(TargetFactory):
        pass

    class LocalHolderFactory(HolderFactory):
        target = factory.SubFactory(LocalTargetFactory)

    register_factory(LocalTargetFactory, _caller_locals=Box({}))

    with pytest.warns(DeprecationWarning, match="LocalTargetFactory has no default subfactory fixture"):
        register(LocalHolderFactory, _caller_locals=Box({}))
