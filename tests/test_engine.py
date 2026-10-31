"""Tests for the generation engine (:mod:`pytest_factoryboy.engine`)."""

from __future__ import annotations

import gc
import weakref
from dataclasses import dataclass

import factory
import pytest

from pytest_factoryboy import LazyFixture, engine, register, register_factory
from pytest_factoryboy.engine import original_factory
from pytest_factoryboy.fixture import Box


@dataclass
class Widget:
    name: str


class WidgetFactory(factory.Factory):
    class Meta:
        model = Widget

    name = "w"


@dataclass
class Gadget:
    label: str


class GadgetFactory(factory.Factory):
    class Meta:
        model = Gadget

    label = "g"


@dataclass
class Wrapper:
    widget: Widget


class WrapperFactory(factory.Factory):
    class Meta:
        model = Wrapper

    widget = factory.SubFactory(WidgetFactory)


_tracked_creations: list[str] = []


@dataclass
class Tracked:
    name: str

    def __post_init__(self) -> None:
        _tracked_creations.append(self.name)


class TrackedFactory(factory.Factory):
    class Meta:
        model = Tracked

    name = "tracked"


@dataclass
class Container:
    tracked: Tracked


class ContainerFactory(factory.Factory):
    class Meta:
        model = Container

    tracked = factory.SubFactory(TrackedFactory)


register_factory(WidgetFactory)
register_factory(GadgetFactory, label="overridden")
register_factory(WrapperFactory)
register(TrackedFactory)
register(TrackedFactory, "other_tracked")
register_factory(ContainerFactory, tracked=LazyFixture("other_tracked"))
register(ContainerFactory, "other_container")


@pytest.fixture
def tracked_creations():
    _tracked_creations.clear()
    return _tracked_creations


def test_bind_factory_returns_a_bound_subclass(request) -> None:
    bound = engine.bind_factory(WidgetFactory, request, "widget_factory")

    assert bound is not WidgetFactory
    assert issubclass(bound, WidgetFactory)
    assert original_factory(bound) is WidgetFactory
    # A factory that is not bound is returned unchanged.
    assert original_factory(WidgetFactory) is WidgetFactory
    # Identity metadata is copied so reprs/docs look like the user's factory.
    assert bound.__name__ == WidgetFactory.__name__
    assert bound.__qualname__ == WidgetFactory.__qualname__
    assert bound.__module__ == WidgetFactory.__module__
    assert bound.__doc__ == WidgetFactory.__doc__


def test_bind_factory_does_not_mutate_the_caller_factory(request) -> None:
    original_generate = WidgetFactory._generate.__func__

    engine.bind_factory(WidgetFactory, request, "widget_factory")

    assert WidgetFactory._generate.__func__ is original_generate


def test_bind_factory_does_not_store_state_globally(request) -> None:
    """The bound class owns the engine state; nothing global keeps it alive."""
    bound = engine.bind_factory(WidgetFactory, request, "widget_factory")
    ref = weakref.ref(bound)

    del bound
    gc.collect()

    assert ref() is None


@pytest.mark.parametrize("widget_factory__name", ["Ada"])
def test_factory_namespace_applies_to_every_entry_point(widget_factory) -> None:
    """``_generate`` is factory_boy's single funnel for top-level generation."""
    assert widget_factory().name == "Ada"
    assert widget_factory.create().name == "Ada"
    assert widget_factory.build().name == "Ada"
    assert widget_factory.stub().name == "Ada"
    assert [widget.name for widget in widget_factory.create_batch(2)] == ["Ada", "Ada"]
    assert [widget.name for widget in widget_factory.build_batch(2)] == ["Ada", "Ada"]
    assert [widget.name for widget in widget_factory.stub_batch(2)] == ["Ada", "Ada"]
    assert widget_factory.generate("create").name == "Ada"
    assert widget_factory.generate("build").name == "Ada"
    assert widget_factory.generate("stub").name == "Ada"


def test_user_generate_override_is_reached(request) -> None:
    seen: list[str] = []

    class CustomFactory(WidgetFactory):
        @classmethod
        def _generate(cls, strategy, params):
            seen.append(strategy)
            return super()._generate(strategy, params)

    bound = engine.bind_factory(CustomFactory, request, "widget_factory")

    assert bound().name == "w"
    assert seen == ["create"]


def test_abstract_factory_stays_abstract(request) -> None:
    class AbstractFactory(factory.Factory):
        class Meta:
            model = Widget
            abstract = True

    bound = engine.bind_factory(AbstractFactory, request, "widget_factory")

    with pytest.raises(factory.errors.FactoryError):
        bound()


def test_register_factory_applies_overrides(widget_factory) -> None:
    assert widget_factory().name == "w"


def test_register_factory_override(gadget_factory) -> None:
    assert gadget_factory().label == "overridden"


@pytest.mark.parametrize("widget_factory__name", ["Ada"])
def test_factory_namespace_parametrization(widget_factory) -> None:
    assert widget_factory().name == "Ada"


@pytest.mark.parametrize("widget_factory__name", ["Ada"])
def test_per_call_override_wins(widget_factory) -> None:
    assert widget_factory(name="Grace").name == "Grace"


def test_register_factory_raises_when_nothing_to_register() -> None:
    locals_ = Box({})
    register_factory(WidgetFactory, _caller_locals=locals_)
    assert "widget_factory" in locals_.value

    with pytest.raises(ValueError, match="already registered"):
        register_factory(WidgetFactory, _caller_locals=locals_)


def test_factory_namespace_bare_subfactory_is_built_fresh(wrapper_factory) -> None:
    # The untouched ``SubFactory`` declaration is skipped by the engine and built by
    # factory_boy.
    wrapper = wrapper_factory()
    assert isinstance(wrapper.widget, Widget)
    assert wrapper.widget.name == "w"


@pytest.mark.parametrize("widget_factory__name", ["Ada"])
def test_nested_subfactory_is_not_intercepted(widget_factory, wrapper_factory) -> None:
    # The ``SubFactory`` recurses through factory_boy's builder and bypasses the engine,
    # so the widget namespace does not leak into the nested build.
    assert widget_factory().name == "Ada"
    assert wrapper_factory().widget.name == "w"


class TestSubfactoryOverride:
    @pytest.fixture
    def wrapper_factory__widget(self):
        return Widget(name="custom")

    def test_override(self, wrapper_factory) -> None:
        assert wrapper_factory().widget.name == "custom"


def test_lazy_fixture_override_is_lazy(tracked_creations, request) -> None:
    # Requesting the model fixture must not eagerly set up the ``LazyFixture`` target.
    container = request.getfixturevalue("other_container")
    assert isinstance(container, Container)
    assert tracked_creations == ["tracked"]


def test_lazy_fixture_override_applies(tracked_creations, request) -> None:
    container_factory = request.getfixturevalue("container_factory")
    other_tracked = request.getfixturevalue("other_tracked")
    assert container_factory().tracked is other_tracked
