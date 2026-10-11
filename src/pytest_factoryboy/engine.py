"""The generation engine behind the factory fixture.

:func:`bind_factory` returns a per-request subclass of the user's factory. The subclass
records the factory it wraps (see :func:`original_factory`), so the model fixture can
build from the original factory instead of the bound subclass.

The next change installs the engine itself on that subclass: overriding ``_generate`` —
factory_boy's single funnel for top-level generation — to merge the factory namespace
(``foo_factory__<attr>``) with the per-call parameters. See
``specs/factory-fixtures.md`` §6/§11.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Protocol, TypeVar, cast

if TYPE_CHECKING:
    from factory.base import Factory

T = TypeVar("T")

__all__ = ("bind_factory", "original_factory")


def bind_factory(factory_class: type[Factory[T]]) -> type[Factory[T]]:
    """Return a subclass of ``factory_class`` for the factory fixture.

    The fixture is function-scoped, so the subclass is created per request.

    :param factory_class: The user's factory.
    :return: A subclass of ``factory_class``.
    """

    class Bound(factory_class):  # type: ignore[valid-type, misc]
        # The factory this subclass wraps. Declared (not just assigned) so callers can read
        # it back with typing — see :func:`original_factory`.
        _factoryboy_original_factory: ClassVar[type[Factory[T]]] = factory_class

    Bound.__name__ = factory_class.__name__
    Bound.__qualname__ = factory_class.__qualname__
    Bound.__module__ = factory_class.__module__
    Bound.__doc__ = factory_class.__doc__
    # Subclassing normally makes a factory concrete; keep the base's abstractness so an
    # abstract factory cannot start generating just because it is bound to a request.
    Bound._meta.abstract = factory_class._meta.abstract
    return Bound


class _BoundFactory(Protocol[T]):
    """A factory class returned by :func:`bind_factory`."""

    _factoryboy_original_factory: ClassVar[type[Factory[T]]]


def original_factory(factory_class: type[Factory[T]]) -> type[Factory[T]]:
    """Return the factory a bound subclass wraps, or ``factory_class`` itself.

    Lets callers unwrap unconditionally: a class that is not bound is returned unchanged.
    """
    if hasattr(factory_class, "_factoryboy_original_factory"):
        return cast("type[_BoundFactory[T]]", factory_class)._factoryboy_original_factory
    return factory_class
