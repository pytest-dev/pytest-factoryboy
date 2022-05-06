"""pytest-factoryboy pytest hooks."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pytest import FixtureRequest


def pytest_factoryboy_done(request: FixtureRequest) -> None:
    """Called after all factory based fixtures and their post-generation actions were evaluated."""
