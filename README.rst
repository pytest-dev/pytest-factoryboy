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

Install pytest-factoryboy
-------------------------

::

    pip install pytest-factoryboy

Example
-------

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
