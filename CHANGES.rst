Changelog
=========

All notable changes to this project will be documented in this file.

The format is based on `Keep a Changelog <https://keepachangelog.com/en/1.1.0/>`_,
and this project adheres to `Semantic Versioning <https://semver.org/spec/v2.0.0.html>`_.

Unreleased
----------

Added
+++++

Changed
+++++++

Deprecated
++++++++++

Removed
+++++++

Fixed
+++++

Security
++++++++

2.8.0
----------

Added
+++++
* Declare compatibility with python 3.13. Supported versions are now: 3.9, 3.10, 3.11, 3.12, 3.13.
* Test against pytest 8.4
* Test against python 3.14 (beta)

Changed
+++++++
* Changelog format updated to follow `Keep a Changelog <https://keepachangelog.com/en/1.1.0/>`_.

Deprecated
++++++++++

Removed
+++++++
* Drop support for python 3.8. Supported versions are now: 3.9, 3.10, 3.11, 3.12, 3.13.
* Drop support for pytest < 7.0.0.

Fixed
+++++
* Fix compatibility with ``pytest 8.4``.

Security
++++++++

2.7.0
----------
- Declare required python version >= 3.8. (python 3.7 support was already removed in 2.6.0, the declared supported version tag was not updated though). `#215 <https://github.com/pytest-dev/pytest-factoryboy/pull/215>`_

2.6.1
----------
- Address compatibility issue with pytest 8.1. `#213 <https://github.com/pytest-dev/pytest-bdd/pull/213>`_

2.6.0
----------
- Drop python 3.7 support and add support for python 3.12. Supported versions are now: 3.8, 3.9, 3.10, 3.11, 3.12. `#197 <https://github.com/pytest-dev/pytest-factoryboy/pull/197>`_
- Drop support for pytest < 6.2. We now support only pytest >= 6.2 (tested against pytest 7.4 at the time of writing). `#197 <https://github.com/pytest-dev/pytest-factoryboy/pull/197>`_

2.5.1
----------
- Fix PytestDeprecationWarning. `#180 <https://github.com/pytest-dev/pytest-factoryboy/pull/180>`_ `#179 <https://github.com/pytest-dev/pytest-factoryboy/issues/179>`_

2.5.0
----------
- Using a generic class container like ``dict``, ``list``, ``set``, etc. will raise a warning suggesting you to wrap your model using ``named_model(...)``. Doing this will make sure that the fixture name is correctly chosen, otherwise SubFactory and RelatedFactory aren't able to determine the name of the model. See `Generic Container Classes as models <https://pytest-factoryboy.readthedocs.io/en/latest/#generic-container-classes-as-models>`_ `#167 <https://github.com/pytest-dev/pytest-factoryboy/pull/167>`_
- Fix ``Factory._after_postgeneration`` being invoked twice. `#164 <https://github.com/pytest-dev/pytest-factoryboy/pull/164>`_ `#156 <https://github.com/pytest-dev/pytest-factoryboy/issues/156>`_
- Stack traces caused by pytest-factoryboy are now slimmer. `#169 <https://github.com/pytest-dev/pytest-factoryboy/pull/169>`_
- Check for naming conflicts between factory and model fixture name, and raise a clear error immediately. `#86 <https://github.com/pytest-dev/pytest-factoryboy/pull/86>`_

2.4.0
----------
- ``LazyFixture`` is now a Generic[T] type.
- Simplify fixture generation (internal change).
- Use poetry (internal change).

2.3.1
----------
- Fix AttributeError when using LazyFixture in register(...) `#159 <https://github.com/pytest-dev/pytest-factoryboy/issues/159>`_ `#158 <https://github.com/pytest-dev/pytest-factoryboy/issues/158>`_


2.3.0
----------
- Add support for ``factory.PostGenerationMethodCall`` `#103 <https://github.com/pytest-dev/pytest-factoryboy/pull/103>`_ `#87 <https://github.com/pytest-dev/pytest-factoryboy/issues/87>`_.


2.2.1
----------
- ``@register()`` decorator now refuses kwargs after the initial specialization. This behaviour was mistakenly introduced in version 2.2.0, and it complicates the usage of the ``register`` function unnecessarily. For example, the following is not allowed anymore:

.. code-block:: python

    # INVALID
    register(
        _name="second_author",
        name="C.S. Lewis",
    )(
        AuthorFactory,
        register_user="cs_lewis",
        register_user__password="Aslan1",
    )

    # VALID
    register(
        AuthorFactory,
        _name="second_author",
        name="C.S. Lewis",
        register_user="cs_lewis",
        register_user__password="Aslan1",
    )


2.2.0
----------
- Drop support for Python 3.6. We now support only python >= 3.7.
- Improve "debuggability". Internal pytest-factoryboy calls are now visible when using a debugger like PDB or PyCharm.
- Add type annotations. Now ``register`` and ``LazyFixture`` are type annotated.
- Fix `Factory._after_postgeneration <https://factoryboy.readthedocs.io/en/stable/reference.html#factory.Factory._after_postgeneration>`_ method not getting the evaluated ``post_generations`` and ``RelatedFactory`` results correctly in the ``result`` param.
- Factories can now be registered inside classes (even nested classes) and they won't pollute the module namespace.
- Allow the ``@register`` decorator to be called with parameters:

.. code-block:: python

    @register
    @register("other_author")
    class AuthorFactory(Factory):
        ...


2.1.0
-----

- Add support for factory_boy >= 3.2.0
- Drop support for Python 2.7, 3.4, 3.5. We now support only python >= 3.6.
- Drop support for pytest < 4.6. We now support only pytest >= 4.6.
- Add missing versions of python (3.9 and 3.10) and pytest (6.x.x) to the CI test matrix.


2.0.3
-----

- Fix compatibility with pytest 5.


2.0.2
-----

- Fix warning `use of getfuncargvalue is deprecated, use getfixturevalue` (sliverc)


2.0.1
-----

Breaking change due to the heavy refactor of both pytest and factory_boy.

- Failing test for using a `attributes` field on the factory (blueyed)
- Minimal pytest version is 3.3.2 (olegpidsadnyi)
- Minimal factory_boy version is 2.10.0 (olegpidsadnyi)


1.3.2
-----

- use {posargs} in pytest command (blueyed)
- pin factory_boy<2.9 (blueyed)


1.3.1
-----

- fix LazyFixture evaluation order (olegpidsadnyi)


1.3.0
-----

- replace request._fixturedefs by request._fixture_defs (p13773)


1.2.2
-----

- fix post-generation dependencies (olegpidsadnyi)


1.2.1
-----

- automatic resolution of the post-generation dependencies (olegpidsadnyi, kvas-it)


1.1.6
-----

- fixes fixture function module name attribute (olegpidsadnyi)
- fixes _after_postgeneration hook invocation for deferred post-generation declarations (olegpidsadnyi)


1.1.5
-----

- support factory models to be passed as strings (bubenkoff)


1.1.3
-----

- circular dependency determination is fixed for the post-generation (olegpidsadnyi)


1.1.2
-----

- circular dependency determination is fixed for the RelatedFactory attributes (olegpidsadnyi)


1.1.1
-----

- fix installation issue when django environment is not set (bubenkoff, amakhnach)


1.1.0
-----

- fixture dependencies on deferred post-generation declarations (olegpidsadnyi)


1.0.3
-----

- post_generation extra parameters fixed (olegpidsadnyi)
- fixture partial specialization (olegpidsadnyi)
- fixes readme and example (dduong42)
- lazy fixtures (olegpidsadnyi)
- deferred post-generation evaluation (olegpidsadnyi)
- hooks (olegpidsadnyi)


1.0.2
-----

- refactoring of the fixture function compilation (olegpidsadnyi)
- related factory fix (olegpidsadnyi)
- post_generation fixture dependency fixed (olegpidsadnyi)
- model fixture registration with specific name (olegpidsadnyi)
- README updated (olegpidsadnyi)

1.0.1
-----

- use ``inflection`` package to convert camel case to underscore (bubenkoff)

1.0.0
-----

- initial release (olegpidsadnyi)
