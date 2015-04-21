"""Factory fixtures tests."""

import factory
from factory import fuzzy
import pytest

from pytest_factoryboy import register


class User(object):

    """User account."""

    def __init__(self, username, password):
        self.username = username
        self.password = password


class Book(object):

    """Book model."""

    def __init__(self, name=None, price=None, author=None):
        self.editions = []
        self.name = name
        self.price = price
        self.author = author


class Author(object):

    """Author model."""

    def __init__(self, name):
        self.name = name
        self.user = None


class Edition(object):

    """Book edition."""

    def __init__(self, book, year):
        self.book = book
        self.year = year
        book.editions.append(self)


class UserFactory(factory.Factory):

    """User factory."""

    class Meta:
        model = User

    password = fuzzy.FuzzyText(length=7)


@register
class AuthorFactory(factory.Factory):

    """Author factory."""

    class Meta:
        model = Author

    name = "Charles Dickens"

    @factory.post_generation
    def register_user(author, create, username, **kwargs):
        """Register author as a user in the system."""
        if username is not None:
            author.user = UserFactory(username=username, **kwargs)


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


def test_model(book):
    """Test model fixture."""
    assert book.name == "Alice in Wonderland"
    assert book.price == 3.99
    assert book.author.name == "Charles Dickens"
    assert book.author.user is None
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
def test_parametrized(book):
    """Test model factory fixture."""
    assert book.name == "PyTest for Dummies"
    assert book.price == 1.0
    assert book.author.name == "Bill Gates"
    assert len(book.editions) == 1
    assert book.editions[0].year == 2000


@pytest.mark.parametrize("author__register_user", ["admin"])
def test_post_generation(author):
    """Test post generation declaration."""
    assert author.user.username == "admin"


register(AuthorFactory, name="second_author")


@pytest.mark.parametrize("second_author__name", ["Mr. Hyde"])
def test_second_author(author, second_author):
    """Test factory registration with specific name."""
    assert author != second_author
    assert second_author.name == "Mr. Hyde"
