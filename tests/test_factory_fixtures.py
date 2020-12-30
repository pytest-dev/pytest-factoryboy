"""Factory fixtures tests."""

import factory
from factory import fuzzy
import pytest

from pytest_factoryboy import register, LazyFixture


class User:
    """User account."""

    def __init__(self, username, password, is_active):
        self.username = username
        self.password = password
        self.is_active = is_active


class Book:
    """Book model."""

    def __init__(self, name=None, price=None, author=None):
        self.editions = []
        self.name = name
        self.price = price
        self.author = author


class Author:
    """Author model."""

    def __init__(self, name):
        self.name = name
        self.user = None


class Edition:
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

    register_user__is_active = True  # Make sure fixture is generated
    register_user__password = "qwerty"  # Make sure fixture is generated

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
    book_edition = factory.RelatedFactory("tests.test_factory_fixtures.EditionFactory", "book")


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
    assert author.user.is_active is True


register(AuthorFactory, "second_author")


@pytest.mark.parametrize("second_author__name", ["Mr. Hyde"])
def test_second_author(author, second_author):
    """Test factory registration with specific name."""
    assert author != second_author
    assert second_author.name == "Mr. Hyde"


register(AuthorFactory, "partial_author", name="John Doe", register_user=LazyFixture(lambda: "jd@jd.com"))


def test_partial(partial_author):
    """Test fixture partial specialization."""
    assert partial_author.name == "John Doe"
    assert partial_author.user.username == "jd@jd.com"


register(AuthorFactory, "another_author", name=LazyFixture(lambda: "Another Author"))


@pytest.mark.parametrize("book__author", [LazyFixture("another_author")])
def test_lazy_fixture_name(book, another_author):
    """Test that book author is replaced with another author by fixture name."""
    assert book.author == another_author
    assert book.author.name == "Another Author"


@pytest.mark.parametrize("book__author", [LazyFixture(lambda another_author: another_author)])
def test_lazy_fixture_callable(book, another_author):
    """Test that book author is replaced with another author by callable."""
    assert book.author == another_author
    assert book.author.name == "Another Author"


@pytest.mark.parametrize(
    ("author__register_user", "author__register_user__password"),
    [
        (LazyFixture(lambda: "lazyfixture"), LazyFixture(lambda: "asdasd")),
    ],
)
def test_lazy_fixture_post_generation(author):
    """Test that post-generation values are replaced with lazy fixtures."""
    # assert author.user.username == "lazyfixture"
    assert author.user.password == "asdasd"
