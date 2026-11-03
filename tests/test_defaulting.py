"""Tests for the model namespace defaulting to the factory namespace."""

from __future__ import annotations

from dataclasses import dataclass

import factory
import pytest

from pytest_factoryboy import register, register_factory


@dataclass
class Item:
    name: str


class ItemFactory(factory.Factory):
    class Meta:
        model = Item

    name = "default"


register_factory(ItemFactory)
register(ItemFactory)  # item
register(ItemFactory, "second_item")  # second_item


class OverrideItemFactory(factory.Factory):
    class Meta:
        model = Item

    name = "default"


register_factory(OverrideItemFactory, name="A")
register(OverrideItemFactory, "override_item", name="B")


@dataclass
class Pure:
    name: str


class PureFactory(factory.Factory):
    class Meta:
        model = Pure

    name = "default"


register_factory(PureFactory, name="from factory")
register(PureFactory, "pure_item")


@dataclass
class Legacy:
    name: str


class LegacyFactory(factory.Factory):
    class Meta:
        model = Legacy

    name = "legacy"


@pytest.fixture
def legacy_factory():
    return LegacyFactory


register(LegacyFactory)


@pytest.mark.parametrize("item_factory__name", ["from factory"])
def test_model_inherits_factory_namespace(item):
    # Only ``item`` is requested; the factory namespace is in its closure.
    assert item.name == "from factory"


@pytest.mark.parametrize("item_factory__name", ["from factory"])
def test_factory_namespace_applies_to_factory(item_factory):
    assert item_factory().name == "from factory"


@pytest.mark.parametrize("item_factory__name", ["from factory"])
def test_model_namespace_fixture_defaults_to_factory(item__name):
    # The model attribute fixture itself defaults to the factory namespace.
    assert item__name == "from factory"


@pytest.mark.parametrize("item__name", ["from model"])
@pytest.mark.parametrize("item_factory__name", ["from factory"])
def test_model_own_namespace_wins(item, second_item, item_factory):
    assert item.name == "from model"
    assert second_item.name == "from factory"
    assert item_factory().name == "from factory"


def test_register_factory_override_is_the_model_default(override_item, override_item_factory):
    # register_factory sets the default the model inherits; register overrides the model.
    assert override_item.name == "B"
    assert override_item_factory().name == "A"


def test_factory_namespace_flows_to_model_without_model_override(pure_item):
    assert pure_item.name == "from factory"


def test_preexisting_factory_fixture_does_not_break_the_model(legacy, legacy_factory):
    # A user-provided ``legacy_factory`` fixture must not break the model: register still
    # adds the missing factory namespace.
    assert legacy_factory is LegacyFactory
    assert legacy.name == "legacy"


@pytest.mark.parametrize("second_item__name", ["isolated"])
def test_registrations_do_not_leak(item, second_item):
    assert second_item.name == "isolated"
    assert item.name == "default"
