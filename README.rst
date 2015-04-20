factory_boy_ integration the pytest_ runner
===========================================

.. image:: https://api.travis-ci.org/pytest-dev/pytest-factoryboy.png
   :target: https://travis-ci.org/pytest-dev/pytest-factoryboy
.. image:: https://pypip.in/v/pytest-factoryboy/badge.png
   :target: https://crate.io/packages/pytest-factoryboy/
.. image:: https://coveralls.io/repos/pytest-dev/pytest-factoryboy/badge.png?branch=master
   :target: https://coveralls.io/r/pytest-dev/pytest-factoryboy
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

    class AuthorFactory(Factory):

        class Meta:
            model = Author


    register(Author)


    def test_factory_fixture(author_factory):
        author = author_fixture(name="Charles Dickens")
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
    register(BookFactory, name="second_book")  # second_book

    register(AuthorFactory) # author
    register(AuthorFactory, name="second_author") # second_author

    register(BookFactory, name="other_book")  # other_book, book of another author

    @pytest.fixture
    def other_book__author(second_author):
        """Make the relation of the second_book to another (second) author."""
        return second_author



Attributes are Fixtures
-----------------------

There are fixtures created for factory attributes. Attribute names are prefixed with the model fixture name and
double underscore (similar to factory boy convention).


.. code-block:: python

    @pytest.mark.parametrized("author__name", ["Bill Gates"])
    def test_model_fixture(author):
        assert author.name == "Bill Gates"

SubFactory
----------

Sub-factory attribute points to the model fixture of the sub-factory.
Attributes of sub-factories are injected as dependencies to the model fixture and can be overridden_ in
the parametrization.

Related Factory
---------------

Related factory attribute points to the model fixture of the related factory.
Attributes of related factories are injected as dependencies to the model fixture and can be overridden_ in
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


License
-------

This software is licensed under the `MIT license <http://en.wikipedia.org/wiki/MIT_License>`_.

© 2015 Oleg Pidsadnyi, Anatoly Bubenkov and others
