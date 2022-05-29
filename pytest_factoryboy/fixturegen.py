from __future__ import annotations

import functools
import inspect
from typing import Callable, Collection, TypeVar

import pytest
from typing_extensions import ParamSpec

T = TypeVar("T")
P = ParamSpec("P")


def create_fixture(
    name: str,
    function: Callable[P, T],
    fixtures: Collection[str] | None = None,
) -> Callable[P, T]:
    """Dynamically create a pytest fixture.

    :param name: Name of the fixture.
    :param function: Function to be called.
    :param fixtures: List of fixtures dependencies, but that will not be passed to ``function``.
    :return: The created fixture function.

    Example:

        .. code-block:: python

            book = create_fixture("book", lambda name: Book(name=name), usefixtures=["db"])``

        is equivalent to:

        .. code-block:: python

            @pytest.fixture
            def book(name, db):
                return Book(name=name)
    """
    if fixtures is None:
        fixtures = []

    @pytest.fixture(name=name)
    @usefixtures(*fixtures)
    @functools.wraps(function)
    def fn(*args: P.args, **kwargs: P.kwargs) -> T:
        return function(*args, **kwargs)

    return fn


def usefixtures(*fixtures: str) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Like ``@pytest.mark.usefixtures(...)``, but for fixture functions."""

    def inner(fixture_function: Callable[P, T]) -> Callable[P, T]:
        function_params = list(inspect.signature(fixture_function).parameters.values())
        allowed_param_kinds = {inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY}
        # This is exactly what pytest does (at the moment) to discover which args to inject as fixtures.
        function_args = {
            param.name
            for param in function_params
            if param.kind in allowed_param_kinds
            # Ignoring parameters with a default allows us to use ``functools.partial``s.
            and param.default == inspect.Parameter.empty
        }

        use_fixtures_params = [
            inspect.Parameter(name=name, kind=inspect.Parameter.KEYWORD_ONLY)
            for name in fixtures
            if name not in function_args  # if the name is already in the function signature, don't add it again
        ]
        # If the function ends with **kwargs, we have to insert our params before that.
        if function_params and function_params[-1].kind == inspect.Parameter.VAR_KEYWORD:
            insert_pos = len(function_params) - 1
        else:
            insert_pos = len(function_params)

        params = function_params[0:insert_pos] + use_fixtures_params + function_params[insert_pos:]

        @functools.wraps(fixture_function)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            for k in set(kwargs.keys()) - function_args:
                del kwargs[k]
            return fixture_function(*args, **kwargs)

        wrapper.__signature__ = inspect.signature(wrapper).replace(parameters=params)  # type: ignore[attr-defined]
        return wrapper

    return inner
