"""Test post-generation dependecies."""

import factory
import pytest

from pytest_factoryboy import register


class Foo(object):

    def __init__(self, value, expected):
        self.value = value
        self.expected = expected


class Bar(object):

    def __init__(self, foo):
        self.foo = foo


@register
class FooFactory(factory.Factory):

    """Foo factory."""

    class Meta:
        model = Foo

    value = 0
    expected = 0
    """Value that is expected at the constructor."""

    @factory.post_generation
    def set1(foo, create, value, **kwargs):
        foo.value = 1

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


@pytest.mark.parametrize('foo__value', [3])
@pytest.mark.parametrize('foo__expected', [1])
def test_depends_on(bar):
    """Test that post-generation hooks are done and the value is 1."""
    assert bar.foo.value == 1


def test_getfuncargvalue(request, factoryboy_request):
    """Test post-generation declarations via the getfuncargvalue."""
    foo = request.getfuncargvalue('foo')
    assert not factoryboy_request.deferred
    assert foo.value == 1


def test_after_postgeneration(foo):
    """Test _after_postgeneration is called."""
    assert foo._postgeneration_results == {'set1': None}
    assert foo._create is True
