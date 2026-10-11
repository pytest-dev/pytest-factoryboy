"""Tests for declarations that capture call-time overrides, such as ``factory.Transformer``."""

from __future__ import annotations

from dataclasses import dataclass

import factory
import pytest

from pytest_factoryboy import register

# ``factory.Transformer`` was introduced in factory_boy 3.3.0
pytest.importorskip("factory", minversion="3.3.0")


@dataclass
class User:
    """User account."""

    password: str


def hash_password(password: str) -> str:
    return f"hashed({password})"


@register
class UserFactory(factory.Factory):
    """User factory."""

    class Meta:
        model = User

    password = factory.Transformer("secret", transform=hash_password)


register(UserFactory, "user_with_register_override", password="from register")


def test_transformer_applied_once(user: User):
    """The model fixture must not apply the transformation again on top of the factory's own declaration."""
    assert user.password == "hashed(secret)"
    assert user.password == UserFactory().password


def test_transformer_register_override(user_with_register_override: User):
    """A value passed to ``register(...)`` is transformed, like a value passed to the factory."""
    assert user_with_register_override.password == "hashed(from register)"


class TestFixtureOverride:
    @pytest.fixture
    def user__password(self):
        return "from fixture"

    def test_transformer_fixture_override(self, user: User):
        """A value provided by an attribute fixture is transformed, like a value passed to the factory."""
        assert user.password == "hashed(from fixture)"


class TestForce:
    @pytest.fixture
    def user__password(self):
        return factory.Transformer.Force("plain")

    def test_transformer_force(self, user: User):
        """``Transformer.Force`` bypasses the transformation, like when passed to the factory."""
        assert user.password == "plain"
