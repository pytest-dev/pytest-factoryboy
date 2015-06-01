"""Test factory registration validation."""

import factory
import pytest
from pytest_factoryboy import register


class WithoutModelFactory(factory.Factory):

    """A factory without model."""


class AbstractFactory(factory.Factory):

    """Abstract factory."""

    class Meta:
        abstract = True
        model = dict


def test_without_model():
    """Test that factory without model can't be registered."""
    with pytest.raises(AssertionError):
        register(WithoutModelFactory)


def test_abstract():
    with pytest.raises(AssertionError):
        register(AbstractFactory)
