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


def register(factory_class, name=None):
    """Register fixtures for the factory class.

    :param factory_class: Factory class to register.
    :param name: Name of the model fixture. By default is lowercase-underscored model name.
    """
    module = get_caller_module()
    model_name = get_model_name(factory_class) if name is None else name
    factory_name = get_factory_name(factory_class)

    deps = get_deps(factory_class, model_name=model_name)
    for attr, value in factory_class.declarations(factory_class._meta.postgen_declarations).items():
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
    return inflection.underscore(factory_class._meta.model.__name__)


def get_factory_name(factory_class):
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
    factory_class = request.getfuncargvalue(factory_name)
    prefix = "".join((request.fixturename, SEPARATOR))
    data = {}
    for argname in request._fixturedef.argnames:
        if argname.startswith(prefix) and argname[len(prefix):] not in factory_class._meta.postgen_declarations:
            data[argname[len(prefix):]] = request.getfuncargvalue(argname)

    class Factory(factory_class):
        pass

    Factory._meta.postgen_declarations = {}
    Factory._meta.exclude = [value for value in Factory._meta.exclude if value in data]
    result = Factory(**data)

    if factory_class._meta.postgen_declarations:
        request._fixturedef.cached_result = (result, 0, None)
        request._fixturedefs[request.fixturename] = request._fixturedef
        postgen_declarations = {}
        for attr, declaration in factory_class._meta.postgen_declarations.items():
            if isinstance(declaration, factory.RelatedFactory):
                request.getfuncargvalue(prefix + attr)
            else:
                postgen_declarations[attr] = declaration

        for attr, declaration in postgen_declarations.items():
            declaration.function(result, True, request.getfuncargvalue(prefix + attr))

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
