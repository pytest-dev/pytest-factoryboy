from __future__ import annotations

import inspect
from typing import Any, Callable, TypeVar

import pytest

T = TypeVar("T")


def create_fixture(
    name: str,
    function: Callable[..., T],  # TODO: Try to use ParamSpec instead of Callable
    usefixtures: list[str] | None = None,
) -> Callable[..., T]:
    """Dynamically create a pytest fixture.

    :param name: Name of the fixture.
    :param function: Function to be called.
    :param usefixtures: List of fixtures requested, but that will not be passed to ``function``.
                        Think about it like a ``@pytest.mark.usefixtures(...)`` for fixture functions.
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
    if usefixtures is None:
        usefixtures = []

    function_params = list(inspect.signature(function).parameters.values())
    allowed_param_kinds = {inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY}

    # This is exactly what pytest does (at the moment) to discover which args to inject as fixtures.
    # Ignoring parameters with a default allows us to use ``functools.partial``s.
    function_args = [
        param.name
        for param in function_params
        if param.kind in allowed_param_kinds and param.default == inspect.Parameter.empty
    ]

    def fn(**kwargs: Any) -> T:
        function_kwargs = {k: kwargs[k] for k in function_args}
        return function(**function_kwargs)

    if usefixtures:
        use_fixtures_params = [
            inspect.Parameter(name=name, kind=inspect.Parameter.KEYWORD_ONLY) for name in usefixtures
        ]
        # If the function ends with **kwargs, we have to insert our params before that.
        if function_params and function_params[-1].kind == inspect.Parameter.VAR_KEYWORD:
            insert_pos = len(function_params) - 1
        else:
            insert_pos = len(function_params)

        params = function_params[0:insert_pos] + use_fixtures_params + function_params[insert_pos:]
    else:
        params = function_params

    fn.__signature__ = inspect.signature(fn).replace(parameters=params)  # type: ignore[attr-defined]

    fix = pytest.fixture(name=name)(fn)
    return fix
