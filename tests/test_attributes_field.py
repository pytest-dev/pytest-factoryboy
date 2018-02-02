from pytest_factoryboy import register
import factory

import pytest


class EmptyModel(object):
    pass


class AttributesFactory(factory.Factory):
    class Meta:
        model = EmptyModel

    attributes = None


register(AttributesFactory, "with_attributes")


@pytest.mark.skip(reason="Doesn't work in FactoryBoy at the moment")
def test_factory_with_attributes():
    """Test that a factory can have a `attributes` field when used as a factory."""
    AttributesFactory()


@pytest.mark.skip(reason="Doesn't work in FactoryBoy at the moment")
def test_factory_fixture_with_attributes(with_attributes):
    """Test that a factory can have a `attributes` field when used as a fixture."""
    pass
