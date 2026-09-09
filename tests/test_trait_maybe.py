import datetime
from typing import NamedTuple, Any

import factory
from pytest_factoryboy import register


class User(NamedTuple):
    is_active: bool
    deactivation_date: datetime.datetime


class UserFactory(factory.Factory):
    class Meta:
        model = User

    is_active = True
    deactivation_date = factory.Maybe(
        "is_active",
        yes_declaration=None,
        no_declaration=factory.fuzzy.FuzzyDateTime(
            datetime.datetime.now(tz=datetime.timezone.utc) - datetime.timedelta(days=10)
        ),
    )


class Package(NamedTuple):
    box: bool
    packed_by: Any


class PackageFactory(factory.Factory):
    class Meta:
        model = Package

    box = False
    packed_by = None

    class Params:
        packed = factory.Trait(
            box=True,
            packed_by=factory.SubFactory(UserFactory),
        )


class Order(NamedTuple):
    state: str
    shipped_on: datetime.datetime
    shipped_by: Any


class OrderFactory(factory.Factory):
    class Meta:
        model = Order

    state = "pending"
    shipped_on = None
    shipped_by = None

    class Params:
        shipped = factory.Trait(
            state="shipped",
            shipped_on=datetime.date.today(),
            shipped_by=factory.RelatedFactory(UserFactory),
        )


register(UserFactory)
register(PackageFactory)
register(OrderFactory)


def test_maybe(user, factoryboy_request, request):
    assert user.deactivation_date is None


def test_trait_subfactory(package, factoryboy_request, request):
    assert not package.box


def test_trait_related_factory(order, factoryboy_request, request):
    # FIXME: although defined as None, value of shipped_by is not passed during creation
    # which causes create() to fail missing an argument
    # Bug hitting all factory-boy versions
    assert order.state == "pending"
