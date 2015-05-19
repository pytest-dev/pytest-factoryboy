"""Factory boy fixture integration."""

import sys
import inspect

import factory
import inflection
import pytest


SEPARATOR = "__"


FIXTURE_FUNC_FORMAT = """
def {name}({deps}):
    return _fixture_impl(request, **kwargs)
"""


def make_fixture(name, module, func, args=None, **kwargs):
    """Make fixture function and inject arguments.

    :param name: Fixture name.
    :param module: Python module to contribute the fixture into.
    :param func: Fixture implementation function.
    :param args: Argument names.
    """
    args = [] if args is None else list(args)
    if "request" not in args:
        args.insert(0, "request")
    deps = ", ".join(args)
    context = dict(_fixture_impl=func, kwargs=kwargs)
    context.update(kwargs)
    exec(FIXTURE_FUNC_FORMAT.format(name=name, deps=deps), context)
    fixture_func = context[name]
    fixture_func.__module__ = module
    fixture = pytest.fixture(fixture_func)
    setattr(module, name, fixture)
    return fixture


def register(factory_class, _name=None, **kwargs):
    """Register fixtures for the factory class.

    :param factory_class: Factory class to register.
    :param _name: Name of the model fixture. By default is lowercase-underscored model name.
    :param \**kwargs: Optional keyword arguments that override factory attributes.
    """
    module = get_caller_module()
    model_name = get_model_name(factory_class) if _name is None else _name
    factory_name = get_factory_name(factory_class)

    deps = get_deps(factory_class, model_name=model_name)
    for attr, value in factory_class.declarations(factory_class._meta.postgen_declarations).items():
        value = kwargs.get(attr, value)  # Partial specialization
        attr_name = SEPARATOR.join((model_name, attr))

        if isinstance(value, (factory.SubFactory, factory.RelatedFactory)):
            subfactory_class = value.get_factory()
            make_fixture(
                name=attr_name,
                module=module,
                func=subfactory_fixture,
                args=get_deps(subfactory_class, factory_class),
                factory_class=subfactory_class,
            )
            if isinstance(value, factory.RelatedFactory):
                deps.extend(get_deps(subfactory_class, factory_class))
        else:
            make_fixture(
                name=attr_name,
                module=module,
                func=attr_fixture,
                value=value if not isinstance(value, factory.declarations.PostGeneration) else None,
            )
    if not hasattr(module, factory_name):
        make_fixture(
            name=factory_name,
            module=module,
            func=factory_fixture,
            factory_class=factory_class,
        )

    make_fixture(
        name=model_name,
        module=module,
        func=model_fixture,
        args=deps,
        factory_name=factory_name,
    )
    return factory_class


def get_model_name(factory_class):
    """Get model fixture name by factory."""
    return inflection.underscore(factory_class._meta.model.__name__)


def get_factory_name(factory_class):
    """Get factory fixture name by factory."""
    return inflection.underscore(factory_class.__name__)


def get_deps(factory_class, parent_factory_class=None, model_name=None):
    """Get factory dependencies.

    :return: List of the fixture argument names for dependency injection.
    """
    model_name = get_model_name(factory_class) if model_name is None else model_name
    parent_model_name = get_model_name(parent_factory_class) if parent_factory_class is not None else None
    return [
        SEPARATOR.join((model_name, attr))
        for attr, value in factory_class.declarations(factory_class._meta.postgen_declarations).items()
        if attr != parent_model_name and not isinstance(value, factory.RelatedFactory)
    ]


def model_fixture(request, factory_name):
    """Model fixture implementation."""

    def evaluate(value):
        """Evaluate the declaration (lazy fixtures, etc)."""
        return value.evaluate(request) if isinstance(value, LazyFixture) else value

    factory_class = request.getfuncargvalue(factory_name)
    prefix = "".join((request.fixturename, SEPARATOR))
    data = {}
    for argname in request._fixturedef.argnames:
        if argname.startswith(prefix) and argname[len(prefix):] not in factory_class._meta.postgen_declarations:
            data[argname[len(prefix):]] = request.getfuncargvalue(argname)

    class Factory(factory_class):

        @classmethod
        def attributes(cls, create=False, extra=None):
            return dict(
                (key, evaluate(value))
                for key, value in super(Factory, cls).attributes(create=create, extra=extra).items()
                if key in data
            )

    Factory._meta.postgen_declarations = {}
    Factory._meta.exclude = [value for value in Factory._meta.exclude if value in data]

    postgen_declarations = {}
    postgen_declaration_args = {}
    related = []
    postgen = []
    if factory_class._meta.postgen_declarations:
        for attr, declaration in sorted(factory_class._meta.postgen_declarations.items()):
            postgen_declarations[attr] = declaration
            postgen_declaration_args[attr] = declaration.extract(attr, data)
            if isinstance(declaration, factory.RelatedFactory):
                related.append(attr)
            else:
                postgen.append(attr)

    result = Factory(**data)
    if postgen_declarations:
        factoryboy_request = request.getfuncargvalue("factoryboy_request")

        def deferred():
            for attr in related:
                request.getfuncargvalue(prefix + attr)
            for attr in postgen:
                declaration = postgen_declarations[attr]
                context = postgen_declaration_args[attr]
                context.value = evaluate(request.getfuncargvalue(prefix + attr))
                context.extra = dict((key, evaluate(value)) for key, value in context.extra.items())
                declaration.call(result, True, context)

        factoryboy_request.defer(deferred)
    return result


def factory_fixture(request, factory_class):
    """Factory fixture implementation."""
    return factory_class


def attr_fixture(request, value):
    """Attribute fixture implementation."""
    return value


def subfactory_fixture(request, factory_class):
    """SubFactory/RelatedFactory fixture implementation."""
    fixture = inflection.underscore(factory_class._meta.model.__name__)
    return request.getfuncargvalue(fixture)


def get_caller_module(depth=2):
    """Get the module of the caller."""
    frame = sys._getframe(depth)
    module = inspect.getmodule(frame)
    # Happens when there's no __init__.py in the folder
    if module is None:
        return get_caller_module(depth=depth)  # pragma: no cover
    return module


class LazyFixture(object):

    """Lazy fixture."""

    def __init__(self, fixture):
        """Lazy pytest fixture wrapper.

        :param fixture: Fixture name or callable with dependencies.
        """
        self.fixture = fixture

    def evaluate(self, request):
        """Evaluate the lazy fixture.

        :param request: pytest request object.
        :return: evaluated fixture.
        """
        if callable(self.fixture):
            kwargs = dict((arg, request.getfuncargvalue(arg)) for arg in inspect.getargspec(self.fixture).args)
            return self.fixture(**kwargs)
        else:
            return request.getfuncargvalue(self.fixture)
