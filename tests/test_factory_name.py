from __future__ import annotations

import factory

from pytest_factoryboy import register


@register
class JSONPayloadFactory(factory.Factory):
    class Meta:
        model = dict

    name = "John Doe"


def test_fixture_name_as_expected(json_payload):
    """Test that the json_payload fixture is registered from the JSONPayloadFactory."""
    assert json_payload["name"] == "John Doe"


def test_fixture_name_cant_be_determined(pytester):
    """Test that an error is raised if the fixture name can't be determined."""
    pytester.makepyfile(
        """
        import factory
        from pytest_factoryboy import register

        @register
        class JSONPayloadF(factory.Factory):
            class Meta:
                model = dict

            name = "John Doe"

        """
    )
    res = pytester.runpytest()
    res.assert_outcomes(errors=1)
    res.stdout.fnmatch_lines("*JSONPayloadF *does not follow*naming convention*")


def test_invalid_factory_name_override(pytester):
    """Test that, although the factory name doesn't follow the naming convention, it can still be overridden."""
    pytester.makepyfile(
        """
        import factory
        from pytest_factoryboy import register

        @register(_name="payload")
        class JSONPayloadF(factory.Factory):
            class Meta:
                model = dict

            name = "John Doe"


        def test_payload(payload):
            assert payload["name"] == "John Doe"
        """
    )
    res = pytester.runpytest()
    res.assert_outcomes(passed=1)
