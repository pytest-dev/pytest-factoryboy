import sys

if sys.version_info < (3, 9):
    from ast_compat import unparse
else:
    from ast import unparse

import re
from ast import parse

import pytest

from pytest_factoryboy.codegen import upgrade_source

PREFIX = "from pytest_factoryboy import register\n"


@pytest.mark.parametrize(
    ["src", "expected"],
    [
        ('register(F, _name="second_foo")', 'register(F, name="second_foo")'),
        ("register(F, _name='second_foo')", "register(F, name='second_foo')"),
        ('register(F, foo="v")', 'register(F, factory_kwargs={"foo": "v"})'),
        ('register(F, "second_foo", name="bar")', 'register(F, "second_foo", factory_kwargs={"name": "bar"})'),
        (
            'register(F, foo3="c", foo2="b", foo1="a")',
            'register(F, factory_kwargs={"foo3": "c", "foo2": "b", "foo1": "a"})',
        ),
        ('register(F, foo="v", **myargs)', 'register(F, factory_kwargs={"foo": "v", **myargs})'),
        ('register(F, "f", foo="v", **myargs)', 'register(F, "f", factory_kwargs={"foo": "v", **myargs})'),
        ('register(F, _name="f", foo="v", **myargs)', 'register(F, name="f", factory_kwargs={"foo": "v", **myargs})'),
        ('register(F, foo="v", **myargs, _name="f")', 'register(F, name="f", factory_kwargs={"foo": "v", **myargs})'),
    ],
)
def test_upgrade_source(src, expected):
    src = PREFIX + src
    rewritten = upgrade_source(src, "<file>")

    rewritten = re.sub(r"^" + re.escape(PREFIX), "", rewritten)
    # assert rewritten == expected  # TODO: enable this when we handle output correctly

    source_ast = parse(rewritten)
    expected_ast = parse(expected)
    source_ast_out = unparse(source_ast)
    expected_ast_out = unparse(expected_ast)
    assert source_ast_out == expected_ast_out
