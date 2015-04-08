"""Factory fixtures tests."""
import factory
import pytest

from pytest_factoryboy import register


class Book(object):

    """Book model."""

    editions = []

    def __init__(self, name=None, price=None, author=None):
        self.name = name
        self.price = price
        self.author = author


class Author(object):

    """Author model."""

    def __init__(self, name):
        self.name = name


class Edition(object):

    """Book edition."""

    def __init__(self, book, year):
        self.book = book
        self.year = year
        book.editions.append(self)


@register
class AuthorFactory(factory.Factory):

    """Author factory."""

    class Meta:
        model = Author

    name = "Charles Dickens"


class BookFactory(factory.Factory):

    """Test factory with all the features."""

    class Meta:
        model = Book

    name = "Alice in Wonderland"
    price = factory.LazyAttribute(lambda f: 3.99)
    author = factory.SubFactory(AuthorFactory)
    edition = factory.RelatedFactory("tests.test_factory_fixtures.EditionFactory", "book")


class EditionFactory(factory.Factory):

    """Book edition factory."""

    class Meta:
        model = Edition

    book = factory.SubFactory(BookFactory)
    year = 1999


register(BookFactory)
register(EditionFactory)


def test_factory(book_factory):
    """Test model factory fixture."""
    assert book_factory == BookFactory


@pytest.mark.xfail
def test_model(book):
    """Test model fixture."""
    assert book.name == "Alice in Wonderland"
    assert book.price == 3.99
    assert book.author.name == "Charles Dickens"
    assert book.editions[0].year == 1999
    assert book.editions[0].book == book


def test_attr(book__name, book__price, author__name, edition__year):
    """Test attribute fixtures.

    :note: Most of the attributes are lazy definitions. Use attribute fixtures in
           order to override the initial values.
    """
    assert book__name == "Alice in Wonderland"
    assert book__price == BookFactory.price
    assert author__name == "Charles Dickens"
    assert edition__year == 1999


@pytest.mark.parametrize("book__name", ["PyTest for Dummies"])
@pytest.mark.parametrize("book__price", [1.0])
@pytest.mark.parametrize("author__name", ["Bill Gates"])
@pytest.mark.parametrize("edition__year", [2000])
@pytest.mark.xfail
def test_parametrized(book):
    """Test model factory fixture."""
    assert book.name == "PyTest for Dummies"
    assert book.price == 1.0
    assert book.author.name == "Bill Gates"
    assert len(book.editions) == 1
    assert book.editions[0].year == 2000
