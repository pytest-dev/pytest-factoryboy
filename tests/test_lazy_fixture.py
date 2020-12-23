"""Test LazyFixture related features."""
import factory
import pytest

from pytest_factoryboy import LazyFixture
from pytest_factoryboy import register


class User:
    """User account."""

    def __init__(self, username, password, is_active):
        self.username = username
        self.password = password
        self.is_active = is_active


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
