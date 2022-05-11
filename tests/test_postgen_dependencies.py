"""Test post-generation dependencies."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import factory
import pytest
from factory.declarations import NotProvided

from pytest_factoryboy import register

if TYPE_CHECKING:
    from typing import Any

    from pytest_factoryboy.plugin import Request


@dataclass
class Foo:
    value: int
    expected: int
    secret: str = ""
    number: int = 4

    def set_secret(self, new_secret: str) -> None:
        self.secret = new_secret

    def set_number(self, new_number: int = 987) -> None:
        self.number = new_number

    bar: Bar | None = None

    # NOTE: following attributes are used internally only for assertions
    _create: bool | None = None
    _postgeneration_results: dict[str, Any] = field(default_factory=dict)


@dataclass
class Bar:
    foo: Foo


@dataclass
class Baz:
    foo: Foo


@register
class BazFactory(factory.Factory):
    class Meta:
        model = Baz

    foo = None


@register
class FooFactory(factory.Factory):
    """Foo factory."""

    class Meta:
        model = Foo

    value = 0
    #: Value that is expected at the constructor
    expected = 0

    secret = factory.PostGenerationMethodCall("set_secret", "super secret")
    number = factory.PostGenerationMethodCall("set_number")

    @factory.post_generation
    def set1(foo: Foo, create: bool, value: Any, **kwargs: Any) -> str:
        foo.value = 1
        return "set to 1"

    baz = factory.RelatedFactory(BazFactory, factory_related_name="foo")

    @factory.post_generation
    def set2(foo, create, value, **kwargs):
        if create and value:
            foo.value = value

    @classmethod
    def _after_postgeneration(cls, obj: Foo, create: bool, results: dict[str, Any] | None = None) -> None:
        obj._postgeneration_results = results or {}
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
    assert foo.secret == "super secret"
    assert foo.number == 987


def test_postgenerationmethodcall_getfixturevalue(request, factoryboy_request):
    """Test default fixture value generated for ``PostGenerationMethodCall``."""
    secret = request.getfixturevalue("foo__secret")
    number = request.getfixturevalue("foo__number")
    assert not factoryboy_request.deferred
    assert secret == "super secret"
    assert number is NotProvided


def test_postgeneration_getfixturevalue(request, factoryboy_request):
    """Ensure default fixture value generated for ``PostGeneration`` is `None`."""
    set1 = request.getfixturevalue("foo__set1")
    set2 = request.getfixturevalue("foo__set2")
    assert not factoryboy_request.deferred
    assert set1 is None
    assert set2 is None


def test_after_postgeneration(foo: Foo):
    """Test _after_postgeneration is called."""
    assert foo._create is True
    assert foo._postgeneration_results.pop("baz")
    assert foo._postgeneration_results == {"set1": "set to 1", "set2": None, "secret": None, "number": None}


@pytest.mark.parametrize("foo__set2", [123])
def test_postgeneration_fixture(foo: Foo):
    """Test fixture for ``PostGeneration`` declaration."""
    assert foo.value == 123


@pytest.mark.parametrize(
    ("foo__secret", "foo__number"),
    [
        ("test secret", 456),
    ],
)
def test_postgenerationmethodcall_fixture(foo: Foo):
    """Test fixture for ``PostGenerationMethodCall`` declaration."""
    assert foo.secret == "test secret"
    assert foo.number == 456


@dataclass
class Ordered:
    value: str | None = None


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
