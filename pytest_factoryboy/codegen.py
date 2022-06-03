from __future__ import annotations

import ast
import copy
import functools
import inspect
import logging
import pathlib
import sys
from collections import defaultdict
from dataclasses import dataclass
from types import ModuleType
from typing import TYPE_CHECKING, Callable, Container, TypeVar

if sys.version_info < (3, 9):
    from ast_compat import unparse
else:
    from ast import unparse

from ast import parse

from tokenize_rt import Offset, reversed_enumerate, src_to_tokens, tokens_to_src

if TYPE_CHECKING:
    from typing_extensions import Literal, Self

T = TypeVar("T")

logger = logging.getLogger(__name__)


# copied from pyupgrade:
# https://github.com/asottile/pyupgrade/blob/75f5b9eaf80353346d1ccb36171ff8426307d5fe/pyupgrade/_ast_helpers.py#L21
def is_name_attr(
    node: ast.AST,
    imports: dict[str, set[str]],
    mods: tuple[str, ...],
    names: Container[str],
) -> bool:
    return (isinstance(node, ast.Name) and node.id in names and any(node.id in imports[mod] for mod in mods)) or (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id in mods
        and node.attr in names
    )


def rewrite_register_node(
    node: ast.Call, new_name_param="name", new_factory_kwargs_param="factory_kwargs"
) -> str | None:
    node = copy.deepcopy(node)

    new_node_keywords = []

    # For debugging purposes
    node_str = unparse(node)  # noqa

    kwargs_names = {k.arg for k in node.keywords}

    if new_factory_kwargs_param not in kwargs_names:

        factory_kwargs_keyword = {}

        for kwarg in node.keywords:
            key = kwarg.arg
            value = kwarg.value
            if key == "factory_class":
                continue

            # Fix #1: _name -> name
            if key == "_name":
                name_kwarg = copy.deepcopy(kwarg)
                name_kwarg.arg = new_name_param
                new_node_keywords.append(name_kwarg)
                continue

            # Fix #2: foo=bar, **kwargs -> factory_kwargs={...}
            if key is not None:
                # the argument is a "foo="bar" style keyword argument
                key = ast.Constant(s=key, kind=None)
            # otherwise it's a "**kwargs"

            factory_kwargs_keyword[key] = value

        if factory_kwargs_keyword:
            keys, values = zip(*factory_kwargs_keyword.items())
            factory_kwargs_node = ast.Expr(value=ast.Dict(keys=keys, values=values))
            new_node_keywords.append(ast.keyword(new_factory_kwargs_param, factory_kwargs_node))

    node.keywords = new_node_keywords
    source = unparse(node)
    return source


@dataclass
class DecoratorInfo:
    node: ast.Call
    offset_start: Offset
    offset_end: Offset

    @classmethod
    def from_node(cls, node: ast.Call) -> Self:
        return cls(
            node=node,
            offset_start=Offset(node.lineno, node.col_offset),
            offset_end=Offset(node.end_lineno, node.end_col_offset),
        )


def available_since(version: tuple[int, int]) -> Callable[[T], T]:
    def wrapper(fn: T) -> T:
        @functools.wraps(fn)
        def wrapped(*args, **kwargs):
            if sys.version_info < version:
                raise RuntimeError(f"This feature is only available with python >= {version[0]}.{version[1]}")
            return fn(*args, **kwargs)

        return wrapped

    return wrapper


@available_since(version=(3, 8))
def upgrade_source(source: str, source_filename: str) -> str:
    tree = parse(source, filename=source_filename)
    found: list[DecoratorInfo] = []
    from_imports: dict[str, set] = defaultdict(set)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and not node.level and node.module in ["pytest_factoryboy"]:
            from_imports[node.module].update(name.name for name in node.names if not name.asname)

        elif isinstance(node, ast.Call):
            func = node.func
            if is_name_attr(
                func,
                from_imports,
                ("pytest_factoryboy",),
                ("register",),
            ):
                print(f"Found register call at {node.lineno}:{node.col_offset}. {unparse(node)}")
                found.append(DecoratorInfo.from_node(node))

    found_by_start_offset: dict[Offset, DecoratorInfo] = {dec_info.offset_start: dec_info for dec_info in found}
    tokens = src_to_tokens(source)
    for i, token in reversed_enumerate(tokens):
        dec_info = found_by_start_offset.get(token.offset)
        if dec_info is None:
            continue

        if not token.src:
            # skip possible DEDENT tokens
            continue

        end_token_pos = next(i for i, t in reversed_enumerate(tokens) if t.offset == dec_info.offset_end)
        new_call = rewrite_register_node(dec_info.node)
        if new_call is not None:
            tokens[i:end_token_pos] = [tokens[i]._replace(src=new_call)]
    new_source = tokens_to_src(tokens)
    return new_source


@available_since(version=(3, 8))
@functools.lru_cache()  # So that we rewrite each file only once
def upgrade_module(module: ModuleType) -> None:
    # TODO: Double check that module.__file__ is always accessible. Maybe it wasn't always an absolute path
    # TODO: Handle case where module.__file__ or module.__source__ is not accessible
    source = inspect.getsource(module)
    source_filename = inspect.getsourcefile(module)
    new_source = upgrade_source(source=source, source_filename=source_filename)

    source_file = pathlib.Path(source_filename)
    source_file.write_text(new_source)
    print(f"Rewritten {source_file}")
