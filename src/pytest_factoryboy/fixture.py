"""Factory boy fixture integration.

Architecture overview:
----------------------
``pytest-factoryboy`` bridges ``pytest`` fixtures with ``factory_boy`` factories across three main phases:

1. Registration Phase (``register``):
   When registering a factory (e.g. ``register(AuthorFactory, "author")``), it dynamically
   defines and injects pytest fixtures into the caller's module.
   Roughly equivalent to writing by hand:

   .. code-block:: python

       class AuthorFactory(factory.Factory):
           class Meta:
               model = Author

           name = "John Doe"
           ...  # other fields

       @pytest.fixture
       def author_factory():
           return AuthorFactory

       @pytest.fixture
       def author__name():
           return AuthorFactory.name  # "John Doe"

       ...  # one attribute fixture per factory declaration

       @pytest.fixture
       def author(request, author_factory, author__name):
           return model_fixture(request, "author_factory")

2. Resolution & Instantiation Phase (``model_fixture``):
   When a test requests the model fixture (e.g. ``def test_something(author):``):
   - Resolves the attribute fixtures, applying any user overrides.
   - Instantiates the model using the underlying factory.

3. Post-Generation Phase:
   - Executes post-generation hooks and builds related factory models in dependency order.
"""

from __future__ import annotations

import contextlib
import functools
import sys
from collections.abc import (
    Callable,
    Collection,
    Iterable,
    Iterator,
    Mapping,
    MutableMapping,
)
from dataclasses import dataclass
from inspect import signature
from types import MethodType
from typing import TYPE_CHECKING, Generic, TypeVar, cast, overload

import factory
import factory.enums
import inflection
from factory.base import Factory
from factory.builder import BuildStep, DeclarationSet, StepBuilder
from factory.declarations import (
    NotProvided,
    PostGeneration,
    PostGenerationDeclaration,
    PostGenerationMethodCall,
    RelatedFactory,
    SubFactory,
)
from typing_extensions import ParamSpec

from .compat import PostGenerationContext
from .engine import (
    UNSET,
    Unset,
    bind_factory,
    default_fixture,
    defaults_for,
    original_factory,
    record_default_fixtures,
    recorded_fixture,
)
from .fixturegen import create_fixture

if TYPE_CHECKING:
    from _pytest.fixtures import SubRequest

    from .plugin import Request as FactoryboyRequest

T = TypeVar("T")
U = TypeVar("U")
T_co = TypeVar("T_co", covariant=True)
P = ParamSpec("P")

SEPARATOR = "__"


@dataclass(eq=False)
class DeferredFunction(Generic[T, U]):
    name: str
    factory: type[Factory[T]]
    is_related: bool
    function: Callable[[SubRequest], U]

    def __call__(self, request: SubRequest) -> U:
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
# class AuthorFactory(Factory): ...
@overload
def register(
    factory_class: type[Factory[T]],
    _name: str | None = ...,
    *,
    _caller_locals: Box[MutableMapping[str, object]] | None = ...,
    **kwargs: object,
) -> type[Factory[T]]: ...


# @register(...)
# class AuthorFactory(Factory): ...
@overload
def register(
    factory_class: None,
    _name: str | None = ...,
    *,
    _caller_locals: Box[MutableMapping[str, object]] | None = ...,
    **kwargs: object,
) -> Callable[[type[Factory[T]]], type[Factory[T]]]: ...


def register(
    factory_class: type[Factory[T]] | None = None,
    _name: str | None = None,
    *,
    _caller_locals: Box[MutableMapping[str, object]] | None = None,
    **kwargs: object,
) -> type[Factory[T]] | Callable[[type[Factory[T]]], type[Factory[T]]]:
    r"""Register fixtures for the factory class.

    :param factory_class: Factory class to register.
    :param _name: Name of the model fixture. By default, is lowercase-underscored model name.
        It is also the default fixture a ``SubFactory``/``RelatedFactory`` to this factory shares.
    :param _caller_locals: Mutable mapping where to inject the generated fixtures. Defaults to the caller's locals().
    :param \**kwargs: Optional keyword arguments that override factory attributes.
    """
    if _caller_locals is None:
        _caller_locals = Box(get_caller_locals())

    if factory_class is None:

        def register_(factory_class: type[Factory[T]]) -> type[Factory[T]]:
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

    # ``model_name`` is the default fixture a SubFactory/RelatedFactory to this factory
    # shares, unless ``register_factory`` already recorded another setting for the kind.
    record_default_fixtures(factory_class, model_name=model_name, subfactory=model_name, relatedfactory=model_name)

    # The model attributes default to the factory namespace, so the whole factory
    # namespace must exist. ``register_factory`` only adds the missing names, so calling
    # it here is safe even when the user already provides a ``foo_factory`` fixture.
    factory_fixture_names = {
        factory_name,
        *(SEPARATOR.join((factory_name, attr)) for attr in factory_class._meta.declarations),
    }
    if not factory_fixture_names <= set(_caller_locals.value):
        register_factory(factory_class, _caller_locals=_caller_locals)

    fixture_defs = dict(
        generate_model_fixtures(
            factory_class=factory_class,
            model_name=model_name,
            factory_name=factory_name,
            overrides=kwargs,
        )
    )
    for name, fixture in fixture_defs.items():
        inject_into_caller(name, fixture, _caller_locals)

    return factory_class


def register_factory(
    factory_class: type[Factory[T]],
    *,
    _default_subfactory_fixture: str | None | Unset = UNSET,
    _default_relatedfactory_fixture: str | None | Unset = UNSET,
    _caller_locals: Box[MutableMapping[str, object]] | None = None,
    **overrides: object,
) -> type[Factory[T]]:
    r"""Register the factory fixture, and its attribute namespace, for the factory class.

    Registers ``foo_factory`` and ``foo_factory__<attr>``. Can be used on its own (no
    model fixture is required). Only adds fixture names that do not exist yet, so **call
    it before** :func:`register` for the same factory; if there is nothing left to
    register, it raises.

    :param factory_class: Factory class to register.
    :param _default_subfactory_fixture: Fixture a ``SubFactory`` to this factory shares, or ``None`` to build a new object. Defaults to what :func:`register` records.
    :param _default_relatedfactory_fixture: Same, for a ``RelatedFactory``.
    :param _caller_locals: Mutable mapping where to inject the generated fixtures. Defaults to the caller's locals().
    :param \**overrides: Optional keyword arguments that override factory attributes.
    """
    if _caller_locals is None:
        _caller_locals = Box(get_caller_locals())

    assert not factory_class._meta.abstract, "Can't register abstract factories."
    assert factory_class._meta.model is not None, "Factory model class is not specified."

    # Recorded even if the fixtures already exist, so an explicit setting is honored
    # regardless of the order of registrations (first writer still wins).
    record_default_fixtures(
        factory_class,
        subfactory=_default_subfactory_fixture,
        relatedfactory=_default_relatedfactory_fixture,
    )

    factory_name = get_factory_name(factory_class)

    fixture_defs = {
        name: fixture
        for name, fixture in generate_factory_fixtures(
            factory_class=factory_class,
            factory_name=factory_name,
            overrides=overrides,
        )
        if name not in _caller_locals.value
    }
    if not fixture_defs:
        raise ValueError(f"{factory_name!r} is already registered: nothing to register.")
    for name, fixture in fixture_defs.items():
        inject_into_caller(name, fixture, _caller_locals)

    return factory_class


def generate_factory_fixtures(
    factory_class: type[Factory[T]],
    factory_name: str,
    overrides: Mapping[str, object],
) -> Iterable[tuple[str, Callable[..., object]]]:
    """Generate the factory fixture and its attribute namespace."""
    attr_names: list[str] = []
    for attr, value in factory_class._meta.declarations.items():
        value = overrides.get(attr, value)
        attr_name = SEPARATOR.join((factory_name, attr))
        attr_names.append(attr_name)
        yield attr_name, make_factory_attr_fixturedef(attr_name, value)

    yield (
        factory_name,
        create_fixture_with_related(
            name=factory_name,
            function=functools.partial(
                factory_fixture,
                factory_class=factory_class,
                factory_name=factory_name,
            ),
            # The factory fixture depends on its whole namespace so that parametrizing
            # ``foo_factory__<attr>`` is part of its closure.
            dependencies=attr_names,
            # Shareable sub-factory targets are resolved lazily, so their attribute
            # fixtures are requested separately — to keep parametrizing them working.
            related=shareable_target_fixtures(factory_class, overrides),
        ),
    )


def shareable_target_fixtures(
    factory_class: type[Factory[T]],
    overrides: Mapping[str, object],
) -> list[str]:
    """Fixture names a shared ``SubFactory`` target makes parametrizable.

    The target is resolved at call time, so it is not part of the factory fixture's
    static closure; requesting the factory fixture must still make the target's attribute
    fixtures part of the test's, or ``@parametrize("author__name")`` fails collection
    (see ``specs/factory-fixtures.md`` §4.1).
    """
    names: list[str] = []
    declarations = factory_class._meta.declarations
    for attr in factory_class._meta.pre_declarations:
        declaration = declarations[attr]
        if attr in overrides or not isinstance(declaration, SubFactory):
            continue
        target = recorded_fixture(declaration, related=False)
        if not isinstance(target, str):
            # Not registered, or explicitly opted out: nothing to parametrize.
            continue
        names.extend(target_attribute_fixtures(declaration.get_factory(), target))
    return names


def target_attribute_fixtures(factory_class: type[Factory[T]], fixture: str) -> list[str]:
    """Attribute fixtures of a shared target that are safe to request eagerly."""
    defaults = defaults_for(factory_class)
    if defaults is None or defaults.model_name != fixture:
        # The shared fixture is not the target's model fixture (a hand-written fixture,
        # or a target registered under another name): no namespace applies to it.
        return []

    names = [SEPARATOR.join((get_factory_name(factory_class), attr)) for attr in factory_class._meta.declarations]
    # Sub/related attributes are skipped: requesting them would create objects even for
    # ``.build()``.
    names.extend(
        SEPARATOR.join((fixture, attr))
        for attr, declaration in factory_class._meta.declarations.items()
        if not isinstance(declaration, (SubFactory, RelatedFactory))
    )
    return names


def generate_model_fixtures(
    factory_class: type[Factory[T]],
    model_name: str,
    factory_name: str,
    overrides: Mapping[str, object],
) -> Iterable[tuple[str, Callable[..., object]]]:
    """Generate the model fixture and its attribute namespace."""
    related: list[str] = []
    for attr, declaration in factory_class._meta.declarations.items():
        value = overrides.get(attr, declaration)
        attr_name = SEPARATOR.join((model_name, attr))
        factory_attr_name = SEPARATOR.join((factory_name, attr))
        yield (
            attr_name,
            make_declaration_fixturedef(
                attr_name=attr_name,
                value=value,
                declaration=declaration,
                factory_class=factory_class,
                related=related,
                factory_attr_name=factory_attr_name,
            ),
        )

    deps = get_deps(factory_class, model_name=model_name)
    yield (
        model_name,
        create_fixture_with_related(
            name=model_name,
            function=functools.partial(model_fixture, factory_name=factory_name),
            dependencies=deps,
            related=related,
        ),
    )


def create_fixture_with_related(
    name: str,
    function: Callable[P, T],
    dependencies: Collection[str] | None = None,
    related: Collection[str] | None = None,
) -> Callable[P, T]:
    if related is None:
        related = []
    fixture, fn = create_fixture(name=name, function=function, dependencies=dependencies)

    # We have to set the `_factoryboy_related` attribute to the original function, since
    # FixtureDef.func will provide that one later when we discover the related fixtures.
    fn._factoryboy_related = related  # type: ignore[attr-defined]
    return fixture


def make_declaration_fixturedef(
    attr_name: str,
    value: object,
    declaration: object,
    factory_class: type[Factory[T]],
    related: list[str],
    factory_attr_name: str,
) -> Callable[[SubRequest], object]:
    """Create the FixtureDef for a factory declaration.

    A plain attribute defaults to the factory namespace (``factory_attr_name``) when it
    was not overridden in the model namespace.
    """
    if isinstance(value, (SubFactory, RelatedFactory)):
        is_related = isinstance(value, RelatedFactory)
        target = default_fixture(value, related=is_related)
        if target is not None:
            subfactory_class: type[Factory[object]] = value.get_factory()
            if target == registered_model_name(subfactory_class):
                # The shared fixture is the target's model fixture, so the target's
                # namespace applies to it.
                subfactory_deps = get_deps(subfactory_class, factory_class, model_name=target)
            else:
                # A hand-written fixture (or a target registered under another name):
                # only the fixture itself is involved.
                subfactory_deps = []

            args = list(subfactory_deps)
            if is_related:
                args.append(target)
                related.append(target)
                related.append(attr_name)
                related.extend(subfactory_deps)
            else:
                args.append(target)

            return create_fixture_with_related(
                name=attr_name,
                function=functools.partial(subfactory_fixture, fixture=target),
                dependencies=args,
            )
        # ``None``: build a new object instead of sharing one — factory_boy evaluates the
        # declaration, like any other attribute (see ``specs/factory-fixtures.md`` §4.1).

    # A plain attribute defaults to the factory namespace.
    deps: list[str] = [factory_attr_name]
    if isinstance(value, PostGeneration):
        value = None
    elif isinstance(value, PostGenerationMethodCall):
        value = value.method_arg
    elif isinstance(value, LazyFixture):
        deps.extend(value.args)

    return create_fixture_with_related(
        name=attr_name,
        function=functools.partial(
            model_attr_fixture, value=value, declaration=declaration, factory_attr_name=factory_attr_name
        ),
        dependencies=deps,
    )


def make_factory_attr_fixturedef(attr_name: str, value: object) -> Callable[[SubRequest], object]:
    """Create the FixtureDef for a factory attribute in the factory namespace.

    Unlike :func:`make_declaration_fixturedef`, a sub-factory declaration stays the
    declaration object and a ``LazyFixture`` stays lazy — the engine skips an untouched
    declaration and resolves a ``LazyFixture`` at call time — so this fixture
    deliberately has no dependencies.
    """
    if isinstance(value, PostGeneration):
        value = None
    elif isinstance(value, PostGenerationMethodCall):
        value = value.method_arg

    return create_fixture_with_related(
        name=attr_name,
        function=functools.partial(attr_fixture, value=value),
    )


def inject_into_caller(name: str, function: Callable[..., object], locals_: Box[MutableMapping[str, object]]) -> None:
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


def get_model_name(factory_class: type[Factory[T]]) -> str:
    """Get model fixture name by factory."""
    model_cls = factory_class._meta.model

    if isinstance(model_cls, str):
        return model_cls

    return inflection.underscore(model_cls.__name__)


def get_factory_name(factory_class: type[Factory[T]]) -> str:
    """Get factory fixture name by factory."""
    return inflection.underscore(factory_class.__name__)


def registered_model_name(factory_class: type[Factory[T]]) -> str:
    """Get the model fixture name a registration recorded, or the inflected one."""
    defaults = defaults_for(factory_class)
    if defaults is not None and defaults.model_name is not None:
        return defaults.model_name
    return get_model_name(factory_class)


def get_deps(
    factory_class: type[Factory[T]],
    parent_factory_class: type[Factory[U]] | None = None,
    model_name: str | None = None,
) -> list[str]:
    """Get factory dependencies.

    :return: List of the fixture argument names for dependency injection.
    """
    model_name = get_model_name(factory_class) if model_name is None else model_name
    parent_model_name = get_model_name(parent_factory_class) if parent_factory_class is not None else None

    def is_dep(value: object) -> bool:
        if isinstance(value, RelatedFactory):
            return False
        if isinstance(value, SubFactory):
            subfactory_class: type[Factory[object]] = value.get_factory()
            if get_model_name(subfactory_class) == parent_model_name:
                return False
        if isinstance(value, PostGenerationDeclaration):
            # Dependency on extracted value
            return True

        return True

    return [
        SEPARATOR.join((model_name, attr)) for attr, value in factory_class._meta.declarations.items() if is_dep(value)
    ]


def evaluate(request: SubRequest, value: LazyFixture[T] | T) -> T:
    """Evaluate the declaration (lazy fixtures, etc)."""
    return value.evaluate(request) if isinstance(value, LazyFixture) else value


def noop(*args: object, **kwargs: object) -> None:
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


def model_fixture(request: SubRequest, factory_name: str) -> object:
    """Instantiate the model for a requested model fixture.

    Resolves attribute fixtures (applying explicit overrides while preserving factory
    defaults), instantiates the model with post-generation hooks deferred, and returns
    the evaluated model instance.

    :param request: Pytest sub-request for fixture resolution.
    :param factory_name: Name of the factory fixture.
    :return: Instantiated model object.
    """
    factoryboy_request: FactoryboyRequest = request.getfixturevalue("factoryboy_request")

    # Try to evaluate as much post-generation dependencies as possible
    factoryboy_request.evaluate(request)

    assert request.fixturename  # NOTE: satisfy mypy
    fixture_name = request.fixturename
    prefix = "".join((fixture_name, SEPARATOR))

    factory_class: type[Factory[object]] = request.getfixturevalue(factory_name)
    # ``factory_fixture`` returns a request-bound subclass; the model fixture builds from
    # the original factory, bypassing the engine hook (the model fixture resolves
    # sub-factories and post-generation itself).
    factory_class = original_factory(factory_class)

    # create Factory override for the model fixture
    NewFactory: type[Factory[object]] = type("Factory", (factory_class,), {})
    # equivalent to:
    # class Factory(factory_class):
    #     pass
    # NewFactory = Factory
    # del Factory

    # it just makes mypy understand it.

    NewFactory._meta.base_declarations = {
        k: v for k, v in NewFactory._meta.base_declarations.items() if not isinstance(v, PostGenerationDeclaration)
    }
    NewFactory._meta.post_declarations = DeclarationSet()

    # Collect keyword arguments for pre-declarations from their corresponding attribute fixtures (e.g. "user__password").
    # By default, generated attribute fixtures return the factory's own declaration object unless overridden by
    # a fixture or register(...) argument.
    kwargs = {}
    for key in factory_class._meta.pre_declarations:
        argname = "".join((prefix, key))
        if argname not in request._fixturedef.argnames:
            continue
        value = evaluate(request, request.getfixturevalue(argname))
        if value is factory_class._meta.pre_declarations[key].declaration:
            # The fixture still holds the factory's own declaration object, meaning
            # neither namespace was set. We omit it from kwargs so factory_boy can
            # evaluate the declaration natively as a default.
            #
            # Passing the declaration back in kwargs would cause factory_boy to treat it
            # as an explicit call-time override. For declarations that capture/transform
            # overrides (e.g. ``factory.Transformer``), treating the declaration as an
            # override causes the transformation to be applied twice: once when
            # evaluating the override argument, and once by the declaration itself.
            continue
        kwargs[key] = value

    strategy = factory.enums.CREATE_STRATEGY
    builder = StepBuilder(NewFactory._meta, kwargs, strategy)
    step = BuildStep(builder=builder, sequence=NewFactory._meta.next_sequence())

    # FactoryBoy invokes the `_after_postgeneration` method, but we will instead call it manually later,
    # once we are able to evaluate all the related fixtures.
    with disable_method(NewFactory._after_postgeneration):  # type: ignore[arg-type]  # https://github.com/python/mypy/issues/14235
        instance = NewFactory(**kwargs)

    # Cache the instance value on pytest level so that the fixture can be resolved before the return
    request._fixturedef.cached_result = (instance, 0, None)
    request._fixture_defs[fixture_name] = request._fixturedef

    # Defer post-generation declarations
    deferred: list[DeferredFunction[object, object]] = []

    for attr in factory_class._meta.post_declarations.sorted():
        decl = factory_class._meta.post_declarations.declarations[attr]

        if isinstance(decl, RelatedFactory) and recorded_fixture(decl, related=True) is not None:
            # Share the target fixture: the attribute fixture already depends on it. A
            # registration can opt out with ``_default_relatedfactory_fixture=None``; the
            # declaration is then evaluated by factory_boy, like a post-generation one.
            deferred.append(make_deferred_related(factory_class, fixture_name, attr))
            continue

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
            value_provided=(postgen_value is not NotProvided and postgen_value is not decl),
            value=postgen_value,
            extra=extra,
        )
        deferred.append(make_deferred_postgen(step, factory_class, fixture_name, instance, attr, decl, postgen_context))
    factoryboy_request.defer(deferred)

    # Try to evaluate as much post-generation dependencies as possible.
    # This will finally invoke Factory._after_postgeneration, which was previously disabled
    factoryboy_request.evaluate(request)
    return instance


def make_deferred_related(factory: type[Factory[T]], fixture: str, attr: str) -> DeferredFunction[T, object]:
    """Make deferred function for the related factory declaration.

    :param factory: Factory class.
    :param fixture: Object fixture name e.g. "book".
    :param attr: Declaration attribute name e.g. "publications".

    :note: Deferred function name results in "book__publication".
    """
    name = SEPARATOR.join((fixture, attr))

    def deferred_impl(request: SubRequest) -> object:
        return request.getfixturevalue(name)

    return DeferredFunction(
        name=name,
        factory=factory,
        is_related=True,
        function=deferred_impl,
    )


def make_deferred_postgen(
    step: BuildStep,
    factory_class: type[Factory[T]],
    fixture: str,
    instance: T,
    attr: str,
    declaration: PostGenerationDeclaration,
    context: PostGenerationContext,
) -> DeferredFunction[T, object]:
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

    def deferred_impl(request: SubRequest) -> object:
        return declaration.call(instance, step, context)

    return DeferredFunction(
        name=name,
        factory=factory_class,
        is_related=False,
        function=deferred_impl,
    )


def factory_fixture(
    request: SubRequest,
    factory_class: type[Factory[T]],
    factory_name: str,
) -> type[Factory[T]]:
    """Factory fixture implementation.

    Returns a request-bound subclass of the user's factory, wired to the generation
    engine (see :mod:`pytest_factoryboy.engine`).
    """
    return bind_factory(factory_class, request, factory_name)


def attr_fixture(request: SubRequest, value: T) -> T:
    """Attribute fixture implementation."""
    return value


def model_attr_fixture(request: SubRequest, value: object, declaration: object, factory_attr_name: str) -> object:
    """Model attribute fixture implementation.

    Defaults to the factory namespace when the model namespace was not overridden.
    """
    if value is declaration:
        return request.getfixturevalue(factory_attr_name)
    return value


def subfactory_fixture(request: SubRequest, fixture: str) -> object:
    """SubFactory/RelatedFactory fixture implementation: return the shared fixture."""
    return request.getfixturevalue(fixture)


def get_caller_locals(depth: int = 0) -> MutableMapping[str, object]:
    """Get the local namespace of the caller frame."""
    # In Python 3.15+, `frame.f_locals` is typed as `FrameLocalsProxyType | dict[str, Any]`.
    # `FrameLocalsProxyType` is not a `dict` subclass, but it implements the mutable mapping
    # protocol, so the return type is modelled as `MutableMapping` and the cast is safe.
    return cast(MutableMapping[str, object], sys._getframe(depth + 2).f_locals)


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
