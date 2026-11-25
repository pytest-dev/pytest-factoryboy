"""The generation engine behind the factory fixture.

:func:`bind_factory` returns a subclass of the user's factory bound to the current pytest
request. The subclass overrides ``_generate`` — factory_boy's single funnel for top-level
generation (``__call__``, ``create``, ``build``, ``stub``, the ``*_batch`` helpers and
``generate`` all route through it) — to merge the factory namespace
(``foo_factory__<attr>`` fixtures) with the per-call parameters, and then delegates to
factory_boy. Nested builds (a ``SubFactory`` recursing through the builder) bypass the
override by design.

The request and the factory fixture name are captured by that method's closure, so they
are reachable only through the returned class — the fixture value — and never stored in a
module-global structure.

The model fixture builds from the original factory instead (see :func:`original_factory`),
bypassing the engine. Later changes resolve shareable sub-factories and manage
post-generation deferral here; see ``specs/factory-fixtures.md`` §6/§11.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Generic, TypeVar, cast

if TYPE_CHECKING:
    from collections.abc import Mapping

    from _pytest.fixtures import SubRequest
    from factory.base import Factory

T = TypeVar("T")

__all__ = ("bind_factory", "original_factory")


class _BoundFactory(Generic[T]):
    """Declares the factory a bound subclass wraps.

    The base of the class returned by :func:`bind_factory`: declaring the attribute
    (rather than checking for it at runtime) is what makes :func:`original_factory` a
    checked, cast-free read.
    """

    _factoryboy_original_factory: ClassVar[type[Factory[T]]]


def bind_factory(
    factory_class: type[Factory[T]],
    request: SubRequest,
    factory_name: str,
) -> type[Factory[T]]:
    """Return a subclass of ``factory_class`` bound to the current pytest request.

    The returned class routes ``_generate`` through the engine and delegates to
    factory_boy's own generation. The request and the factory fixture name are captured by
    that method's closure, so they live exactly as long as the returned class — the
    fixture value — and are not kept in any module-global structure.

    :param factory_class: The user's factory.
    :param request: The pytest request to bind (used to resolve fixtures).
    :param factory_name: The factory fixture name, used to resolve ``foo_factory__<attr>``.
    :return: A subclass of ``factory_class`` whose ``_generate`` goes through the engine.
    """

    class Bound(factory_class, _BoundFactory[T]):  # type: ignore[valid-type, misc]
        # The factory this subclass wraps; ``_BoundFactory`` declares it, so callers can
        # read it back with typing — see :func:`original_factory`.
        _factoryboy_original_factory = factory_class

        @classmethod
        def _generate(cls, strategy: str, params: Mapping[str, object]) -> T:
            overrides = _factory_namespace_overrides(cls, request, factory_name)
            overrides.update(params)
            # ``super()`` is factory_boy's own ``_generate``: nothing re-enters the engine.
            return cast("T", super()._generate(strategy, overrides))

    Bound.__name__ = factory_class.__name__
    Bound.__qualname__ = factory_class.__qualname__
    Bound.__module__ = factory_class.__module__
    Bound.__doc__ = factory_class.__doc__
    # Subclassing normally makes a factory concrete; keep the base's abstractness so an
    # abstract factory cannot start generating just because it is bound to a request.
    Bound._meta.abstract = factory_class._meta.abstract
    return Bound


def original_factory(factory_class: type[Factory[T]]) -> type[Factory[T]]:
    """Return the factory a bound subclass wraps, or ``factory_class`` itself.

    Lets callers unwrap unconditionally: a class that is not bound is returned unchanged.
    """
    if issubclass(factory_class, _BoundFactory):
        return factory_class._factoryboy_original_factory
    return factory_class


def _factory_namespace_overrides(
    cls: type[Factory[T]],
    request: SubRequest,
    factory_name: str,
) -> dict[str, object]:
    """Collect the factory namespace values that were explicitly set.

    A ``foo_factory__<attr>`` fixture returns the factory's own declaration when it was
    not overridden, which is skipped so factory_boy evaluates the declaration natively.
    """
    from .fixture import evaluate  # local import to avoid an import cycle

    declarations = cls._meta.declarations
    overrides: dict[str, object] = {}
    for attr in cls._meta.pre_declarations:
        declaration = declarations[attr]
        value = evaluate(request, request.getfixturevalue(f"{factory_name}__{attr}"))
        if value is not declaration:
            overrides[attr] = value
    return overrides
