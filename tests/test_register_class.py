import factory
from pytest_factoryboy import register


class EmptyModel(object):
    pass


class FooFactory(factory.Factory):
    class Meta:
        model = EmptyModel


register(FooFactory, "foo_factory")


def test_factory_with_attributes(foo_factory):
    """Test that foo_factory can be used / throws a proper error."""
    pass
