"""Test LazyFixture related features."""
from __future__ import annotations

from dataclasses import dataclass

import factory
import pytest

from pytest_factoryboy import register, LazyFixture


@dataclass
class User:
    """User account."""

    username: str
    password: str
    is_active: bool


class UserFactory(factory.Factory):
    """User factory."""

    class Meta:
        model = User

    username = factory.faker.Faker("user_name")
    password = factory.faker.Faker("password")
    is_active = factory.LazyAttribute(lambda f: f.password == "ok")


register(UserFactory)


register(
    UserFactory,
    "partial_user",
    password=LazyFixture("ok_password"),
)


@pytest.fixture
def ok_password() -> str:
    return "ok"


@pytest.mark.parametrize("user__password", [LazyFixture("ok_password")])
def test_lazy_attribute(user: User):
    """Test LazyFixture value is extracted before the LazyAttribute is called."""
    assert user.is_active


def test_lazy_attribute_partial(partial_user: User):
    """Test LazyFixture value is extracted before the LazyAttribute is called. Partial."""
    assert partial_user.is_active
