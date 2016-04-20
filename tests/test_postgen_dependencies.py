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

    @factory.post_generation
    def set2(foo, create, value, **kwargs):
        foo.value = 2

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
        return super(BarFactory, cls)._create(model_class, foo=foo)

    class Meta:
        model = Bar


def test_invocation_order(foo):
    """Test that post-generation hooks are done and the value is 2."""
    assert foo.value == 2


register(
    BarFactory,
    'depends_on_1',
    _postgen_dependencies=["foo__set1"],
)
"""Forces 'set1' to be evaluated first."""


register(
    BarFactory,
    'depends_on_2',
    _postgen_dependencies=["foo__set2"],
)
"""Forces 'set2' to be evaluated first."""


@pytest.mark.parametrize('foo__value', [3])
@pytest.mark.parametrize('foo__expected', [1])
def test_depends_on_1(depends_on_1):
    """Test that post-generation hooks are done and the value is 2."""
    assert depends_on_1.foo.value == 2


@pytest.mark.parametrize('foo__value', [3])
@pytest.mark.parametrize('foo__expected', [2])
def test_depends_on_2(depends_on_2):
    """Test that post-generation hooks are done and the value is 1."""
    assert depends_on_2.foo.value == 1


def test_getfuncargvalue(request):
    """Test post-generation declarations via the getfuncargvalue."""
    assert request.getfuncargvalue('foo')


def test_after_postgeneration(foo):
    """Test _after_postgeneration is called."""
    assert foo._postgeneration_results == {'set1': None, 'set2': None}
    assert foo._create is True
