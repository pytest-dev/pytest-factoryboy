factory_boy_ integration with the pytest_ runner
================================================

.. image:: https://api.travis-ci.org/pytest-dev/pytest-factoryboy.png
   :target: https://travis-ci.org/pytest-dev/pytest-factoryboy
.. image:: https://pypip.in/v/pytest-factoryboy/badge.png
   :target: https://crate.io/packages/pytest-factoryboy/
.. image:: https://readthedocs.org/projects/pytest-factoryboy/badge/?version=latest
    :target: https://readthedocs.org/projects/pytest-factoryboy/?badge=latest
    :alt: Documentation Status

pytest-factoryboy makes it easy to combine ``factory`` approach to the test setup with the ``dependency`` injection,
heart of the `pytest fixtures`_.

.. _factory_boy: http://factoryboy.readthedocs.org
.. _pytest: http://pytest.org
.. _pytest fixtures: https://pytest.org/latest/fixture.html
.. _overridden: http://pytest.org/latest/fixture.html#override-a-fixture-with-direct-test-parametrization


Install pytest-factoryboy
-------------------------

::

    pip install pytest-factoryboy


Concept
-------

Library exports a function to register factories as fixtures. Fixtures are contributed
to the same module where register function is called.

Factory Fixture
---------------

Factory fixtures allow using factories without importing them. Name convention is lowercase-underscore
class name.

.. code-block:: python

    import factory
    from pytest_factoryboy import register

    class AuthorFactory(factory.Factory):

        class Meta:
            model = Author


    register(AuthorFactory)


    def test_factory_fixture(author_factory):
        author = author_factory(name="Charles Dickens")
        assert author.name == "Charles Dickens"


Model Fixture
-------------

Model fixture implements an instance of a model created by the factory. Name convention is lowercase-underscore
class name.


.. code-block:: python

    import factory
    from pytest_factoryboy import register

    @register
    class AuthorFactory(Factory):

        class Meta:
            model = Author

        name = "Charles Dickens"


    def test_model_fixture(author):
        assert author.name == "Charles Dickens"


Model fixtures can be registered with specific names. For example if you address instances of some collection
by the name like "first", "second" or of another parent as "other":


.. code-block:: python

    register(BookFactory)  # book
    register(BookFactory, "second_book")  # second_book

    register(AuthorFactory) # author
    register(AuthorFactory, "second_author") # second_author

    register(BookFactory, "other_book")  # other_book, book of another author

    @pytest.fixture
    def other_book__author(second_author):
        """Make the relation of the second_book to another (second) author."""
        return second_author



Attributes are Fixtures
-----------------------

There are fixtures created for factory attributes. Attribute names are prefixed with the model fixture name and
double underscore (similar to the convention used by factory_boy).


.. code-block:: python

    @pytest.mark.parametrized("author__name", ["Bill Gates"])
    def test_model_fixture(author):
        assert author.name == "Bill Gates"

SubFactory
----------

Sub-factory attribute points to the model fixture of the sub-factory.
Attributes of sub-factories are injected as dependencies to the model fixture and can be overridden_ via
the parametrization.

Related Factory
---------------

Related factory attribute points to the model fixture of the related factory.
Attributes of related factories are injected as dependencies to the model fixture and can be overridden_ via
the parametrization.


post-generation
---------------

Post-generation attribute fixture implements only the extracted value for the post generation function.


Integration
-----------

An example of factory_boy_ and pytest_ integration.

factories/__init__.py:

.. code-block:: python

    import factory
    from faker import Factory as FakerFactory

    faker = FakerFactory.create()


    class AuthorFactory(factory.django.DjangoModelFactory):

        """Author factory."""

        name = factory.LazyAttribute(lambda x: faker.name())

        class Meta:
            model = 'app.Author'


    class BookFactory(factory.django.DjangoModelFactory):

        """Book factory."""

        title = factory.LazyAttribute(lambda x: faker.sentence(nb_words=4))

        class Meta:
            model = 'app.Book'

        author = factory.SubFactory(AuthorFactory)

tests/conftest.py:

.. code-block:: python

    from pytest_factoryboy import register

    from factories import AuthorFactory, BookFactory

    register(AuthorFactory)
    register(BookFactory)

tests/test_models.py:

.. code-block:: python

    from app.models import Book
    from factories import BookFactory

    def test_book_factory(book_factory):
        """Factories become fixtures automatically."""
        assert isinstance(book_factory, BookFactory)

    def test_book(book):
        """Instances become fixtures automatically."""
        assert isinstance(book, Book)

    @pytest.mark.parametrize("book__title", ["PyTest for Dummies"])
    @pytest.mark.parametrize("author__name", ["Bill Gates"])
    def test_parametrized(book):
        """You can set any factory attribute as a fixture using naming convention."""
        assert book.name == "PyTest for Dummies"
        assert book.author.name == "Bill Gates"


Fixture partial specialization
------------------------------

There is a possibility to pass keyword parameters in order to override factory attribute values during fixture
registration. This comes in handy when your test case is requesting a lot of fixture flavors. Too much for the
regular pytest parametrization.
In this case you can register fixture flavors in the local test module and specify value deviations inside ``register``
function calls.


.. code-block:: python

    register(AuthorFactory, "male_author", gender="M", name="John Doe")
    register(AuthorFactory, "female_author", gender="F")


    @pytest.fixture
    def female_author__name():
        """Override female author name as a separate fixture."""
        return "Jane Doe"


    @pytest.mark.parametrize("male_author__age", [42])  # Override even more
    def test_partial(male_author, female_author):
        """Test fixture partial specialization."""
        assert male_author.gender == "M"
        assert male_author.name == "John Doe"
        assert male_author.age == 42

        assert female_author.gender == "F"
        assert female_author.name == "Jane Doe"


Fixture attributes
------------------

Sometimes it is necessary to pass an instance of another fixture as an attribute value to the factory.
It is possible to override the generated attribute fixture where desired values can be requested as
fixture dependencies. There is also a lazy wrapper for the fixture that can be used in the parametrization
without defining fixtures in a module.


LazyFixture constructor accepts either existing fixture name or callable with dependencies:

.. code-block:: python

    import pytest
    from pytest_factoryboy import register, LazyFixture


    @pytest.mark.parametrize("book__author", [LazyFixture("another_author")])
    def test_lazy_fixture_name(book, another_author):
        """Test that book author is replaced with another author by fixture name."""
        assert book.author == another_author


    @pytest.mark.parametrize("book__author", [LazyFixture(lambda another_author: another_author)])
    def test_lazy_fixture_callable(book, another_author):
        """Test that book author is replaced with another author by callable."""
        assert book.author == another_author


    # Can also be used in the partial specialization during the registration.
    register(AuthorFactory, "another_book", author=LazyFixture("another_author"))


Post-generation dependencies
============================

Unlike factory_boy which binds related objects using an internal container to store results of lazy evaluations,
pytest-factoryboy relies on the PyTest request.

Circular dependencies between objects can be resolved using post-generation hooks/related factories in combination with
passing the SelfAttribute, but in the case of PyTest request fixture functions have to return values in order to be cached
in the request and to become available to other fixtures.

That's why evaluation of the post-generation declaration in pytest-factoryboy is deferred until calling
the test funciton.
This solves circular dependecy resolution for situations like:

::

    o->[ A ]-->[ B ]<--[ C ]-o
    |                        |
    o----(C depends on A)----o


On the other hand deferring the evaluation of post-generation declarations evaluation makes their result unavailable during the generation
of objects that are not in the circular dependecy, but they rely on the post-generation action.

pytest-factoryboy is trying to detect cycles and resolve post-generation dependencies automatically.


.. code-block:: python

    from pytest_factoryboy import register


    class Foo(object):

        def __init__(self, value):
            self.value = value


    class Bar(object):

        def __init__(self, foo):
            self.foo = foo


    @register
    class FooFactory(factory.Factory):

        """Foo factory."""

        class Meta:
            model = Foo

        value = 0

        @factory.post_generation
        def set1(foo, create, value, **kwargs):
            foo.value = 1


    class BarFactory(factory.Factory):

        """Bar factory."""

        foo = factory.SubFactory(FooFactory)

        @classmethod
        def _create(cls, model_class, foo):
            assert foo.value == 1  # Assert that set1 is evaluated before object generation
            return super(BarFactory, cls)._create(model_class, foo=foo)

        class Meta:
            model = Bar


    register(
        BarFactory,
        'bar',
    )
    """Forces 'set1' to be evaluated first."""


    def test_depends_on_set1(bar):
        """Test that post-generation hooks are done and the value is 2."""
        assert depends_on_1.foo.value == 1


Hooks
-----

pytest-factoryboy exposes several `pytest hooks <http://pytest.org/latest/plugins.html#well-specified-hooks>`_
which might be helpful for e.g. controlling database transaction, for reporting etc:

* pytest_factoryboy_done(request) - Called after all factory based fixtures and their post-generation actions have been evaluated.


License
-------

This software is licensed under the `MIT license <http://en.wikipedia.org/wiki/MIT_License>`_.

© 2015 Oleg Pidsadnyi, Anatoly Bubenkov and others
