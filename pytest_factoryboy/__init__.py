"""pytest-factoryboy public API."""

__version__ = '1.1.0'

try:
    from .fixture import register, LazyFixture

    __all__ = [
        register.__name__,
        LazyFixture.__name__,
    ]
except:  # pragma: no cover
    # We need to catch all exceptions because of factoryboy that uses django when it is not yet configured.
    # Also avoid import errors when only __version__ is needed (for setup.py)
    pass
