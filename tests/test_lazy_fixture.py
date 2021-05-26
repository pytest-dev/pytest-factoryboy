"""Test LazyFixture related features."""
from typing import NamedTuple

import factory
import pytest

from pytest_factoryboy import register, LazyFixture


class User(NamedTuple):
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
def ok_password():
    return "ok"


@pytest.mark.parametrize("user__password", [LazyFixture("ok_password")])
def test_lazy_attribute(user):
    """Test LazyFixture value is extracted before the LazyAttribute is called."""
    assert user.is_active


def test_lazy_attribute_partial(partial_user):
    """Test LazyFixture value is extracted before the LazyAttribute is called. Partial."""
    assert partial_user.is_active


class UserPost(NamedTuple):
    """A message posted by a user"""

    user: User
    message: str


class UserPostFactory(factory.Factory):
    class Meta:
        model = UserPost

    user = LazyFixture("user")
    message = factory.faker.Faker("paragraph")


register(UserPostFactory)


def test_lazy_fixture_in_factory_fixture(user_post_factory, user):
    user_post = user_post_factory()
    assert user_post.user is user


def test_lazy_fixture_in_factory_fixture_create_overrides(user_post_factory, partial_user):
    user_post = user_post_factory(user=LazyFixture("partial_user"))
    assert user_post.user is partial_user
