import warnings

import factory
import pytest

from pytest_factoryboy.fixture import get_model_name, named_model
from tests.compat import assert_outcomes


def make_class(name: str):
    """Create a class with the given name."""
    return type(name, (object,), {})


@pytest.mark.parametrize("model_cls", [dict, set, list, frozenset, tuple])
def test_get_model_name_warns_for_common_containers(model_cls):
    """Test that a warning is raised when common containers are used as models."""

    class ModelFactory(factory.Factory):
        class Meta:
            model = model_cls

    with pytest.warns(
        UserWarning,
        match=rf"Using a .*{model_cls.__name__}.* as model type for .*ModelFactory.* is discouraged",
    ):
        assert get_model_name(ModelFactory)


def test_get_model_name_does_not_warn_for_user_defined_models():
    """Test that no warning is raised for when using user-defined models"""

    class Foo:
        pass

    class ModelFactory(factory.Factory):
        class Meta:
            model = Foo

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert get_model_name(ModelFactory) == "foo"


@pytest.mark.parametrize(
    ["model_cls", "expected"],
    [
        (make_class("Foo"), "foo"),
        (make_class("TwoWords"), "two_words"),
        (make_class("HTTPHeader"), "http_header"),
        (make_class("C3PO"), "c3_po"),
    ],
)
def test_get_model_name(model_cls, expected):
    """Test normal cases for ``get_model_name``."""

    class ModelFactory(factory.Factory):
        class Meta:
            model = model_cls

    assert get_model_name(ModelFactory) == expected


def test_named_model():
    """Assert behaviour of ``named_model``."""
    cls = named_model(dict, "Foo")

    assert cls.__name__ == "Foo"
    assert issubclass(cls, dict)


def test_generic_model_with_custom_name_no_warning(testdir):
    testdir.makepyfile("""
        from factory import Factory
        from pytest_factoryboy import named_model, register

        @register
        class JSONPayloadFactory(Factory):
            class Meta:
                model = named_model(dict, "JSONPayload")
            foo = "bar"


        def test_payload(json_payload: dict):
            assert isinstance(json_payload, dict)
            assert json_payload["foo"] == "bar"
        """)
    result = testdir.runpytest("-Werror")  # Warnings become errors
    assert_outcomes(result, passed=1)


def test_generic_model_name_raises_warning(testdir):
    testdir.makepyfile("""
        import builtins
        from factory import Factory
        from pytest_factoryboy import register

        @register
        class JSONPayloadFactory(Factory):
            class Meta:
                model = dict
            foo = "bar"


        def test_payload(dict):
            assert isinstance(dict, builtins.dict)
            assert dict["foo"] == "bar"
    """)
    result = testdir.runpytest()
    assert_outcomes(result, passed=1)
    result.stdout.fnmatch_lines(
        "*UserWarning: Using a *class*dict* as model type for *JSONPayloadFactory* is discouraged*"
    )


def test_generic_model_with_register_override_no_warning(testdir):
    testdir.makepyfile("""
        from factory import Factory
        from pytest_factoryboy import named_model, register

        @register(_name="json_payload")
        class JSONPayloadFactory(Factory):
            class Meta:
                model = dict
            foo = "bar"


        def test_payload(json_payload: dict):
            assert isinstance(json_payload, dict)
            assert json_payload["foo"] == "bar"

        """)
    result = testdir.runpytest("-Werror")  # Warnings become errors
    assert_outcomes(result, passed=1)


def test_using_generic_model_name_for_subfactory_raises_warning(testdir):
    testdir.makepyfile("""
        import builtins
        from factory import Factory, SubFactory
        from pytest_factoryboy import register

        @register(_name="JSONPayload")
        class JSONPayloadFactory(Factory):
            class Meta:
                model = dict  # no warning raised here, since we override the name at the @register(...)
            foo = "bar"

        class HTTPRequest:
            def __init__(self, json: dict):
                self.json = json

        @register
        class HTTPRequestFactory(Factory):
            class Meta:
                model = HTTPRequest

            json = SubFactory(JSONPayloadFactory)  # this will raise a warning

        def test_payload(http_request):
            assert http_request.json["foo"] == "bar"
        """)

    result = testdir.runpytest()
    assert_outcomes(result, errors=1)
    result.stdout.fnmatch_lines(
        "*UserWarning: Using *class*dict* as model type for *JSONPayloadFactory* is discouraged*"
    )
