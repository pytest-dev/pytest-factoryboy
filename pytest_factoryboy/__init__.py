"""pytest-factoryboy public API."""

import warnings

__version__ = '1.1.0'

try:
    from .fixture import register, LazyFixture

    __all__ = [
        register.__name__,
        LazyFixture.__name__,
    ]
except Exception, e:  # pragma: no cover
    warnings.warn(e)
