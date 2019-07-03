"""Factory boy fixture integration."""

import sys

import factory
import factory.builder
import factory.declarations
import factory.enums
import inflection
import pytest

from inspect import getmodule

if sys.version_info > (3, 0):
    from inspect import signature
else:
    from funcsigs import signature

SEPARATOR = "__"


FIXTURE_FUNC_FORMAT = """
def {name}({deps}):
    return _fixture_impl(request, **kwargs)
"""


def make_fixture(name, module, func, args=None, related=None, **kwargs):
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
    fixture_func.__module__ = module.__name__

    if related:
        fixture_func._factoryboy_related = related

    fixture = pytest.fixture(fixture_func)
    setattr(module, name, fixture)
    return fixture


def register(factory_class, _name=None, **kwargs):
    r"""Register fixtures for the factory class.

    :param factory_class: Factory class to register.
    :param _name: Name of the model fixture. By default is lowercase-underscored model name.
    :param \**kwargs: Optional keyword arguments that override factory attributes.
    """
    assert not factory_class._meta.abstract, "Can't register abstract factories."
    assert factory_class._meta.model is not None, "Factory model class is not specified."

    module = get_caller_module()
    model_name = get_model_name(factory_class) if _name is None else _name
    factory_name = get_factory_name(factory_class)

    deps = get_deps(factory_class, model_name=model_name)
    related = []

    for attr, value in factory_class._meta.declarations.items():
        args = None
        attr_name = SEPARATOR.join((model_name, attr))

        if isinstance(value, factory.declarations.PostGeneration):
            value = kwargs.get(attr, None)
            if isinstance(value, LazyFixture):
                args = value.args

            make_fixture(
                name=attr_name,
                module=module,
                func=attr_fixture,
                value=value,
                args=args,
            )
        else:
            value = kwargs.get(attr, value)

            if isinstance(value, (factory.SubFactory, factory.RelatedFactory)):
                subfactory_class = value.get_factory()
                subfactory_deps = get_deps(subfactory_class, factory_class)

                args = list(subfactory_deps)
                if isinstance(value, factory.RelatedFactory):
                    related_model = get_model_name(subfactory_class)
                    args.append(related_model)
                    related.append(related_model)
                    related.append(attr_name)
                    related.extend(subfactory_deps)

                if isinstance(value, factory.SubFactory):
                    args.append(inflection.underscore(subfactory_class._meta.model.__name__))

                make_fixture(
                    name=attr_name,
                    module=module,
                    func=subfactory_fixture,
                    args=args,
                    factory_class=subfactory_class,
                )
            else:
                if isinstance(value, LazyFixture):
                    args = value.args

                make_fixture(
                    name=attr_name,
                    module=module,
                    func=attr_fixture,
                    value=value,
                    args=args,
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
        related=related,
    )
    return factory_class


def get_model_name(factory_class):
    """Get model fixture name by factory."""
    return (
        inflection.underscore(factory_class._meta.model.__name__)
        if not isinstance(factory_class._meta.model, str) else factory_class._meta.model)


def get_factory_name(factory_class):
    """Get factory fixture name by factory."""
    return inflection.underscore(factory_class.__name__)


def get_deps(factory_class, parent_factory_class=None, model_name=None):
    """Get factory dependencies.

    :return: List of the fixture argument names for dependency injection.
    """
    model_name = get_model_name(factory_class) if model_name is None else model_name
    parent_model_name = get_model_name(parent_factory_class) if parent_factory_class is not None else None

    def is_dep(value):
        if isinstance(value, factory.RelatedFactory):
            return False
        if isinstance(value, factory.SubFactory) and get_model_name(value.get_factory()) == parent_model_name:
                return False
        if isinstance(value, factory.declarations.PostGeneration):
            # Dependency on extracted value
            return True

        return True

    return [
        SEPARATOR.join((model_name, attr))
        for attr, value in factory_class._meta.declarations.items()
        if is_dep(value)
    ]


def evaluate(request, value):
    """Evaluate the declaration (lazy fixtures, etc)."""
    return value.evaluate(request) if isinstance(value, LazyFixture) else value


def model_fixture(request, factory_name):
    """Model fixture implementation."""
    factoryboy_request = request.getfixturevalue("factoryboy_request")

    # Try to evaluate as much post-generation dependencies as possible
    factoryboy_request.evaluate(request)

    factory_class = request.getfixturevalue(factory_name)
    prefix = "".join((request.fixturename, SEPARATOR))

    # Create model fixture instance

    class Factory(factory_class):
        pass

    Factory._meta.base_declarations = dict(
        (k, v) for k, v in Factory._meta.base_declarations.items()
        if not isinstance(v, factory.declarations.PostGenerationDeclaration)
    )
    Factory._meta.post_declarations = factory.builder.DeclarationSet()

    kwargs = {}
    for key in factory_class._meta.pre_declarations:
        argname = "".join((prefix, key))
        if argname in request._fixturedef.argnames:
            kwargs[key] = evaluate(request, request.getfixturevalue(argname))

    strategy = factory.enums.CREATE_STRATEGY
    builder = factory.builder.StepBuilder(Factory._meta, kwargs, strategy)
    step = factory.builder.BuildStep(builder=builder, sequence=Factory._meta.next_sequence())

    instance = Factory(**kwargs)

    # Cache the instance value on pytest level so that the fixture can be resolved before the return
    request._fixturedef.cached_result = (instance, 0, None)
    request._fixture_defs[request.fixturename] = request._fixturedef

    # Defer post-generation declarations
    deferred = []

    for attr in factory_class._meta.post_declarations.sorted():

        decl = factory_class._meta.post_declarations.declarations[attr]

        if isinstance(decl, factory.RelatedFactory):
            deferred.append(make_deferred_related(factory_class, request.fixturename, attr))
        else:
            argname = "".join((prefix, attr))
            extra = {}
            for k, v in factory_class._meta.post_declarations.contexts[attr].items():
                if k == '':
                    continue
                post_attr = SEPARATOR.join((argname, k))

                if post_attr in request._fixturedef.argnames:
                    extra[k] = evaluate(request, request.getfixturevalue(post_attr))
                else:
                    extra[k] = v

            postgen_context = factory.builder.PostGenerationContext(
                value_provided=True,
                value=evaluate(request, request.getfixturevalue(argname)),
                extra=extra,
            )
            deferred.append(
                make_deferred_postgen(step, factory_class, request.fixturename, instance, attr, decl, postgen_context)
            )
    factoryboy_request.defer(deferred)

    # Try to evaluate as much post-generation dependencies as possible
    factoryboy_request.evaluate(request)
    return instance


def make_deferred_related(factory, fixture, attr):
    """Make deferred function for the related factory declaration.

    :param factory: Factory class.
    :param fixture: Object fixture name e.g. "book".
    :param attr: Declaration attribute name e.g. "publications".

    :note: Deferred function name results in "book__publication".
    """
    name = SEPARATOR.join((fixture, attr))

    def deferred(request):
        request.getfixturevalue(name)

    deferred.__name__ = name
    deferred._factory = factory
    deferred._fixture = fixture
    deferred._is_related = True
    return deferred


def make_deferred_postgen(step, factory_class, fixture, instance, attr, declaration, context):
    """Make deferred function for the post-generation declaration.

    :param step: factory_boy builder step.
    :param factory_class: Factory class.
    :param fixture: Object fixture name e.g. "author".
    :param instance: Parent object instance.
    :param attr: Declaration attribute name e.g. "register_user".
    :param context: Post-generation declaration context.

    :note: Deferred function name results in "author__register_user".
    """
    name = SEPARATOR.join((fixture, attr))

    def deferred(request):
        declaration.call(instance, step, context)

    deferred.__name__ = name
    deferred._factory = factory_class
    deferred._fixture = fixture
    deferred._is_related = False
    return deferred


def factory_fixture(request, factory_class):
    """Factory fixture implementation."""
    return factory_class


def attr_fixture(request, value):
    """Attribute fixture implementation."""
    return value


def subfactory_fixture(request, factory_class):
    """SubFactory/RelatedFactory fixture implementation."""
    fixture = inflection.underscore(factory_class._meta.model.__name__)
    return request.getfixturevalue(fixture)


def get_caller_module(depth=2):
    """Get the module of the caller."""
    frame = sys._getframe(depth)
    module = getmodule(frame)
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
        if callable(self.fixture):
            params = signature(self.fixture).parameters.values()
            self.args = [
                param.name for param in params
                if param.kind == param.POSITIONAL_OR_KEYWORD
            ]
        else:
            self.args = [self.fixture]

    def evaluate(self, request):
        """Evaluate the lazy fixture.

        :param request: pytest request object.
        :return: evaluated fixture.
        """
        if callable(self.fixture):
            kwargs = dict((arg, request.getfixturevalue(arg)) for arg in self.args)
            return self.fixture(**kwargs)
        else:
            return request.getfixturevalue(self.fixture)
