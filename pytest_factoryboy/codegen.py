from __future__ import annotations

import inspect
import logging
from typing import Callable

import pytest

logger = logging.getLogger(__name__)


def _fixture(name, related):
    def fixture_maker(fn):
        fn._factoryboy_related = related
        return pytest.fixture(fn, name=name)

    return fixture_maker


def generate_fixture(name, function, function_kwargs, deps=None, related=None) -> Callable:
    if related is None:
        related = []
    if deps is None:
        deps = []
    kwargs_names = deps

    def fn(request, **kwargs):
        return function(request, **function_kwargs)

    sig = inspect.signature(fn)
    params = [sig.parameters["request"]] + [
        inspect.Parameter(name=name, kind=inspect.Parameter.POSITIONAL_OR_KEYWORD) for name in kwargs_names
    ]
    sig = sig.replace(parameters=tuple(params))
    fn.__signature__ = sig

    fix = _fixture(name=name, related=related)(fn)
    return fix
