"""pytest-factoryboy public API."""

__version__ = '1.1.0'

from .fixture import register, LazyFixture

__all__ = [
    register.__name__,
    LazyFixture.__name__,
]
