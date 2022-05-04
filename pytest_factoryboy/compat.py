from __future__ import annotations

import pathlib
import sys

__all__ = ("PostGenerationContext", "path_with_stem")

try:
    from factory.declarations import PostGenerationContext
except ImportError:  # factory_boy < 3.2.0
    from factory.builder import PostGenerationContext

if sys.version_info >= (3, 9):

    def path_with_stem(path: pathlib.Path, stem: str) -> pathlib.Path:
        return path.with_stem(stem)

else:

    def path_with_stem(path: pathlib.Path, stem: str) -> pathlib.Path:
        return path.with_name(stem + path.suffix)
