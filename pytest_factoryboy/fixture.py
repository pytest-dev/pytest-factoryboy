"""Factory boy fixture integration."""
from __future__ import annotations

import contextlib
import functools
import sys
import warnings
from dataclasses import dataclass
from inspect import signature
from types import MethodType
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Collection,
    Generic,
    Iterable,
    Iterator,
    Mapping,
    Type,
    TypeVar,
    cast,
    overload,
)

import factory
import factory.builder
import factory.declarations
import factory.enums
import inflection
from typing_extensions import ParamSpec, TypeAlias

from .compat import PostGenerationContext
from .fixturegen import create_fixture

if TYPE_CHECKING:
    from _pytest.fixtures import SubRequest

    from .plugin import Request as FactoryboyRequest

FactoryType: TypeAlias = Type[factory.Factory]
F = TypeVar("F", bound=FactoryType)
T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)
P = ParamSpec("P")

SEPARATOR = "__"
WARN_FOR_MODEL_TYPES = frozenset({dict, list, set, tuple, frozenset})


@dataclass(eq=False)
class DeferredFunction:
    name: str
    factory: FactoryType
    is_related: bool
    function: Callable[[SubRequest], Any]

    def __call__(self, request: SubRequest) -> Any:
        return self.function(request)


class Box(Generic[T_co]):
    """Simple box class, used to hold a value.

    The main purpose of this is to hold objects that we don't want to appear in stack traces.
    For example, the "caller_locals" dict holding a lot of items.
    """

    def __init__(self, value: T_co) -> None:
        self.value = value


def named_model(model_cls: type[T], name: str) -> type[T]:
    """Return a model class with a given name."""
    return type(name, (model_cls,), {})


# register(AuthorFactory, ...)
#
# @register
# class AuthorFactory(factory.Factory): ...
@overload
def register(factory_class: F, _name: str | None = None, **kwargs: Any) -> F:
    ...


# @register(...)
# class AuthorFactory(factory.Factory): ...
@overload
def register(*, _name: str | None = None, **kwargs: Any) -> Callable[[F], F]:
    ...


def register(
    factory_class: F | None = None,
    _name: str | None = None,
    *,
    _caller_locals: Box[dict[str, Any]] | None = None,
    **kwargs: Any,
) -> F | Callable[[F], F]:
    r"""Register fixtures for the factory class.

    :param factory_class: Factory class to register.
    :param _name: Name of the model fixture. By default, is lowercase-underscored model name.
    :param _caller_locals: Dictionary where to inject the generated fixtures. Defaults to the caller's locals().
    :param \**kwargs: Optional keyword arguments that override factory attributes.
    """
    if _caller_locals is None:
        _caller_locals = Box(get_caller_locals())

    if factory_class is None:

        def register_(factory_class: F) -> F:
            return register(factory_class, _name=_name, _caller_locals=_caller_locals, **kwargs)

        return register_

    assert not factory_class._meta.abstract, "Can't register abstract factories."
    assert factory_class._meta.model is not None, "Factory model class is not specified."

    factory_name = get_factory_name(factory_class)
    model_name = get_model_name(factory_class) if _name is None else _name

    assert model_name != factory_name, (
        f"Naming collision for {factory_class}:\n"
        f" * factory fixture name: {factory_name}\n"
        f" * model fixture name: {model_name}\n"
        f"Please provide different name for model fixture."
    )

    fixture_defs = dict(
        generate_fixtures(
            factory_class=factory_class,
            model_name=model_name,
            factory_name=factory_name,
            overrides=kwargs,
            caller_locals=_caller_locals,
        )
    )
    for name, fixture in fixture_defs.items():
        inject_into_caller(name, fixture, _caller_locals)

    return factory_class


def generate_fixtures(
    factory_class: FactoryType,
    model_name: str,
    factory_name: str,
    overrides: Mapping[str, Any],
    caller_locals: Box[Mapping[str, Any]],
) -> Iterable[tuple[str, Callable[..., Any]]]:
    """Generate all the FixtureDefs for the given factory class."""

    related: list[str] = []
    for attr, value in factory_class._meta.declarations.items():
        value = overrides.get(attr, value)
        attr_name = SEPARATOR.join((model_name, attr))
        yield (
            attr_name,
            make_declaration_fixturedef(
                attr_name=attr_name,
                value=value,
                factory_class=factory_class,
                related=related,
            ),
        )

    if factory_name not in caller_locals.value:
        yield (
            factory_name,
            create_fixture_with_related(
                name=factory_name,
                function=functools.partial(factory_fixture, factory_class=factory_class),
            ),
        )

    deps = get_deps(factory_class, model_name=model_name)
    yield (
        model_name,
        create_fixture_with_related(
            name=model_name,
            function=functools.partial(model_fixture, factory_name=factory_name),
            fixtures=deps,
            related=related,
        ),
    )


def create_fixture_with_related(
    name: str,
    function: Callable[P, T],
    fixtures: Collection[str] | None = None,
    related: Collection[str] | None = None,
) -> Callable[P, T]:
    if related is None:
        related = []
    f = create_fixture(name=name, function=function, fixtures=fixtures)

    # We have to set the `_factoryboy_related` attribute to the original function, since
    # FixtureDef.func will provide that one later when we discover the related fixtures.
    f.__pytest_wrapped__.obj._factoryboy_related = related  # type: ignore[attr-defined]
    return f


def make_declaration_fixturedef(
    attr_name: str,
    value: Any,
    factory_class: FactoryType,
    related: list[str],
) -> Callable[..., Any]:
    """Create the FixtureDef for a factory declaration."""
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

        return create_fixture_with_related(
            name=attr_name,
            function=functools.partial(subfactory_fixture, factory_class=subfactory_class),
            fixtures=args,
        )

    deps: list[str]  # makes mypy happy
    if isinstance(value, factory.PostGeneration):
        value = None
        deps = []
    elif isinstance(value, factory.PostGenerationMethodCall):
        value = value.method_arg
        deps = []
    elif isinstance(value, LazyFixture):
        value = value
        deps = value.args
    else:
        value = value
        deps = []

    return create_fixture_with_related(
        name=attr_name,
        function=functools.partial(attr_fixture, value=value),
        fixtures=deps,
    )


def inject_into_caller(name: str, function: Callable[..., Any], locals_: Box[dict[str, Any]]) -> None:
    """Inject a function into the caller's locals, making sure that the function will work also within classes."""
    # We need to check if the caller frame is a class, since in that case the first argument is the class itself.
    # In that case, we can apply the staticmethod() decorator to the injected function, so that the first param
    # will be disregarded.
    # To figure out if the caller frame is a class, we can check if the __qualname__ attribute is present.

    # According to the python docs, __qualname__ is available for both **classes and functions**.
    # However, it seems that for functions it is not yet available in the function namespace before it's defined.
    # This could change in the future, but it shouldn't be too much of a problem since registering a factory
    # in a function namespace would not make it usable anyway.
    # Therefore, we can just check for __qualname__ to figure out if we are in a class, and apply the @staticmethod.
    is_class_or_function = "__qualname__" in locals_.value
    if is_class_or_function:
        function = staticmethod(function)

    locals_.value[name] = function


def get_model_name(factory_class: FactoryType) -> str:
    """Get model fixture name by factory."""
    model_cls = factory_class._meta.model

    if isinstance(model_cls, str):
        return model_cls

    model_name = inflection.underscore(model_cls.__name__)
    if model_cls in WARN_FOR_MODEL_TYPES:
        warnings.warn(
            f"Using a {model_cls} as model type for {factory_class} is discouraged by pytest-factoryboy, "
            f"as it assumes that the model name is {model_name!r} when using it as SubFactory or RelatedFactory, "
            "which is too generic and probably not what you want.\n"
            "You can giving an explicit name to the model by using:\n"
            f'model = named_model({model_cls.__name__}, "Foo")',
        )

    return model_name


def get_factory_name(factory_class: FactoryType) -> str:
    """Get factory fixture name by factory."""
    return inflection.underscore(factory_class.__name__)


def get_deps(
    factory_class: FactoryType,
    parent_factory_class: FactoryType | None = None,
    model_name: str | None = None,
) -> list[str]:
    """Get factory dependencies.

    :return: List of the fixture argument names for dependency injection.
    """
    model_name = get_model_name(factory_class) if model_name is None else model_name
    parent_model_name = get_model_name(parent_factory_class) if parent_factory_class is not None else None

    def is_dep(value: Any) -> bool:
        if isinstance(value, factory.RelatedFactory):
            return False
        if isinstance(value, factory.SubFactory) and get_model_name(value.get_factory()) == parent_model_name:
            return False
        if isinstance(value, factory.declarations.PostGenerationDeclaration):
            # Dependency on extracted value
            return True

        return True

    return [
        SEPARATOR.join((model_name, attr)) for attr, value in factory_class._meta.declarations.items() if is_dep(value)
    ]


def evaluate(request: SubRequest, value: LazyFixture[T] | T) -> T:
    """Evaluate the declaration (lazy fixtures, etc)."""
    return value.evaluate(request) if isinstance(value, LazyFixture) else value


def noop(*args: Any, **kwargs: Any) -> None:
    """No-op function."""
    pass


@contextlib.contextmanager
def disable_method(method: MethodType) -> Iterator[None]:
    """Disable a method."""
    klass = method.__self__
    method_name = method.__name__
    old_method = getattr(klass, method_name)
    setattr(klass, method_name, noop)
    try:
        yield
    finally:
        setattr(klass, method.__name__, old_method)


def model_fixture(request: SubRequest, factory_name: str) -> Any:
    """Model fixture implementation."""
    factoryboy_request: FactoryboyRequest = request.getfixturevalue("factoryboy_request")

    # Try to evaluate as much post-generation dependencies as possible
    factoryboy_request.evaluate(request)

    assert request.fixturename  # NOTE: satisfy mypy
    fixture_name = request.fixturename
    prefix = "".join((fixture_name, SEPARATOR))

    factory_class: FactoryType = request.getfixturevalue(factory_name)

    # Create model fixture instance
    Factory: FactoryType = cast(FactoryType, type("Factory", (factory_class,), {}))
    # equivalent to:
    # class Factory(factory_class):
    #     pass
    # it just makes mypy understand it.

    Factory._meta.base_declarations = {
        k: v
        for k, v in Factory._meta.base_declarations.items()
        if not isinstance(v, factory.declarations.PostGenerationDeclaration)
    }
    Factory._meta.post_declarations = factory.builder.DeclarationSet()

    kwargs = {}
    for key in factory_class._meta.pre_declarations:
        argname = "".join((prefix, key))
        if argname in request._fixturedef.argnames:
            kwargs[key] = evaluate(request, request.getfixturevalue(argname))

    strategy = factory.enums.CREATE_STRATEGY
    builder = factory.builder.StepBuilder(Factory._meta, kwargs, strategy)
    step = factory.builder.BuildStep(builder=builder, sequence=Factory._meta.next_sequence())

    # FactoryBoy invokes the `_after_postgeneration` method, but we will instead call it manually later,
    # once we are able to evaluate all the related fixtures.
    with disable_method(Factory._after_postgeneration):
        instance = Factory(**kwargs)

    # Cache the instance value on pytest level so that the fixture can be resolved before the return
    request._fixturedef.cached_result = (instance, 0, None)
    request._fixture_defs[fixture_name] = request._fixturedef

    # Defer post-generation declarations
    deferred: list[DeferredFunction] = []

    for attr in factory_class._meta.post_declarations.sorted():

        decl = factory_class._meta.post_declarations.declarations[attr]

        if isinstance(decl, factory.RelatedFactory):
            deferred.append(make_deferred_related(factory_class, fixture_name, attr))
        else:
            argname = "".join((prefix, attr))
            extra = {}
            for k, v in factory_class._meta.post_declarations.contexts[attr].items():
                if k == "":
                    continue
                post_attr = SEPARATOR.join((argname, k))

                if post_attr in request._fixturedef.argnames:
                    extra[k] = evaluate(request, request.getfixturevalue(post_attr))
                else:
                    extra[k] = v
            # Handle special case for ``PostGenerationMethodCall`` where
            # `attr_fixture` value is equal to ``NotProvided``, which mean
            # that `value_provided` should be falsy
            postgen_value = evaluate(request, request.getfixturevalue(argname))
            postgen_context = PostGenerationContext(
                value_provided=(postgen_value is not factory.declarations.NotProvided),
                value=postgen_value,
                extra=extra,
            )
            deferred.append(
                make_deferred_postgen(step, factory_class, fixture_name, instance, attr, decl, postgen_context)
            )
    factoryboy_request.defer(deferred)

    # Try to evaluate as much post-generation dependencies as possible.
    # This will finally invoke Factory._after_postgeneration, which was previously disabled
    factoryboy_request.evaluate(request)
    return instance


def make_deferred_related(factory: FactoryType, fixture: str, attr: str) -> DeferredFunction:
    """Make deferred function for the related factory declaration.

    :param factory: Factory class.
    :param fixture: Object fixture name e.g. "book".
    :param attr: Declaration attribute name e.g. "publications".

    :note: Deferred function name results in "book__publication".
    """
    name = SEPARATOR.join((fixture, attr))

    def deferred_impl(request: SubRequest) -> Any:
        return request.getfixturevalue(name)

    return DeferredFunction(
        name=name,
        factory=factory,
        is_related=True,
        function=deferred_impl,
    )


def make_deferred_postgen(
    step: factory.builder.BuildStep,
    factory_class: FactoryType,
    fixture: str,
    instance: Any,
    attr: str,
    declaration: factory.declarations.PostGenerationDeclaration,
    context: PostGenerationContext,
) -> DeferredFunction:
    """Make deferred function for the post-generation declaration.

    :param step: factory_boy builder step.
    :param factory_class: Factory class.
    :param fixture: Object fixture name e.g. "author".
    :param instance: Parent object instance.
    :param attr: Declaration attribute name e.g. "register_user".
    :param declaration: Post-generation declaration.
    :param context: Post-generation declaration context.

    :note: Deferred function name results in "author__register_user".
    """
    name = SEPARATOR.join((fixture, attr))

    def deferred_impl(request: SubRequest) -> Any:
        return declaration.call(instance, step, context)

    return DeferredFunction(
        name=name,
        factory=factory_class,
        is_related=False,
        function=deferred_impl,
    )


def factory_fixture(request: SubRequest, factory_class: F) -> F:
    """Factory fixture implementation."""
    return factory_class


def attr_fixture(request: SubRequest, value: T) -> T:
    """Attribute fixture implementation."""
    return value


def subfactory_fixture(request: SubRequest, factory_class: FactoryType) -> Any:
    """SubFactory/RelatedFactory fixture implementation."""
    fixture = inflection.underscore(factory_class._meta.model.__name__)
    return request.getfixturevalue(fixture)


def get_caller_locals(depth: int = 0) -> dict[str, Any]:
    """Get the local namespace of the caller frame."""
    return sys._getframe(depth + 2).f_locals


class LazyFixture(Generic[T]):
    """Lazy fixture."""

    def __init__(self, fixture: Callable[..., T] | str) -> None:
        """Lazy pytest fixture wrapper.

        :param fixture: Fixture name or callable with dependencies.
        """
        self.fixture = fixture
        if callable(self.fixture):
            params = signature(self.fixture).parameters.values()
            self.args = [param.name for param in params if param.kind == param.POSITIONAL_OR_KEYWORD]
        else:
            self.args = [self.fixture]

    def evaluate(self, request: SubRequest) -> T:
        """Evaluate the lazy fixture.

        :param request: pytest request object.
        :return: evaluated fixture.
        """
        if callable(self.fixture):
            kwargs = {arg: request.getfixturevalue(arg) for arg in self.args}
            return self.fixture(**kwargs)
        else:
            return cast(T, request.getfixturevalue(self.fixture))
