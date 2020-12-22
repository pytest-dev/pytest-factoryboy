"""Test post-generation dependecies."""

import factory
import pytest

from factory.declarations import NotProvided
from pytest_factoryboy import register


class Foo(object):
    def __init__(self, value, expected):
        self.value = value
        self.expected = expected
        self.secret = ""
        self.number = 4

    def set_secret(self, new_secret):
        self.secret = new_secret

    def set_number(self, new_number=987):
        self.number = new_number


class Bar(object):
    def __init__(self, foo):
        self.foo = foo


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
    def set1(foo, create, value, **kwargs):
        foo.value = 1

    @factory.post_generation
    def set2(foo, create, value, **kwargs):
        if create and value:
            foo.value = value

    @classmethod
    def _after_postgeneration(cls, obj, create, results=None):
        obj._postgeneration_results = results
        obj._create = create


class BarFactory(factory.Factory):

    """Bar factory."""

    foo = factory.SubFactory(FooFactory)

    @classmethod
    def _create(cls, model_class, foo):
        assert foo.value == foo.expected
        bar = super(BarFactory, cls)._create(model_class, foo=foo)
        foo.bar = bar
        return bar

    class Meta:
        model = Bar


def test_postgen_invoked(foo):
    """Test that post-generation hooks are done and the value is 2."""
    assert foo.value == 1


register(BarFactory)


@pytest.mark.parametrize("foo__value", [3])
@pytest.mark.parametrize("foo__expected", [1])
def test_depends_on(bar):
    """Test that post-generation hooks are done and the value is 1."""
    assert bar.foo.value == 1


def test_getfixturevalue(request, factoryboy_request):
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


def test_after_postgeneration(foo):
    """Test _after_postgeneration is called."""
    assert foo._postgeneration_results == {"set1": None, "set2": None, "secret": None, "number": None}
    assert foo._create is True


@pytest.mark.parametrize("foo__set2", [123])
def test_postgeneration_fixture(foo):
    """Test fixture for ``PosGeneration`` declaration."""
    assert foo.value == 123


@pytest.mark.parametrize(
    ("foo__secret", "foo__number"),
    [
        ("test secret", 456),
    ],
)
def test_postgenerationmethodcall_fixture(foo):
    """Test fixture for ``PosGenerationMethodCall`` declaration."""
    assert foo.secret == "test secret"
    assert foo.number == 456


class Ordered(object):
    value = None


@register
class OrderedFactory(factory.Factory):
    class Meta:
        model = Ordered

    @factory.post_generation
    def zzz(obj, create, val, **kwargs):
        obj.value = "zzz"

    @factory.post_generation
    def aaa(obj, create, val, **kwargs):
        obj.value = "aaa"


def test_ordered(ordered):
    """Test post generation are ordered by creation counter."""
    assert ordered.value == "aaa"
