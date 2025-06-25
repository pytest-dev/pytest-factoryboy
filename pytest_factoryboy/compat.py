from __future__ import annotations

from collections.abc import Sequence
from importlib.metadata import version
from typing import Any

from _pytest.fixtures import FixtureDef, FixtureManager
from _pytest.nodes import Node
from packaging.version import parse as parse_version

pytest_version = parse_version(version("pytest"))

__all__ = ("PostGenerationContext", "getfixturedefs")

try:
    from factory.declarations import PostGenerationContext
except ImportError:  # factory_boy < 3.2.0
    from factory.builder import PostGenerationContext

if pytest_version.release >= (8, 1):

    def getfixturedefs(fixturemanager: FixtureManager, fixturename: str, node: Node) -> Sequence[FixtureDef[Any]] | None:
        return fixturemanager.getfixturedefs(fixturename, node)

else:

    def getfixturedefs(fixturemanager: FixtureManager, fixturename: str, node: Node) -> Sequence[FixtureDef[Any]] | None:
        return fixturemanager.getfixturedefs(fixturename, node.nodeid)  # type: ignore[arg-type]
