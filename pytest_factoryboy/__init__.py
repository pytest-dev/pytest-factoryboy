"""pytest-factoryboy public API."""
from .fixture import register, LazyFixture

__version__ = '2.0.0b2'


__all__ = [
    register.__name__,
    LazyFixture.__name__,
]
