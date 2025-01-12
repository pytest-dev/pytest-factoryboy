# TODO: Improve tests
# TODO: Change test module

from dataclasses import dataclass

import factory
import pytest

from pytest_factoryboy import register


@dataclass
class Book:
    name: str


@register
class BookFactory(factory.Factory):
    class Meta:
        model = Book

    name = "foo"


@pytest.mark.parametrize("book__name", ["bar"])
def test_book_initialise_later(book_factory, book__name, book):
    assert book.name == "bar"

    book_f = book_factory()
    assert book_f.name == "bar"
