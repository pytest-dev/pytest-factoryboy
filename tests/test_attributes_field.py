from pytest_factoryboy import register
import factory


class EmptyModel(object):
    pass


class AttributesFactory(factory.Factory):
    class Meta:
        model = EmptyModel

    attributes = None


register(AttributesFactory, "with_attributes")


def test_factory_with_attributes(with_attributes):
    """Test that a factory can have a `attributes` field."""
    pass
