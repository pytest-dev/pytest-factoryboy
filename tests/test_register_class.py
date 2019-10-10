import factory
import pytest
from pytest_factoryboy import register


class EmptyModel(object):
    pass


class FooFactory(factory.Factory):
    class Meta:
        model = EmptyModel


def test_register_model_fixture_with_name_same_as_factory_fixture():
    with pytest.raises(AssertionError) as excinfo:
        register(FooFactory, 'foo_factory')
    assert 'FooFactory' in str(excinfo)
    assert 'foo_factory' in str(excinfo)
