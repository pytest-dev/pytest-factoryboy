"""Factory boy fixture integration."""
import re
import sys
import inspect
from types import CodeType

import factory
import pytest
import six


SEPARATOR = "__"


def to_underscore(value):
    return re.sub("(?!^)([A-Z]+)", r"_\1", value).lower()


def register(factory_class):
    """Register fixtures for the factory class."""
    module = get_caller_module()
    model_name = get_model_name(factory_class)
    factory_name = get_factory_name(factory_class)

    deps = get_deps(factory_class)
    for attr, value in factory_class.declarations(factory_class._meta.postgen_declarations).items():
        fixture = None
        attr_name = SEPARATOR.join((model_name, attr))
        add_args = []
        if isinstance(value, (factory.SubFactory, factory.RelatedFactory)):
            subfactory_class = value.get_factory()
            fixture = make_subfactory_fixture(subfactory_class)
            add_args = get_deps(subfactory_class, factory_class)
            if isinstance(value, factory.RelatedFactory):
                deps.extend(get_deps(subfactory_class, factory_class))
        else:
            fixture = make_attr_fixture(value)

        if fixture is not None:
            contribute_to_module(module, attr_name, fixture, add_args=add_args)

    contribute_to_module(module, factory_name, make_factory_fixture(factory_class))
    contribute_to_module(module, model_name, make_model_fixture(factory_name), add_args=deps)
    return factory_class


def get_model_name(factory_class):
    return to_underscore(factory_class._meta.model.__name__)


def get_factory_name(factory_class):
    return to_underscore(factory_class.__name__)


def get_deps(factory_class, parent_factory_class=None):
    model_name = get_model_name(factory_class)
    parent_model_name = get_model_name(parent_factory_class) if parent_factory_class is not None else None
    return [
        SEPARATOR.join((model_name, attr))
        for attr in factory_class._meta.declarations
        if attr != parent_model_name
    ]


def make_model_fixture(factory_name):
    @pytest.fixture
    def model_fixture(request):
        factory_class = request.getfuncargvalue(factory_name)
        prefix = "".join((request.fixturename, SEPARATOR))
        data = {}

        for argname in request._fixturedef.argnames:
            if argname.startswith(prefix):
                data[argname[len(prefix):]] = request.getfuncargvalue(argname)

        class Factory(factory_class):
            pass

        related_factories = []
        for attr, value in Factory._meta.postgen_declarations.items():
            if isinstance(value, factory.RelatedFactory):
                related_factories.append(value)
                Factory._meta.postgen_declarations.pop(attr)

        result = Factory(**data)

        if related_factories:
            request._fixturedef.cached_result = (result, 0, None)
            request._fixturedefs[request.fixturename] = request._fixturedef

            for related_factory in related_factories:
                related_factory_class = related_factory.get_factory()
                model_name = get_model_name(related_factory_class)
                request.getfuncargvalue(model_name)
        return result

    return model_fixture


def make_factory_fixture(factory_class):
    @pytest.fixture
    def factory_fixture():
        return factory_class
    return factory_fixture


def make_attr_fixture(value):
    @pytest.fixture
    def attr_fixture():
        return value
    return attr_fixture


def make_subfactory_fixture(factory_class):
    fixture = to_underscore(factory_class._meta.model.__name__)

    @pytest.fixture
    def subfactory_fixture(request):
        return request.getfuncargvalue(fixture)
    return subfactory_fixture


def recreate_function(func, module=None, name=None, add_args=[], firstlineno=None):
    """Recreate a function, replacing some info.

    :param func: Function object.
    :param module: Module to contribute to.
    :param add_args: Additional arguments to add to the function.

    :return: Function copy.
    """
    def get_code(func):
        return func.__code__ if six.PY3 else func.func_code

    def set_code(func, code):
        if six.PY3:
            func.__code__ = code
        else:
            func.func_code = code

    argnames = [
        "co_argcount", "co_nlocals", "co_stacksize", "co_flags", "co_code", "co_consts", "co_names",
        "co_varnames", "co_filename", "co_name", "co_firstlineno", "co_lnotab", "co_freevars", "co_cellvars",
    ]
    if six.PY3:
        argnames.insert(1, "co_kwonlyargcount")

    for arg in inspect.getargspec(func).args:
        if arg in add_args:
            add_args.remove(arg)

    args = []
    code = get_code(func)
    for arg in argnames:
        if module is not None and arg == "co_filename":
            args.append(module.__file__)
        elif name is not None and arg == "co_name":
            args.append(name)
        elif arg == "co_argcount":
            args.append(getattr(code, arg) + len(add_args))
        elif arg == "co_varnames":
            co_varnames = getattr(code, arg)
            args.append(co_varnames[:code.co_argcount] + tuple(add_args) + co_varnames[code.co_argcount:])
        elif arg == "co_firstlineno":
            args.append(firstlineno if firstlineno else 0)
        else:
            args.append(getattr(code, arg))

    set_code(func, CodeType(*args))
    if name is not None:
        func.__name__ = name
    return func


def contribute_to_module(module, name, func, add_args=[]):
    """Contribute a function to a module.

    :param module: Module to contribute to.
    :param name: Attribute name.
    :param func: Function object.
    :param add_args: Additional arguments to add to the function.

    :return: New function copy contributed to the module
    """
    func = recreate_function(func, module=module, add_args=add_args)
    setattr(module, name, func)
    return func


def get_caller_module(depth=2):
    """Get the module of the caller."""
    frame = sys._getframe(depth)
    module = inspect.getmodule(frame)
    if module is None:
        return get_caller_module(depth=depth)
    return module
