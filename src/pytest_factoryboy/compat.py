from __future__ import annotations

from collections.abc import Sequence
from importlib.metadata import version

from _pytest.fixtures import FixtureDef, FixtureManager
from _pytest.nodes import Node
from packaging.version import parse as parse_version
from typing_extensions import TypeAlias

pytest_version = parse_version(version("pytest"))

__all__ = ("PostGenerationContext", "getfixturedefs", "PytestFixtureT")

try:
    from factory.declarations import PostGenerationContext
except ImportError:  # factory_boy < 3.2.0
    from factory.builder import (  # type: ignore[attr-defined, no-redef]
        PostGenerationContext,
    )

if pytest_version.release >= (8, 1):

    def getfixturedefs(
        fixturemanager: FixtureManager, fixturename: str, node: Node
    ) -> Sequence[FixtureDef[object]] | None:
        return fixturemanager.getfixturedefs(fixturename, node)

else:

    def getfixturedefs(
        fixturemanager: FixtureManager, fixturename: str, node: Node
    ) -> Sequence[FixtureDef[object]] | None:
        return fixturemanager.getfixturedefs(fixturename, node.nodeid)  # type: ignore[arg-type]


if pytest_version.release >= (8, 4):
    from _pytest.fixtures import FixtureFunctionDefinition

    PytestFixtureT: TypeAlias = FixtureFunctionDefinition
else:
    from _pytest.fixtures import FixtureFunction

    PytestFixtureT: TypeAlias = FixtureFunction  # type: ignore[misc, no-redef]
