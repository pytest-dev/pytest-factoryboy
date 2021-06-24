"""Test circular definitions."""

import factory

from pytest_factoryboy import register


class Book:

    """Book model."""

    def __init__(self, name=None, price=None, author=None):
        self.editions = []
        self.name = name
        self.price = price
        self.author = author
        self.author.books.append(self)


class Author:

    """Author model."""

    def __init__(self, name):
        self.books = []
        self.name = name
        self.user = None


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


def test_circular(author, factoryboy_request, request):
    assert author.books


def test_circular_with_trait(author_book_trait):
    # FIXME: The trait, converted to Maybe, is handled in fixture.make_deferred_postgen
    # which tries to run call() on the Maybe class, which was disabled in factory-boy 3.2
    assert author_book_trait.name == "Charles Dickens"
