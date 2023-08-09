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


def test_factory_request_fixtures_without_factory_only():
    class Foo:
        pass

    class FooFactory(factory.Factory):
        class Meta:
            model = Foo

    with pytest.raises(AssertionError, match="Can't register factory request fixtures unless _factory_only=True."):
        register(FooFactory, _factory_request_fixtures=["foo"])


def test_name_with_factory_only():
    class Foo:
        pass

    class FooFactory(factory.Factory):
        class Meta:
            model = Foo

    with pytest.raises(AssertionError, match="Can't set _name when _factory_only=True."):
        register(FooFactory, _name="foobar", _factory_only=True)


def test_factory_only_after_model_fixture():
    class Foo:
        pass

    class FooFactory(factory.Factory):
        class Meta:
            model = Foo

    register(FooFactory)

    with pytest.raises(AssertionError, match="Factory fixture foo_factory already exists."):
        register(FooFactory, _factory_only=True)
