"""Tests for the generation engine (:mod:`pytest_factoryboy.engine`)."""

from __future__ import annotations

from dataclasses import dataclass

import factory

from pytest_factoryboy import engine


@dataclass
class Widget:
    name: str


class WidgetFactory(factory.Factory):
    class Meta:
        model = Widget

    name = "w"


def test_bind_factory_returns_a_bound_subclass(request) -> None:
    bound = engine.bind_factory(WidgetFactory, request, "widget")

    assert bound is not WidgetFactory
    assert issubclass(bound, WidgetFactory)
    assert bound._factoryboy_request is request
    assert bound._factoryboy_model_name == "widget"
    assert bound._factoryboy_original_factory is WidgetFactory


def test_bind_factory_routes_generation_through_the_engine(monkeypatch, request) -> None:
    seen: list[str] = []
    real_generate = engine.generate

    def spy(cls, strategy, params):
        seen.append(cls.__name__)
        return real_generate(cls, strategy, params)

    monkeypatch.setattr(engine, "generate", spy)
    bound = engine.bind_factory(WidgetFactory, request, "widget")

    assert bound().name == "w"
    assert seen == ["WidgetFactory"]
