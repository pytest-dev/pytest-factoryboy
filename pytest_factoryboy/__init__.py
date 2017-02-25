"""pytest-factoryboy public API."""
from .fixture import register, LazyFixture

__version__ = '1.3.1'


__all__ = [
    register.__name__,
    LazyFixture.__name__,
]
