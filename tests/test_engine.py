"""Tests for the generation engine (:mod:`pytest_factoryboy.engine`)."""

from __future__ import annotations

import gc
import weakref
from dataclasses import dataclass

import factory

from pytest_factoryboy import engine
from pytest_factoryboy.engine import original_factory


@dataclass
class Widget:
    name: str


class WidgetFactory(factory.Factory):
    class Meta:
        model = Widget

    name = "w"


def test_bind_factory_returns_a_bound_subclass() -> None:
    bound = engine.bind_factory(WidgetFactory)

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


def test_original_factory_of_a_subclass_is_the_wrapped_factory() -> None:
    bound = engine.bind_factory(WidgetFactory)

    class Sub(bound):
        pass

    assert original_factory(Sub) is WidgetFactory


def test_bind_factory_does_not_mutate_the_caller_factory() -> None:
    original_generate = WidgetFactory._generate.__func__

    engine.bind_factory(WidgetFactory)

    assert WidgetFactory._generate.__func__ is original_generate


def test_bind_factory_does_not_store_state_globally() -> None:
    """The bound class owns the engine state; nothing global keeps it alive."""
    bound = engine.bind_factory(WidgetFactory)
    ref = weakref.ref(bound)

    del bound
    gc.collect()

    assert ref() is None


def test_bind_factory_keeps_the_factory_abstract() -> None:
    class AbstractFactory(factory.Factory):
        class Meta:
            model = Widget
            abstract = True

    bound = engine.bind_factory(AbstractFactory)

    assert bound._meta.abstract is True
