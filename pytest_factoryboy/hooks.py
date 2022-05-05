"""pytest-factoryboy pytest hooks."""

from pytest import FixtureRequest


def pytest_factoryboy_done(request: FixtureRequest) -> None:
    """Called after all factory based fixtures and their post-generation actions were evaluated."""
