"""pytest-factoryboy public API."""

__version__ = '1.0.3'

try:
    from .fixture import register, LazyFixture

    __all__ = [
        register.__name__,
        LazyFixture.__name__,
    ]
except ImportError:  # pragma: no cover
    # avoid import errors when only __version__ is needed (for setup.py)
    pass
