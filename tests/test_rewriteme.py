import importlib
import inspect

from pytest_factoryboy.codegen import upgrade_source


def test_rewrite_me():
    m = importlib.import_module("tests.rewriteme")
    source = inspect.getsource(m)
    output = upgrade_source(source, source_filename=m.__file__)
    assert (
        output
        == """\
import factory

from pytest_factoryboy import register


class Author:
    def __init__(self, name, last_name):
        self.name = name
        self.last_name = last_name


@register
@register(name="second_author_explicit_name_decorator")
@register(factory_kwargs={"last_name": "Dickens as kwargs"})
class AuthorFactory(factory.Factory):
    class Meta:
        model = Author

    name = "Charles"
    last_name = "Dickens"


register(AuthorFactory, "third_author", factory_kwargs={"last_name": "Dickens as kwargs"})
register(AuthorFactory, name="author_explicit_name_call")
register(AuthorFactory, "partial_author", factory_kwargs{"name": "John Doe"})
"""
    )
