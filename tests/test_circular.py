"""Test circular definitions."""

from __future__ import annotations

from dataclasses import dataclass, field

import factory

from pytest_factoryboy import register


@dataclass
class Book:
    """Book model."""

    name: str
    price: float
    author: Author

    def __post_init__(self):
        self.author.books.append(self)


@dataclass
class Author:
    """Author model."""

    name: str
    books: list[Book] = field(default_factory=list, init=False)


class AuthorFactory(factory.Factory):
    class Meta:
        model = Author

    name = "Charles Dickens"

    book = factory.RelatedFactory("tests.test_circular.BookFactory", "author")


class BookFactory(factory.Factory):
    class Meta:
        model = Book

    name = "Alice in Wonderland"
    price = factory.LazyAttribute(lambda f: 3.99)
    author = factory.SubFactory(AuthorFactory)


register(AuthorFactory)
register(BookFactory)


def test_circular(author: Author, factoryboy_request, request):
    assert author.books
