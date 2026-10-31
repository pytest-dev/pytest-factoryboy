"""Factory fixtures tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import factory
import pytest
from factory import fuzzy

from pytest_factoryboy import LazyFixture, register, register_factory
from pytest_factoryboy.engine import original_factory

if TYPE_CHECKING:
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
    def register_user(author: Author, create: bool, username: str | None, **kwargs: object) -> None:
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


@dataclass
class Lazy:
    name: str


_lazy_calls: list[str] = []


def _lazy_name() -> str:
    _lazy_calls.append("called")
    return "lazy name"


class LazyFactory(factory.Factory):
    class Meta:
        model = Lazy

    name = "lazy"


register_factory(LazyFactory, name=LazyFixture(_lazy_name))
register(LazyFactory)


@pytest.fixture
def lazy_calls():
    _lazy_calls.clear()
    return _lazy_calls


def test_factory(book_factory) -> None:
    """Test model factory fixture."""
    # The factory fixture is a request-bound subclass of the user's factory, not the
    # factory itself (see specs/factory-fixtures.md §6).
    assert book_factory is not BookFactory
    assert issubclass(book_factory, BookFactory)
    assert original_factory(book_factory) is BookFactory
    # The engine's ``_generate`` override is installed on the bound subclass.
    assert book_factory._generate.__func__ is not BookFactory._generate.__func__
    # Identity metadata is copied so reprs/docs look like the user's factory.
    assert book_factory.__module__ == BookFactory.__module__
    assert book_factory.__doc__ == BookFactory.__doc__


def test_model_fixture_bypasses_the_engine(lazy_calls, lazy) -> None:
    """The model fixture builds from the original factory, bypassing the engine.

    ``lazy__name`` defaults to the factory namespace, so the lazy callable must run once:
    the model fixture resolves it, and the engine (which would resolve it again) is not
    entered.
    """
    assert lazy.name == "lazy name"
    assert lazy_calls == ["called"]


def test_factory_call(book_factory) -> None:
    """Calling the factory fixture creates an instance through the engine."""
    book = book_factory()
    assert isinstance(book, Book)
    assert book.name == "Alice in Wonderland"
    assert book.author.name == "Charles Dickens"


def test_factory_call_evaluates_the_lazy_fixture_once(lazy_calls, lazy_factory) -> None:
    assert lazy_factory().name == "lazy name"
    assert lazy_calls == ["called"]


def test_factory_call_creates_distinct_instances(book_factory) -> None:
    assert book_factory() is not book_factory()


def test_factory_call_shares_the_registered_subfactory(book, author, book_factory) -> None:
    """A bare ``SubFactory`` to a registered factory shares its fixture (§4.1)."""
    assert book_factory().author is book.author is author


def test_factory_call_shares_one_subfactory_between_calls(book_factory) -> None:
    first, second = book_factory(), book_factory()

    assert first is not second
    assert first.author is second.author


def test_factory_build_does_not_share(book_factory, author) -> None:
    """Only ``create`` shares; ``build``/``stub`` must not inject a created object."""
    assert book_factory.build().author is not author
    assert book_factory.stub().author is not author


@pytest.mark.parametrize("author__name", ["Grace Hopper"])
def test_shared_subfactory_parametrization(book_factory, request) -> None:
    """``author__name`` parametrizes a shared target, without requesting ``author``."""
    book = book_factory()

    assert book.author.name == "Grace Hopper"
    assert book.author is request.getfixturevalue("author")


@pytest.mark.parametrize("author_factory__name", ["Grace Hopper"])
def test_shared_subfactory_factory_namespace_parametrization(book_factory, request) -> None:
    """The target's factory namespace parametrizes the shared target as well."""
    book = book_factory()

    assert book.author.name == "Grace Hopper"
    assert book.author is request.getfixturevalue("author")


@pytest.mark.parametrize("author__name", ["Grace Hopper"])
def test_shared_subfactory_parametrization_does_not_leak_into_build(book_factory) -> None:
    assert book_factory.build().author.name == "Charles Dickens"


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
