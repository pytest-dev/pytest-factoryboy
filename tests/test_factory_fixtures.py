"""Factory fixtures tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import factory
import pytest
from factory import fuzzy

from pytest_factoryboy import LazyFixture, register

if TYPE_CHECKING:
    from typing import Any

    from factory.declarations import LazyAttribute


@dataclass
class User:
    """User account."""

    username: str
    password: str
    is_active: bool


@dataclass
class Book:
    """Book model."""

    name: str
    price: float
    author: Author
    editions: list[Edition] = field(default_factory=list, init=False)


@dataclass
class Author:
    """Author model."""

    name: str
    user: User | None = field(init=False, default=None)


@dataclass
class Edition:
    """Book edition."""

    book: Book
    year: int

    def __post_init__(self) -> None:
        self.book.editions.append(self)


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
    def register_user(author: Author, create: bool, username: str | None, **kwargs: Any) -> None:
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


def test_factory(book_factory) -> None:
    """Test model factory fixture."""
    assert book_factory == BookFactory


def test_model(book: Book):
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
def test_parametrized(book: Book):
    """Test model factory fixture."""
    assert book.name == "PyTest for Dummies"
    assert book.price == 1.0
    assert book.author.name == "Bill Gates"
    assert len(book.editions) == 1
    assert book.editions[0].year == 2000


@pytest.mark.parametrize("author__register_user", ["admin"])
def test_post_generation(author: Author):
    """Test post generation declaration."""
    assert author.user
    assert author.user.username == "admin"
    assert author.user.is_active is True


class TestParametrizeAlternativeNameFixture:
    register(AuthorFactory, "second_author")

    @pytest.mark.parametrize("second_author__name", ["Mr. Hyde"])
    def test_second_author(self, author: Author, second_author: Author):
        """Test parametrization of attributes for fixture registered under a different name
        ("second_author")."""
        assert author != second_author
        assert second_author.name == "Mr. Hyde"


class TestPartialSpecialization:
    register(AuthorFactory, "partial_author", name="John Doe", register_user=LazyFixture(lambda: "jd@jd.com"))

    def test_partial(self, partial_author: Author):
        """Test fixture partial specialization."""
        assert partial_author.name == "John Doe"
        assert partial_author.user  # Makes mypy happy
        assert partial_author.user.username == "jd@jd.com"


class TestLazyFixture:
    register(AuthorFactory, "another_author", name=LazyFixture(lambda: "Another Author"))
    register(BookFactory, "another_book", author=LazyFixture("another_author"))

    @pytest.mark.parametrize("book__author", [LazyFixture("another_author")])
    def test_lazy_fixture_name(self, book: Book, another_author: Author):
        """Test that book author is replaced with another author by fixture name."""
        assert book.author == another_author
        assert book.author.name == "Another Author"

    @pytest.mark.parametrize("book__author", [LazyFixture(lambda another_author: another_author)])
    def test_lazy_fixture_callable(self, book: Book, another_author: Author) -> None:
        """Test that book author is replaced with another author by callable."""
        assert book.author == another_author
        assert book.author.name == "Another Author"

    @pytest.mark.parametrize(
        ("author__register_user", "author__register_user__password"),
        [
            (LazyFixture(lambda: "lazyfixture"), LazyFixture(lambda: "asdasd")),
        ],
    )
    def test_lazy_fixture_post_generation(self, author: Author):
        """Test that post-generation values are replaced with lazy fixtures."""
        assert author.user
        assert author.user.username == "lazyfixture"
        assert author.user.password == "asdasd"

    def test_override_subfactory_with_lazy_fixture(self, another_book: Book):
        """Ensure subfactory fixture can be overriden with ``LazyFixture``.

        Issue: https://github.com/pytest-dev/pytest-factoryboy/issues/158

        """
        assert another_book.author.name == "Another Author"


class TestDeferredEvaluation:
    @pytest.mark.parametrize("book__name", ["bar"])
    def test_book_initialise_later(self, book_factory, book):
        assert book.name == "bar"

        book_f = book_factory()
        assert book_f.name == "bar"
