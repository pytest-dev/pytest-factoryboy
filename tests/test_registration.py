from __future__ import annotations

from dataclasses import dataclass

import factory
import pytest
from _pytest.fixtures import FixtureLookupError

from pytest_factoryboy import register


@dataclass(eq=False)
class Foo:
    value: str


class TestRegisterDirectDecorator:
    @register()
    class FooFactory(factory.Factory):
        class Meta:
            model = Foo

        value = "@register()"

    def test_register(self, foo: Foo):
        """Test that `register` can be used as a decorator with 0 arguments."""
        assert foo.value == "@register()"


class TestRegisterDecoratorNoArgs:
    @register
    class FooFactory(factory.Factory):
        class Meta:
            model = Foo

        value = "@register"

    def test_register(self, foo: Foo):
        """Test that `register` can be used as a direct decorator."""
        assert foo.value == "@register"


class TestRegisterDecoratorWithArgs:
    @register(value="bar")
    class FooFactory(factory.Factory):
        class Meta:
            model = Foo

        value = None

    def test_register(self, foo: Foo):
        """Test that `register` can be used as a decorator with arguments overriding the factory declarations."""
        assert foo.value == "bar"


class TestRegisterAlternativeName:
    @register(_name="second_foo")
    class FooFactory(factory.Factory):
        class Meta:
            model = Foo

        value = None

    def test_register(self, request, second_foo: Foo):
        """Test that `register` invoked with a specific `_name` registers the fixture under that `_name`."""
        assert second_foo.value == None

        with pytest.raises(FixtureLookupError) as exc:
            request.getfixturevalue("foo")
        assert exc.value.argname == "foo"


class TestRegisterAlternativeNameAndArgs:
    @register(_name="second_foo", value="second_bar")
    class FooFactory(factory.Factory):
        class Meta:
            model = Foo

        value = None

    def test_register(self, second_foo: Foo):
        """Test that `register` can be invoked with `_name` to specify an alternative
        fixture name and with any kwargs to override the factory declarations."""
        assert second_foo.value == "second_bar"


class TestRegisterCall:
    class FooFactory(factory.Factory):
        class Meta:
            model = Foo

        value = "register(FooFactory)"

    register(FooFactory)
    register(FooFactory, _name="second_foo", value="second_bar")

    def test_register(self, foo: Foo, second_foo: Foo):
        """Test that `register` can be invoked directly."""
        assert foo.value == "register(FooFactory)"
        assert second_foo.value == "second_bar"
