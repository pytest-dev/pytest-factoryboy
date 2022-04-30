"""Test post-generation dependecies."""
from __future__ import annotations

from dataclasses import dataclass

import factory
import pytest

from pytest_factoryboy import register
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any
    from pytest_factoryboy.plugin import Request


@dataclass
class Foo:
    value: int
    expected: int


@dataclass
class Bar:
    foo: Foo


@register
class FooFactory(factory.Factory):

    """Foo factory."""

    class Meta:
        model = Foo

    value = 0
    expected = 0
    """Value that is expected at the constructor."""

    @factory.post_generation
    def set1(foo: Foo, create: bool, value: Any, **kwargs: Any) -> None:
        foo.value = 1

    @classmethod
    def _after_postgeneration(cls, obj: Foo, create: bool, results: dict[str, Any] | None = None) -> None:
        obj._postgeneration_results = results
        obj._create = create


class BarFactory(factory.Factory):

    """Bar factory."""

    foo = factory.SubFactory(FooFactory)

    @classmethod
    def _create(cls, model_class: type[Bar], foo: Foo) -> Bar:
        assert foo.value == foo.expected
        bar = super()._create(model_class, foo=foo)
        foo.bar = bar
        return bar

    class Meta:
        model = Bar


def test_postgen_invoked(foo: Foo):
    """Test that post-generation hooks are done and the value is 2."""
    assert foo.value == 1


register(BarFactory)


@pytest.mark.parametrize("foo__value", [3])
@pytest.mark.parametrize("foo__expected", [1])
def test_depends_on(bar: Bar):
    """Test that post-generation hooks are done and the value is 1."""
    assert bar.foo.value == 1


def test_getfixturevalue(request, factoryboy_request: Request):
    """Test post-generation declarations via the getfixturevalue."""
    foo = request.getfixturevalue("foo")
    assert not factoryboy_request.deferred
    assert foo.value == 1


def test_after_postgeneration(foo: Foo):
    """Test _after_postgeneration is called."""
    assert foo._postgeneration_results == {"set1": None}
    assert foo._create is True


class Ordered:
    value = None


@register
class OrderedFactory(factory.Factory):
    class Meta:
        model = Ordered

    @factory.post_generation
    def zzz(obj: Ordered, create: bool, val: Any, **kwargs: Any) -> None:
        obj.value = "zzz"

    @factory.post_generation
    def aaa(obj: Ordered, create: bool, val: Any, **kwargs: Any) -> None:
        obj.value = "aaa"


def test_ordered(ordered: Ordered):
    """Test post generation are ordered by creation counter."""
    assert ordered.value == "aaa"
