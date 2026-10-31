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

This module also owns the resolution of shareable sub-factories: registrations record a
per-kind default fixture (:func:`record_default_fixtures`), and ``_generate`` resolves a
bare ``SubFactory`` to it lazily, at call time, when the strategy is ``create``.

The model fixture builds from the original factory instead (see :func:`original_factory`),
bypassing the engine. Later changes manage post-generation deferral here; see
``specs/factory-fixtures.md`` §6/§11.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, Final, Generic, TypeVar, cast
from weakref import WeakKeyDictionary

import factory.enums
from _pytest.fixtures import FixtureLookupError
from factory.declarations import RelatedFactory, SubFactory

if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import Any

    from _pytest.fixtures import SubRequest
    from factory.base import Factory

T = TypeVar("T")

__all__ = (
    "UNSET",
    "Unset",
    "bind_factory",
    "default_fixture",
    "defaults_for",
    "original_factory",
    "record_default_fixtures",
)


class Unset:
    """Type of the :data:`UNSET` sentinel: nothing recorded for this kind."""

    def __repr__(self) -> str:
        return "UNSET"


UNSET: Final = Unset()


@dataclass
class _FactoryDefaults:
    """What the registrations of a factory recorded, per kind.

    A kind is a fixture name (shared), ``None`` (build a new object) or :data:`UNSET`
    (nothing recorded: fall back to the deprecated model-name inflection).
    """

    subfactory: str | None | Unset = UNSET
    relatedfactory: str | None | Unset = UNSET
    model_name: str | None = None


# Keyed by the factory class itself, so a subclass does not inherit the recording of its
# base (which would share the wrong fixture).
_DEFAULTS: WeakKeyDictionary[type[Any], _FactoryDefaults] = WeakKeyDictionary()


def record_default_fixtures(
    factory_class: type[Factory[T]],
    *,
    model_name: str | None = None,
    subfactory: str | None | Unset = UNSET,
    relatedfactory: str | None | Unset = UNSET,
) -> None:
    """Record the default fixtures of a registration.

    Each setting is recorded once — first writer wins — so a later registration of the
    same factory does not change what an earlier one recorded.
    """
    defaults = _DEFAULTS.setdefault(factory_class, _FactoryDefaults())
    if defaults.model_name is None:
        defaults.model_name = model_name
    if isinstance(defaults.subfactory, Unset):
        defaults.subfactory = subfactory
    if isinstance(defaults.relatedfactory, Unset):
        defaults.relatedfactory = relatedfactory


def defaults_for(factory_class: type[Factory[T]]) -> _FactoryDefaults | None:
    """Return what ``factory_class`` recorded, or ``None`` if it is not registered."""
    return _DEFAULTS.get(factory_class)


def recorded_fixture(declaration: SubFactory | RelatedFactory, *, related: bool) -> str | None | Unset:
    """Return the fixture a registration recorded for ``declaration``, without fallback."""
    defaults = _DEFAULTS.get(declaration.get_factory())
    if defaults is None:
        return UNSET
    return defaults.relatedfactory if related else defaults.subfactory


def default_fixture(declaration: SubFactory | RelatedFactory, *, related: bool) -> str | None:
    """Resolve the fixture a declaration shares, or ``None`` to build a new object.

    A recorded setting is used as-is. A target with no recorded setting falls back to
    the deprecated model-name inflection, with a :class:`DeprecationWarning`.
    """
    configured = recorded_fixture(declaration, related=related)
    if not isinstance(configured, Unset):
        return configured
    return fallback_fixture(declaration, related=related)


def fallback_fixture(declaration: SubFactory | RelatedFactory, *, related: bool) -> str:
    """The deprecated model-name inflection of a declaration's target."""
    from .fixture import get_model_name  # local import to avoid an import cycle

    target = declaration.get_factory()
    fallback = get_model_name(target)
    kind = "related" if related else "sub"
    warnings.warn(
        f"{target.__name__} has no default {kind}factory fixture: falling back to the "
        f"{fallback!r} fixture by model-name inflection. Register the factory, or pass "
        f"_default_{kind}factory_fixture=None to build a new object instead. The fallback "
        f"will be removed in a future release.",
        DeprecationWarning,
        stacklevel=3,
    )
    return fallback


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
            shared = _shared_subfactories(cls, request, strategy, overrides)
            shared.update(overrides)
            # ``super()`` is factory_boy's own ``_generate``: nothing re-enters the engine.
            return cast("T", super()._generate(strategy, shared))

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


def _shared_subfactories(
    cls: type[Factory[T]],
    request: SubRequest,
    strategy: str,
    overrides: Mapping[str, object],
) -> dict[str, object]:
    """Resolve bare ``SubFactory`` declarations to the fixture they share.

    Only ``create`` shares: injecting an already-created object into ``build``/``stub``
    would create rows. Resolution happens here, at call time, because the strategy is not
    known when the fixture is set up (see ``specs/factory-fixtures.md`` §4.1).
    """
    if strategy != factory.enums.CREATE_STRATEGY:
        return {}

    declarations = cls._meta.declarations
    shared: dict[str, object] = {}
    for attr in cls._meta.pre_declarations:
        declaration = declarations[attr]
        if attr in overrides or not isinstance(declaration, SubFactory):
            continue
        configured = recorded_fixture(declaration, related=False)
        if configured is None:
            continue
        if isinstance(configured, Unset):
            # Deprecated model-name inflection: share it if such a fixture exists,
            # otherwise build a new object, as factory_boy would.
            try:
                shared[attr] = request.getfixturevalue(fallback_fixture(declaration, related=False))
            except FixtureLookupError:
                continue
        else:
            shared[attr] = request.getfixturevalue(configured)
    return shared
