"""pytest-factoryboy public API."""
from .fixture import LazyFixture, register

# TODO: Remove this, it's managed by poetry
__version__ = "2.4.0"


__all__ = ("register", "LazyFixture")
