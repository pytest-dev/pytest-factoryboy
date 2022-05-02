from dataclasses import dataclass

import pytest
from _pytest.fixtures import FixtureLookupError
from factory import Factory

from pytest_factoryboy import register


@dataclass
class Foo:
    value: str


@register
class FooFactory(Factory):
    class Meta:
        model = Foo

    value = "module_foo"


def test_module_namespace(foo):
    assert foo.value == "module_foo"


class TestClassNamespace:
    @register
    class FooFactory(Factory):
        class Meta:
            model = Foo

        value = "class_foo"

    register(FooFactory, "class_foo")

    def test_class_namespace(self, class_foo, foo):
        assert foo.value == class_foo.value == "class_foo"

    class TestNestedClassNamespace:
        @register
        class FooFactory(Factory):
            class Meta:
                model = Foo

            value = "nested_class_foo"

        register(FooFactory, "nested_class_foo")

        def test_nested_class_namespace(self, foo, nested_class_foo):
            assert foo.value == nested_class_foo.value == "nested_class_foo"

    def test_nested_class_factories_dont_pollute_the_class(self, request):
        with pytest.raises(FixtureLookupError):
            request.getfixturevalue("nested_class_foo")


def test_class_factories_dont_pollute_the_module(request):
    with pytest.raises(FixtureLookupError):
        request.getfixturevalue("class_foo")
    with pytest.raises(FixtureLookupError):
        request.getfixturevalue("nested_class_foo")
