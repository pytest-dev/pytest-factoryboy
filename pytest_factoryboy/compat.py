from __future__ import annotations

import pathlib
import sys
from collections.abc import Sequence
from importlib.metadata import version

from _pytest.fixtures import FixtureDef, FixtureManager
from _pytest.nodes import Node
from packaging.version import parse as parse_version

pytest_version = parse_version(version("pytest"))

__all__ = ("PostGenerationContext", "path_with_stem", "getfixturedefs")

try:
    from factory.declarations import PostGenerationContext
except ImportError:  # factory_boy < 3.2.0
    from factory.builder import PostGenerationContext

if sys.version_info >= (3, 9):

    def path_with_stem(path: pathlib.Path, stem: str) -> pathlib.Path:
        return path.with_stem(stem)

else:

    def path_with_stem(path: pathlib.Path, stem: str) -> pathlib.Path:
        return path.with_name(stem + path.suffix)


if pytest_version.release >= (8, 1):

    def getfixturedefs(fixturemanager: FixtureManager, fixturename: str, node: Node) -> Sequence[FixtureDef] | None:
        return fixturemanager.getfixturedefs(fixturename, node)

else:

    def getfixturedefs(fixturemanager: FixtureManager, fixturename: str, node: Node) -> Sequence[FixtureDef] | None:
        return fixturemanager.getfixturedefs(fixturename, node.nodeid)
