# TODO: Unit test get_model_name
from tests.compat import assert_outcomes


def test_generic_model_with_custom_name_no_warning(testdir):
    testdir.makepyfile(
        """
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
        """
    )
    result = testdir.runpytest("-Werror")  # Warnings become errors
    assert_outcomes(result, passed=1)


def test_generic_model_name_raises_warning(testdir):
    testdir.makepyfile(
        """
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
    """
    )
    result = testdir.runpytest()
    assert_outcomes(result, passed=1)
    result.stdout.fnmatch_lines(
        "*UserWarning: Using a *class*dict* as model type for *JSONPayloadFactory* is discouraged*"
    )


def test_generic_model_with_register_override_no_warning(testdir):
    testdir.makepyfile(
        """
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

        """
    )
    result = testdir.runpytest("-Werror")  # Warnings become errors
    assert_outcomes(result, passed=1)


def test_using_generic_model_name_for_subfactory_raises_warning(testdir):
    testdir.makepyfile(
        """
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
        """
    )

    result = testdir.runpytest()
    assert_outcomes(result, errors=1)
    result.stdout.fnmatch_lines(
        "*UserWarning: Using *class*dict* as model type for *JSONPayloadFactory* is discouraged*"
    )
