"""pytest-factoryboy plugin."""
from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from typing import Any

    from _pytest.config import PytestPluginManager
    from _pytest.fixtures import FixtureRequest, SubRequest
    from _pytest.nodes import Item
    from _pytest.python import Metafunc
    from factory import Factory

    from .fixture import DeferredFunction


class CycleDetected(Exception):
    pass


class Request:
    """PyTest FactoryBoy request."""

    def __init__(self) -> None:
        """Create pytest_factoryboy request."""
        self.deferred: list[list[DeferredFunction]] = []
        self.results: dict[str, dict[str, Any]] = defaultdict(dict)
        self.model_factories: dict[str, type[Factory]] = {}
        self.in_progress: set[DeferredFunction] = set()

    def defer(self, functions: list[DeferredFunction]) -> None:
        """Defer post-generation declaration execution until the end of the test setup.

        :param functions: Functions to be deferred.
        :note: Once already finalized all following defer calls will execute the function directly.
        """
        self.deferred.append(functions)

    def get_deps(self, request: SubRequest, fixture: str, deps: set[str] | None = None) -> set[str]:
        request = request.getfixturevalue("request")

        if deps is None:
            deps = {fixture}
        if fixture == "request":
            return deps

        for fixturedef in request._fixturemanager.getfixturedefs(fixture, request._pyfuncitem.parent.nodeid) or []:
            for argname in fixturedef.argnames:
                if argname not in deps:
                    deps.add(argname)
                    deps.update(self.get_deps(request, argname, deps))
        return deps

    def get_current_deps(self, request: FixtureRequest | SubRequest) -> set[str]:
        deps = set()
        while hasattr(request, "_parent_request"):
            if request.fixturename and request.fixturename not in getattr(request, "_fixturedefs", {}):
                deps.add(request.fixturename)
            request = request._parent_request
        return deps

    def execute(self, request: SubRequest, function: DeferredFunction, deferred: list[DeferredFunction]) -> None:
        """Execute deferred function and store the result."""
        if function in self.in_progress:
            raise CycleDetected()
        fixture = function.name
        model, attr = fixture.split("__", 1)
        if function.is_related:
            deps = self.get_deps(request, fixture)
            if deps.intersection(self.get_current_deps(request)):
                raise CycleDetected()
        self.model_factories[model] = function.factory

        self.in_progress.add(function)
        self.results[model][attr] = function(request)
        deferred.remove(function)
        self.in_progress.remove(function)

    def after_postgeneration(self, request: SubRequest) -> None:
        """Call _after_postgeneration hooks."""
        for model in list(self.results.keys()):
            results = self.results.pop(model)
            obj = request.getfixturevalue(model)
            factory = self.model_factories[model]
            factory._after_postgeneration(obj, create=True, results=results)

    def evaluate(self, request: SubRequest) -> None:
        """Finalize, run deferred post-generation actions, etc."""
        while self.deferred:
            try:
                deferred = self.deferred[-1]
                for function in list(deferred):
                    self.execute(request, function, deferred)
                if not deferred:
                    self.deferred.remove(deferred)
            except CycleDetected:
                return

        if not self.deferred:
            self.after_postgeneration(request)


@pytest.fixture
def factoryboy_request() -> Request:
    """PyTest FactoryBoy request fixture."""
    return Request()


# type ignored because pluggy v1.0.0 has no type annotations:
# https://github.com/pytest-dev/pluggy/issues/191
@pytest.hookimpl(tryfirst=True)  # type: ignore[misc]
def pytest_runtest_call(item: Item) -> None:
    """Before the test item is called."""
    # TODO: We should instead do an `if isinstance(item, Function)`.
    try:
        request = item._request  # type: ignore[attr-defined]
    except AttributeError:
        # pytest-pep8 plugin passes Pep8Item here during tests.
        return
    factoryboy_request = request.getfixturevalue("factoryboy_request")
    factoryboy_request.evaluate(request)
    assert not factoryboy_request.deferred
    request.config.hook.pytest_factoryboy_done(request=request)


def pytest_addhooks(pluginmanager: PytestPluginManager) -> None:
    """Register plugin hooks."""
    from pytest_factoryboy import hooks

    pluginmanager.add_hookspecs(hooks)


def pytest_generate_tests(metafunc: Metafunc) -> None:
    related: list[str] = []
    for arg2fixturedef in metafunc._arg2fixturedefs.values():
        fixturedef = arg2fixturedef[-1]
        related_fixtures = getattr(fixturedef.func, "_factoryboy_related", [])
        related.extend(related_fixtures)

    metafunc.fixturenames.extend(related)
