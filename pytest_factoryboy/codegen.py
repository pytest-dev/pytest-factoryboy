from __future__ import annotations

import inspect
import logging
from typing import Any, Callable, TypeVar

import pytest
from _pytest.fixtures import FixtureRequest

logger = logging.getLogger(__name__)

T = TypeVar("T")


def _fixture(name: str, related: list[str]) -> Callable[[Callable[..., T]], Callable[..., T]]:
    def fixture_maker(fn: Callable[..., T]) -> Callable[..., T]:
        fn._factoryboy_related = related  # type: ignore[attr-defined]
        return pytest.fixture(fn, name=name)

    return fixture_maker


def generate_fixture(
    name: str,
    function: Callable[..., T],  # TODO: Try to use ParamSpec instead of Callable
    function_kwargs: dict[str, Any],
    deps: list[str] | None = None,
    related: list[str] | None = None,
) -> Callable[..., T]:
    if related is None:
        related = []
    if deps is None:
        deps = []

    def fn(request: FixtureRequest, **kwargs: Any) -> T:
        return function(request, **function_kwargs)

    sig = inspect.signature(fn)
    params = [sig.parameters["request"]] + [
        inspect.Parameter(name=name, kind=inspect.Parameter.POSITIONAL_OR_KEYWORD) for name in deps
    ]
    sig = sig.replace(parameters=tuple(params))
    fn.__signature__ = sig  # type: ignore[attr-defined]

    fix = _fixture(name=name, related=related)(fn)
    return fix
