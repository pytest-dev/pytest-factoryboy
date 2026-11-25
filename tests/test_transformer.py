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
register(
    UserFactory,
    "user_with_force_in_register",
    password=factory.Transformer.Force("plain_from_register"),
)


def test_transformer_applied_once(user: User):
    """The model fixture must not apply the transformation again on top of the factory's own declaration."""
    assert user.password == "hashed(secret)"
    assert user.password == UserFactory().password


def test_transformer_register_override(user_with_register_override: User):
    """A value passed to ``register(...)`` is transformed, like a value passed to the factory."""
    assert user_with_register_override.password == "hashed(from register)"


def test_transformer_force_in_register(user_with_force_in_register: User):
    """``Transformer.Force`` passed to ``register(...)`` bypasses the transformation."""
    assert user_with_force_in_register.password == "plain_from_register"


def test_transformer_applied_once_via_factory(user_factory):
    """The factory path must not apply the transformation again on top of the declaration."""
    assert user_factory().password == "hashed(secret)"


@pytest.mark.parametrize("user_factory__password", ["from factory namespace"])
def test_transformer_factory_namespace(user_factory):
    """A value in the factory namespace is transformed, like a value passed to the factory."""
    assert user_factory().password == "hashed(from factory namespace)"


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
