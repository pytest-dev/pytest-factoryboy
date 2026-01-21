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


class AuthorBookTraitFactory(factory.Factory):
    class Meta:
        model = Author

    name = "Charles Dickens"

    class Params:
        with_book = factory.Trait(book=factory.RelatedFactory("tests.test_circular.BookFactory", "author"))


class BookFactory(factory.Factory):
    class Meta:
        model = Book

    name = "Alice in Wonderland"
    price = factory.LazyAttribute(lambda f: 3.99)
    author = factory.SubFactory(AuthorFactory)


register(AuthorFactory)
register(AuthorBookTraitFactory, "author_book_trait")
register(BookFactory)


def test_circular(author: Author, factoryboy_request, request):
    assert author.books


def test_circular_with_trait(author_book_trait):
    # FIXME: The trait, converted to Maybe, is handled in fixture.make_deferred_postgen
    # which tries to run call() on the Maybe class, which was disabled in factory-boy 3.2
    assert author_book_trait.name == "Charles Dickens"
