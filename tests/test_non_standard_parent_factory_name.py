from __future__ import annotations

from dataclasses import dataclass

import factory

from pytest_factoryboy import register


@dataclass
class Owner:
    pass


@dataclass
class Foo:
    owner: Owner


@register
class OwnerFactory(factory.Factory):
    """Foo factory."""

    class Meta:
        model = Owner


@register(_name="foo")
class FooMaker(factory.Factory):  # Deliberately breaking the naming convention for the purpose of this test
    class Meta:
        model = Foo

    owner = factory.SubFactory(OwnerFactory)


def test_foo_maker(foo):
    assert foo.owner
