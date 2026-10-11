"""Re-entrancy-guarded interception of factory_boy's ``_generate``.

Every *top-level* generation entry point (``Factory.__call__``, ``create``, ``build``,
``stub``, ``create_batch``, ``build_batch``, ``stub_batch``, ``generate``) funnels through
``factory.base.BaseFactory._generate``. :func:`install_generate_hook` returns a subclass of
a factory whose ``_generate`` is routed through a hook, together with a re-entrancy guard
that lets the hook delegate back to factory_boy's own generation.

Nested builds are **not** intercepted: a ``SubFactory`` recurses through
``factory.builder.BuildStep.recurse`` → ``builder.build()`` directly, bypassing
``_generate``.

This is the interception point the factory-fixture engine builds on; see
``specs/factory-fixtures.md`` §6.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from contextvars import ContextVar
from typing import TypeVar, cast

from factory.base import Factory

T = TypeVar("T")

__all__ = ("install_generate_hook",)

# The set of hooked installations currently running their hook on this call stack. An
# installation in the set is being generated *by* its own hook, so ``_generate`` must
# fall through to factory_boy instead of re-entering the hook. A ``ContextVar`` keeps
# this correct across threads and async tasks.
_generate_guard: ContextVar[frozenset[object]] = ContextVar("pytest_factoryboy_generate_guard", default=frozenset())


def install_generate_hook(
    factory_class: type[Factory[T]],
    hook: Callable[[type[Factory[T]], str, Mapping[str, object]], T],
) -> type[Factory[T]]:
    """Return a subclass of ``factory_class`` that routes ``_generate`` through ``hook``.

    ``hook`` is called as ``hook(cls, strategy, params)`` for every top-level generation.
    Inside it, calling ``cls._generate(strategy, params)`` runs factory_boy's own
    generation — the guard keeps that from re-entering ``hook`` — so the hook decides
    *whether* and *how* to build.

    A new subclass is returned, so installing a hook never mutates ``factory_class``.

    :param factory_class: Factory to intercept.
    :param hook: Callable invoked for every top-level generation of the returned subclass.
    :return: A subclass of ``factory_class`` whose ``_generate`` goes through ``hook``.
    """

    # A unique, hashable token identifying this installation. Keying the guard on it (not
    # on ``cls``) means a hooked class can be subclassed and hooks can be stacked without
    # one installation's guard swallowing another's hook.
    key = object()

    class Hooked(factory_class):  # type: ignore[valid-type, misc]
        @classmethod
        def _generate(cls, strategy: str, params: Mapping[str, object]) -> T:
            if key in _generate_guard.get():
                # We are inside ``hook`` for this installation: run factory_boy's
                # generation instead of re-entering the hook.
                return cast("T", super()._generate(strategy, params))
            token = _generate_guard.set(_generate_guard.get() | {key})
            try:
                return hook(cls, strategy, params)
            finally:
                _generate_guard.reset(token)

    Hooked.__name__ = factory_class.__name__
    Hooked.__qualname__ = factory_class.__qualname__
    # Subclassing normally makes a factory concrete; keep the base's abstractness so an
    # abstract factory cannot start generating just because a hook was installed.
    Hooked._meta.abstract = factory_class._meta.abstract
    return Hooked
