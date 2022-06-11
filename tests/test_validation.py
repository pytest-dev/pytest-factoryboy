"""Test factory registration validation."""

import factory
import pytest

from pytest_factoryboy import register


def test_without_model():
    """Test that factory without model can't be registered."""

    class WithoutModelFactory(factory.Factory):
        """A factory without model."""

    with pytest.raises(AssertionError, match="Can't register abstract factories"):
        register(WithoutModelFactory)


def test_abstract():
    class AbstractFactory(factory.Factory):
        """Abstract factory."""

        class Meta:
            abstract = True
            model = dict

    with pytest.raises(AssertionError, match="Can't register abstract factories"):
        register(AbstractFactory)


def test_fixture_name_conflict():
    class Foo:
        pass

    class FooFactory(factory.Factory):
        class Meta:
            model = Foo

    with pytest.raises(AssertionError, match="Naming collision"):
        register(FooFactory, "foo_factory")
