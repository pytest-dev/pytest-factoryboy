import factory

from pytest_factoryboy import register


class Author:
    def __init__(self, name, last_name):
        self.name = name
        self.last_name = last_name


@register
@register(_name="second_author_explicit_name_decorator")
@register(last_name="Dickens as kwargs")
class AuthorFactory(factory.Factory):
    class Meta:
        model = Author

    name = "Charles"
    last_name = "Dickens"


register(AuthorFactory, "third_author", last_name="Dickens as kwargs")
register(AuthorFactory, _name="author_explicit_name_call")
register(AuthorFactory, "partial_author", name="John Doe")


def test_normal(author):
    assert author.name == "Charles"


def test_alt_name(second_author_explicit_name_decorator):
    assert second_author_explicit_name_decorator.name == "Charles"


def test_last_name(author):
    assert author.last_name == "Dickens"


def test_third_author(third_author):
    assert third_author.last_name == "Dickens as kwargs"


def test_author_explicit_name_call(author_explicit_name_call):
    assert author_explicit_name_call.name == "Charles"


def test_partial_author(partial_author):
    assert partial_author.name == "John Doe"
