"""Tests for the ``_generate`` interception hook (:mod:`pytest_factoryboy.generate`)."""

from __future__ import annotations

from dataclasses import dataclass

import factory
import pytest

from pytest_factoryboy.generate import install_generate_hook


@dataclass
class Author:
    name: str


@dataclass
class Book:
    title: str
    author: Author


class AuthorFactory(factory.Factory):
    class Meta:
        model = Author

    name = "Charles Dickens"


class BookFactory(factory.Factory):
    class Meta:
        model = Book

    title = "Alice in Wonderland"
    author = factory.SubFactory(AuthorFactory)


def _delegate(cls, strategy, params):
    return cls._generate(strategy, params)


def test_returns_a_subclass_without_mutating_the_original() -> None:
    original_generate = AuthorFactory._generate.__func__

    hooked = install_generate_hook(AuthorFactory, _delegate)

    assert hooked is not AuthorFactory
    assert issubclass(hooked, AuthorFactory)
    # Installing a hook must not touch the caller's factory.
    assert AuthorFactory._generate.__func__ is original_generate
    assert AuthorFactory().name == "Charles Dickens"


def test_hook_sees_every_top_level_entry_point() -> None:
    calls: list[str] = []

    def hook(cls, strategy, params):
        calls.append(strategy)
        return cls._generate(strategy, params)

    hooked = install_generate_hook(AuthorFactory, hook)

    assert hooked().name == "Charles Dickens"
    assert hooked.create().name == "Charles Dickens"
    assert hooked.build().name == "Charles Dickens"
    assert hooked.stub() is not None
    assert len(hooked.create_batch(2)) == 2
    assert len(hooked.build_batch(2)) == 2
    assert len(hooked.stub_batch(2)) == 2
    assert hooked.generate("create").name == "Charles Dickens"
    assert hooked.generate("build").name == "Charles Dickens"
    assert hooked.generate("stub") is not None

    assert calls == [
        "create",
        "create",
        "build",
        "stub",
        "create",
        "create",
        "build",
        "build",
        "stub",
        "stub",
        "create",
        "build",
        "stub",
    ]


def test_hook_can_delegate_back_to_factory_boy_without_recursion() -> None:
    calls: list[str] = []

    def hook(cls, strategy, params):
        calls.append(strategy)
        return cls._generate(strategy, params)

    hooked = install_generate_hook(AuthorFactory, hook)

    assert hooked().name == "Charles Dickens"
    # Exactly one hook call: the native delegation did not re-enter the hook.
    assert calls == ["create"]


def test_hook_can_replace_the_result() -> None:
    sentinel = Author(name="Ada")

    hooked = install_generate_hook(AuthorFactory, lambda cls, strategy, params: sentinel)

    assert hooked() is sentinel


def test_hook_receives_strategy_and_params() -> None:
    seen: list[tuple[str, dict[str, object]]] = []

    def hook(cls, strategy, params):
        seen.append((strategy, dict(params)))
        return cls._generate(strategy, params)

    hooked = install_generate_hook(AuthorFactory, hook)
    hooked(name="Ada")

    assert seen == [("create", {"name": "Ada"})]


def test_guard_resets_between_calls() -> None:
    calls: list[str] = []

    def hook(cls, strategy, params):
        calls.append(strategy)
        return cls._generate(strategy, params)

    hooked = install_generate_hook(AuthorFactory, hook)
    hooked()
    hooked()

    assert calls == ["create", "create"]


def test_guard_resets_after_an_exception() -> None:
    calls: list[str] = []

    def hook(cls, strategy, params):
        calls.append(strategy)
        if len(calls) == 1:
            raise RuntimeError("boom")
        return cls._generate(strategy, params)

    hooked = install_generate_hook(AuthorFactory, hook)

    try:
        hooked()
    except RuntimeError:
        pass

    # The guard must not stay set after the hook raised.
    assert hooked().name == "Charles Dickens"
    assert calls == ["create", "create"]


def test_nested_subfactory_is_not_intercepted() -> None:
    calls: list[str] = []

    def hook(cls, strategy, params):
        calls.append(strategy)
        return cls._generate(strategy, params)

    hooked = install_generate_hook(BookFactory, hook)
    book = hooked()

    # Only the top-level Book generation is seen; the nested Author SubFactory recurses
    # through the builder and bypasses ``_generate``.
    assert calls == ["create"]
    assert book.author.name == "Charles Dickens"


def test_independent_hooked_factories_do_not_interfere() -> None:
    book_calls: list[str] = []
    author_calls: list[str] = []

    def author_hook(cls, strategy, params):
        author_calls.append(strategy)
        return cls._generate(strategy, params)

    hooked_author = install_generate_hook(AuthorFactory, author_hook)

    def book_hook(cls, strategy, params):
        book_calls.append(strategy)
        # A top-level generation of a *different* hooked factory must still run its hook.
        hooked_author.create()
        return cls._generate(strategy, params)

    hooked_book = install_generate_hook(BookFactory, book_hook)
    hooked_book()

    assert book_calls == ["create"]
    assert author_calls == ["create"]


def test_subclass_of_a_hooked_class_is_intercepted() -> None:
    seen: list[str] = []

    def hook(cls, strategy, params):
        seen.append(cls.__name__)
        return cls._generate(strategy, params)

    hooked = install_generate_hook(AuthorFactory, hook)

    class Sub(hooked):
        pass

    assert Sub().name == "Charles Dickens"
    # The hook still fires, and sees the *actual* class being generated.
    assert seen == ["Sub"]


def test_stacked_hooks_each_run() -> None:
    inner_calls: list[str] = []
    outer_calls: list[str] = []

    def inner_hook(cls, strategy, params):
        inner_calls.append(strategy)
        return cls._generate(strategy, params)

    def outer_hook(cls, strategy, params):
        outer_calls.append(strategy)
        return cls._generate(strategy, params)

    inner = install_generate_hook(AuthorFactory, inner_hook)
    outer = install_generate_hook(inner, outer_hook)

    assert outer().name == "Charles Dickens"
    # Both hooks run exactly once; the inner one is not swallowed by the outer guard.
    assert inner_calls == ["create"]
    assert outer_calls == ["create"]


def test_user_generate_override_is_reached() -> None:
    seen: list[str] = []

    class CustomFactory(AuthorFactory):
        @classmethod
        def _generate(cls, strategy, params):
            seen.append(strategy)
            return super()._generate(strategy, params)

    hooked = install_generate_hook(CustomFactory, _delegate)
    hooked()

    assert seen == ["create"]


def test_abstract_factory_runs_hook_then_raises() -> None:
    calls: list[str] = []

    class AbstractFactory(factory.Factory):
        class Meta:
            model = Author
            abstract = True

    def hook(cls, strategy, params):
        calls.append(strategy)
        return cls._generate(strategy, params)

    hooked = install_generate_hook(AbstractFactory, hook)

    # The hook runs first; factory_boy's abstract check still raises on delegation.
    with pytest.raises(factory.errors.FactoryError):
        hooked()
    assert calls == ["create"]
