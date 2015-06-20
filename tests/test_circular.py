"""Test circular definitions."""

import factory

from pytest_factoryboy import register


class Book(object):

    """Book model."""

    def __init__(self, name=None, price=None, author=None):
        self.editions = []
        self.name = name
        self.price = price
        self.author = author
        self.author.books.append(self)


class Author(object):

    """Author model."""

    def __init__(self, name):
        self.books = []
        self.name = name
        self.user = None


class AuthorFactory(factory.Factory):

    class Meta:
        model = Author

    name = "Charles Dickens"

    book = factory.RelatedFactory('tests.test_circular.BookFactory', 'author')


class BookFactory(factory.Factory):

    class Meta:
        model = Book

    name = "Alice in Wonderland"
    price = factory.LazyAttribute(lambda f: 3.99)
    author = factory.SubFactory(AuthorFactory)


register(AuthorFactory)
register(BookFactory)


def test_circular(author):
    assert author.books
