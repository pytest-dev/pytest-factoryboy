"""pytest-factoryboy compatibility."""


def get_fixture_value(request, *args):
    """Compatibility check for pytest2 FixtureRequest.getfuncargvalue method."""
    try:
        return request.getfixturevalue(*args)
    except AttributeError:
        return request.getfuncargvalue(*args)
