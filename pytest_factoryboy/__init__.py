"""pytest-factoryboy public API."""
from .fixture import LazyFixture
from .fixture import register

__version__ = "2.0.3"


__all__ = [
    register.__name__,
    LazyFixture.__name__,
]
