# pytest-factoryboy — Factory-anchored fixtures

**Status:** design spec, targeting the next major release.
**Branch:** `rethink-factory-fixtures` (based on `master`).
**Stance:** prefer deprecations over hard breaks; existing
`@pytest.mark.parametrize("foo__field", ...)` must keep working. A minimum-version
bump is acceptable (see §7).

## Summary

Today the **model fixture** is the plugin's anchor and the **factory fixture is
vestigial** — `foo_factory` *is* the factory class, so it is not bound to the test and
cannot honor the test's setup. This spec makes the factory fixture first-class:

- `foo_factory` becomes a **callable dynamic subclass** of the user's factory, bound
  to the test's request.
- It has its **own namespace** (`foo_factory__<attr>`) and honors that namespace plus
  per-call overrides, so objects can be created **on demand** — in a test body, inside
  `transaction.atomic()`, under a decorator — instead of at fixture-setup time.
- Each call creates a **new** instance; *shareable* sub-factories remain shared.
- Sub/related factories resolve by **factory identity**, which removes the need for
  `named_model` (follow-up — see §5).

```python
@pytest.mark.parametrize("book_factory__name", ["bar"])
def test_create_later(book_factory):   # request only the factory
    book = book_factory()              # create on demand
    assert book.name == "bar"          # the factory's parametrization is honored
```

---

## 1. Problem statement

### 1.1 Where we are

| fixture | name | what it is today |
| --- | --- | --- |
| model | `foo` | eager, cached instance |
| factory | `foo_factory` | **the raw factory class** |
| attribute | `foo__<attr>` | declaration / override value |
| post-gen context | `foo__<postgen>__<key>` | extracted post-gen kwarg |

The model fixture is eager: `foo` creates the object during fixture setup, so by the
time the test body runs, the object already exists. There is no first-class way to
say "create it when I ask".

### 1.2 Concrete problems (verified on `master`)

1. **The factory fixture is not bound to the request.** `book_factory` literally *is*
   `BookFactory`; it has no attribute fixtures, so nothing the test sets up (fixtures,
   `parametrize`) can reach it. Calling it just calls the raw class.
2. **Sub-factory divergence.** `book.author is author` is `True`, but
   `book_factory().author is author` is `False`; the factory path ignores
   `author__name`.
3. **Sub/related resolution is by _model name_**, which forces `named_model` and
   breaks same-model factories (#218), subclassed sub-factories (#257) and
   self-references (#94).
4. **`@register` resolves `SubFactory` at decoration time**, so mutually referencing
   factories fail at import (#82).
5. **Declarations are replaced, not evaluated**, losing `SubFactory(X, a=...)` and
   parent-relative `SelfAttribute` (#263, #40).

---

## 2. Proposed change

Anchor on the **factory fixture**. `foo_factory` is a callable dynamic subclass of the
user's factory, bound to the pytest request, with its own override namespace. Each call
produces a fresh instance.

### 2.1 What an end user writes

```python
# Convention: register the factory first, then the model fixtures.
register_factory(BookFactory, name="Factory Name")   # book_factory + book_factory__<attr>

register(AuthorFactory)
register(BookFactory)                    # book (book_factory is already registered)
register(BookFactory, "second_book")     # second_book


# (1) The model fixture
@pytest.mark.parametrize("book__name", ["PyTest for Dummies"])
def test_model(book):
    assert book.name == "PyTest for Dummies"


# (2) The factory fixture, and its own parametrization
@pytest.mark.parametrize("book_factory__name", ["PyTest for Dummies"])
def test_factory_honors_parametrization(book_factory):
    assert book_factory().name == "PyTest for Dummies"        # factory param applied
    assert book_factory(name="override").name == "override"   # per-call wins


# (3) Fresh instance per call; a shareable sub-factory is shared
def test_instance_identity(book, author, book_factory):
    b1, b2 = book_factory(), book_factory()
    assert b1 is not b2                        # distinct books per call
    assert b1 is not book and b2 is not book   # ... and not the model instance
    assert b1.author is b2.author is author    # shared author
    assert book.author is author               # model fixture shares it too


# (4) Deferred creation inside a transaction / context manager
@pytest.mark.django_db(transactional=True)
def test_within_atomic(book_factory):
    with transaction.atomic():
        book = book_factory()


# (5) Registrations keep their own namespaces (no leakage)
@pytest.mark.parametrize("second_book__name", ["Mr. Hyde"])
def test_second_book_is_isolated(book, second_book, book_factory):
    assert second_book.name == "Mr. Hyde"          # second_book's param
    assert book.name == "Factory Name"             # book inherits the factory default
    assert book_factory().name == "Factory Name"   # factory default


# (6) The factory namespace feeds the factory, and the model by default
@pytest.mark.parametrize("book_factory__name", ["Factory Param"])
def test_factory_namespace(book, book_factory):
    assert book_factory().name == "Factory Param"
    assert book.name == "Factory Param"   # book__name defaults to book_factory__name


# (7) Both namespaces set: the model reads its own first
@pytest.mark.parametrize("book__name", ["Model Name"])
@pytest.mark.parametrize("book_factory__name", ["Factory Param"])
def test_both_namespaces(book, second_book, book_factory):
    assert book.name == "Model Name"            # model override wins
    assert second_book.name == "Factory Param"  # no own override -> factory default
    assert book_factory().name == "Factory Param"


# (8) Batch building through the factory
def test_build_batch(book_factory):
    batch = book_factory.build_batch(size=3)   # 3 un-persisted books
    assert all(b.name == "Factory Name" for b in batch)
```

### 2.2 Before / after

| Usage | Today | After |
| --- | --- | --- |
| `@parametrize("book_factory__name", [..])` + `book_factory` | not a fixture / ignored | `book_factory().name` honors it |
| `book_factory is BookFactory` | `True` | `issubclass(book_factory, BookFactory)` |
| `book_factory().author` | fresh instance | shares the `author` fixture (if shareable) |
| SubFactory of a subclassed factory (#257) | wrong fixture | resolves by factory identity *(follow-up F1)* |
| Two factories sharing a model name (#218) | fixture collision | distinct fixtures *(follow-up F1)* |
| `dict`/`list` model (#225) | needs `named_model` | factory-anchored *(follow-up F1)* |
| `SubFactory(F, c=SelfAttribute("..a"))` (#263) | args dropped | preserved *(follow-up F2)* |
| Mutually-referencing factories under `@register` (#82) | import error | deferred resolution *(follow-up F1)* |

---

## 3. Public API

### 3.1 Registration

`register` keeps its call form and gains a sibling that registers the factory on its
own:

```python
register_factory(BookFactory, name="Factory Name")  # factory first (convention)
register(BookFactory)                 # book (book_factory is already registered)
register(BookFactory, "second_book")  # second_book (shares book_factory)
register(BookFactory, price=1)        # book's overrides
```

- `register_factory(factory, *, _default_fixture=<unset>, **overrides)` registers the
  shared `foo_factory` and its namespace `foo_factory__<attr>`, and can be used alone
  (no model fixture required). It only adds fixture names that do not exist yet, so
  **call it before `register(...)` for the same factory**; if there is nothing left to
  register, it **raises**.
  - `_default_fixture="bar"` — the fixture that `SubFactory`s (and `RelatedFactory`s) to
    this factory share (§4.1). It applies to both kinds of reference, so it is named for
    the fixture, not for `SubFactory`.
  - `_default_fixture=None` — explicitly opts the factory into native sub-builds.
  - Omitted: left unset; a following `register(...)` sets it to the model fixture name.
- `register(factory, _name=None, **overrides)` registers the model fixtures `foo` /
  `foo__<attr>`, and records `_name` (or the inflected model name) as the factory's
  default fixture **unless one is already recorded** (§4.1). When `foo_factory` does not
  yet exist in the module, it also calls `register_factory(factory)` for you (with no
  factory-level overrides).

Because `register_factory` must run first, the convention is to list it before the
`register(...)` calls (see §2.1).

### 3.2 Fixtures

| fixture | created by | meaning |
| --- | --- | --- |
| `foo` | `register` | model fixture: eager, cached `foo_factory()` result |
| `foo_factory` | `register_factory` | callable dynamic subclass of `FooFactory` |
| `foo__<attr>` | `register` | the model's attribute / override |
| `foo_factory__<attr>` | `register_factory` | the factory's attribute / override |
| `foo__<postgen>__<key>` | `register` | a declaration named `<postgen>__<key>` |
| `foo_factory__<postgen>__<key>` | `register_factory` | the same declaration, factory-level |

The `<postgen>__<key>` fixtures are **not** a three-level lookup: the declaration is
literally named `<postgen>__<key>` (a post-generation context argument), and it is
supported today (e.g. `author__register_user__password`). Like every other attribute,
it exists in both namespaces.

### 3.3 Override resolution

`foo_factory` is independent of `foo`; `foo` defaults to the factory's values:

- **`foo`** (model): `foo__<attr>` → (its default) `foo_factory__<attr>` → declaration
  default.
- **`foo_factory()`** (factory): per-call kwargs → `foo_factory__<attr>` → declaration
  default.

`foo_factory` never reads `foo__<attr>` — the factory does not know about the model.
But `foo__<attr>` **defaults to** `foo_factory__<attr>`, so the model inherits the
factory's defaults and only needs its own namespace to override them. A namespace only
contributes when it has been *set*: an override was passed to
`register`/`register_factory`, or the fixture was parametrized.

Consequences:

- `@parametrize("foo_factory__attr")` configures the factory, and the model inherits it.
- `@parametrize("foo__attr")` configures the model only.
- `register_factory(Factory, name="A")` sets the default the model inherits;
  `register(Factory, name="B")` overrides it for the model:
  `foo.name == "B"`, `foo_factory().name == "A"`.
- Issue #223's deferred-creation goal is unchanged; its sketch uses
  `book_factory__name` for the factory.

### 3.4 Using the factory fixture

```python
def test(book_factory):
    a = book_factory()                        # CREATE one
    b = book_factory.build()                  # BUILD one
    c = book_factory.stub()                   # STUB one
    batch = book_factory.build_batch(size=3)  # BUILD many

    d = book_factory(name="x")                # per-call override
    e = book_factory(author__name="Ada")      # nested per-call override

    assert issubclass(book_factory, BookFactory)
```

`foo_factory` also works with decorators that expect a factory
(`factory.django.mute_signals(...)`, etc.).

### 3.5 API delta

**Added**

| New | What it is |
| --- | --- |
| `register_factory(factory, **overrides)` | Registers the shared `foo_factory` and its `foo_factory__<attr>` namespace. |
| callable `foo_factory` | A callable dynamic subclass of `FooFactory`. |
| `foo_factory(**overrides)` | Per-call attribute overrides. |
| `foo_factory.build_batch() / .build() / .create() / .stub()` | Strategy control. |
| `foo_factory__<attr>` | Factory-level attribute fixtures. |

**Changed**

| Aspect | Before | After |
| --- | --- | --- |
| `foo_factory` identity | the class `FooFactory` | a per-test subclass → use `issubclass(...)` |
| `foo_factory` parametrization | none | via `foo_factory__<attr>` |
| `foo_factory().sub` (shareable) | fresh instance | shares the `sub` fixture |
| `foo_factory()` post-generation | n/a (plain class) | deferred, parity with `foo` |
| `register(...)` | registers `foo` + `foo_factory` | same form; auto-calls `register_factory` when absent |
| minimum versions | `pytest>=7.0`, `factory_boy>=2.10` | `pytest>=9.1`, `factory_boy>=3.3` (§7) |

**Deprecated:** `named_model` (only at F1). Nothing is removed in the first PR; the
sub/related target lookup no longer guesses a fixture name — it uses the recorded
default fixture, or the user explicitly opts into native.

**Unchanged:** the `register(...)` call form; the model fixture names `foo`,
`foo__attr`; `@parametrize("foo__attr")` + `foo`.

---

## 4. Behavior specs

### 4.1 Sub-factory sharing (via the target's default fixture)

When the target factory has a **default fixture** registered, a `SubFactory` (or
`RelatedFactory`) to it **shares** that fixture automatically: `foo` and `foo_factory()`
then refer to the same object. Sharing is the automatic behaviour for any registered
target; what is opt-in is the *native* alternative (`_default_fixture=None`), and an
unset target raises.

No extra action is needed — a registered factory just does the right thing:

```python
def test(book, author, book_factory):
    # AuthorFactory is registered -> its default fixture `author` is shared
    assert book_factory().author is book.author is author
```

The default fixture is recorded at registration:

| registration | factory's default fixture |
| --- | --- |
| `register(Factory, name=None, **overrides)` | `name` (default: the inflected model name) |
| `register_factory(Factory, _default_fixture="bar")` | `bar` |
| `register_factory(Factory, _default_fixture=None)` | none — build natively |

This is not a runtime name lookup: the plugin materialises the binding as a fixture
`bar_factory___default_fixture` that depends on the named fixture *statically*
(`def bar_factory___default_fixture(bar): return bar`). A `SubFactory` / `RelatedFactory`
to the factory depends on that fixture, so the edge is a real one in the pytest graph
and can be overridden like any other fixture.

Resolving `SubFactory(TargetFactory)` — and `RelatedFactory(TargetFactory)`:

- **a fixture name** → inject it (shared);
- **`None`** → build **natively**: a new sub-object every time the factory is invoked
  (factory_boy's own behaviour), never the shared fixture;
- **unset** (the target is not registered, or was registered without a default) →
  **raise**, telling the user to register the target or pass `_default_fixture=None`.
  Building natively is therefore always explicit.

Other rules:

- **Extra arguments are ignored for a shared target** — `SubFactory(AuthorFactory,
  name="A")` still injects the `author` fixture, as it does today.
- **Parent-relative `SelfAttribute`** targets are not supported. (Today they are
  resolved through the inflected fixture with the attribute *dropped* — #263 — rather
  than built natively; the design does not attempt to support them.)
- **The default fixture is recorded once — first writer wins.** `register(...)` records
  the model name; an explicit `register_factory(..., _default_fixture=...)` records what
  it is given, including `None`. Later registrations do not change it. This is also how
  you opt a **registered** factory out of sharing: record native-ness first.

  ```python
  register_factory(BookFactory, _default_fixture=None)   # native sub-builds...
  register(BookFactory)                                  # ...but still provides `book`
  ```

- A registration can bind a `SubFactory` attribute to a specific fixture, e.g.
  `register(BookFactory, author=LazyFixture("another_author"))` (supported today).

**`RelatedFactory` shares the same way.** The target factory's default fixture decides
it, exactly as for `SubFactory` — `book` is shared into `author.book`. Sharing is most
useful when the related object is a single, known child you want to make parametrizable
and refer to by identity (`user.profile is profile`); note that a `RelatedFactory`
declaration generates exactly one child per call anyway, so this is no more restrictive
than factory_boy. What differs is **timing and wiring**, and the first PR does not change
them:

- A `RelatedFactory` is a post-generation declaration: the parent is built first and the
  related object is resolved afterwards, whereas a `SubFactory` is an ordinary
  dependency of the parent.
- The parent does **not** depend on the related attribute via the normal dependency
  graph (`get_deps` excludes it). Instead the target fixture is pulled in through the
  `related` list (`_factoryboy_related`) which `pytest_generate_tests` adds to
  `metafunc.fixturenames`, so requesting the parent also sets up the related fixture.
- Sharing only guarantees the target fixture is **created**. Whether the object is
  linked back onto the parent (e.g. `author.books == [book]`) is up to the model — a
  `__post_init__` that appends, or an `_after_postgeneration` hook. The `RelatedFactory`
  machinery itself is **not** run on the shared path (today the parent is built with its
  post-declarations stripped).

Today the model path already shares a related target but a direct `author_factory()`
call does not; the first PR makes the factory path match the model path, with
`_default_fixture=None` available to opt into native child creation instead.

**Why only for create.** Sharing injects an already-created object; `build()`/`stub()`
must not create rows, so they always build sub-objects themselves.

### 4.2 Deferred creation and post-generation

The deferred post-generation / cycle machinery is retained. One creation is created
once and post-generated once, with three scheduling cases:

- **Model fixture consumed during setup** → post-generation is deferred to the end of
  setup (as today).
- **Direct `foo_factory()` call** → post-generation for *that* creation runs
  synchronously before the call returns; an unresolved cycle raises a clear error
  rather than returning a half-built object.
- **A direct call that resolves another fixture** (e.g. a shared sub-factory) → that
  fixture is set up normally; only the creations owned by the call are drained.

Deferred work must not request new fixtures during teardown (a pytest 10 error), and
`_after_postgeneration` runs exactly once per creation.

### 4.3 Overrides are evaluated, not baked

An override must be handed to the factory **at call time** (`book_factory(name="x")`),
never written onto the subclass as a class attribute. A concrete example shows why:

```python
class BookFactory(factory.Factory):
    class Meta:
        model = Book
    author = factory.SubFactory(AuthorFactory)
    name = factory.SelfAttribute("author.name")   # computed at build time
```

`name`'s value is **not** a constant: it is derived from `author` when the object is
built. If we copied a resolved value onto the subclass as a class attribute, `name`
would become a fixed field and stop tracking `author`. Declarations such as
`SelfAttribute` and `Transformer` must stay declarations. Passing overrides as call
kwargs (and delegating the actual build to factory_boy) keeps them intact.

### 4.4 Scoping (follow-up)

Registration should ultimately use pytest's own scope machinery (module/class/package
resolution and shadowing) rather than a hand-rolled map. See §8 for the pytest
capability this depends on.

---

## 5. Delivery scope

Keep independent pieces independent. The **first PR** is the headline only:

- **In:** `register_factory`; the `foo_factory__<attr>` / `foo__<attr>` namespaces and
  their resolution (§3.3); a callable, factory-parametrized `foo_factory`; distinct
  instances per call; shareable sub-factory sharing; full deferred / cycle parity.
- **Follow-ups:**
  - **F1 — Factory-anchored identity resolution** (fixes #218/#257/#225): make the
    target registration mandatory (drop the deprecated inflection fallback), then
    deprecate `named_model`.
  - **F2 — Native evaluation** for non-shareable / unregistered `SubFactory`
    (#263/#40/#69).
  - **F3 — Scoping** via `pytest.register_fixture` (#81).
  - **F4 — Traits/Params/Maybe, model-only attributes, build fixtures.**

---

## 6. Design notes & constraints

Non-obvious constraints the implementation must respect. They are not part of the
public spec, but they explain several choices above.

**The factory fixture is a bound subclass.** `FooFactory` →
`type(name, (FooFactory,), {})`, with the request (and model name) bound under
underscore-prefixed attributes so factory_boy does not mistake them for declarations.

**Intercept `_generate`, not `create`/`build`.** Every entry point (`__call__`,
`create`, `build`, `stub`, `*_batch`, `generate`) funnels through
`BaseFactory._generate`. A re-entrancy guard on that single point covers all of them,
while overriding `create`/`build` individually is easily bypassed. This is an
independent, self-contained change and lands **first as a standalone pre-PR**
(see §11), separate from the fixture-generation work.

**The model fixture is routed through the same engine.** `model_fixture` must bypass
the `_generate` override (delegating to the native path) to avoid recursion. The engine
is strategy-parameterized so `.build()`/`.stub()` keep BUILD semantics.

**`Trait`/`Params` live in `_meta.parameters`, not `_meta.declarations`**, so they must
be forwarded to the builder explicitly. `LazyFixture` declarations still need engine
evaluation. `.attributes()` does not exist in factory_boy 3.3.x.

**Resolution uses an "unset" sentinel.** The `foo__<attr>` / `foo_factory__<attr>`
fixtures default to a sentinel when not explicitly overridden, so "was this namespace
set?" is decided without comparing values to declaration defaults.

---

## 7. Compatibility & migration

See §3.5 for the API delta; this section covers behavioral compatibility.

| Aspect | Today | Target | Strategy |
| --- | --- | --- | --- |
| `parametrize("foo__attr")` | `foo` only | still `foo` only | unchanged |
| `parametrize("foo_factory__attr")` | not available | factory, and the model's default | new |
| `foo_factory is FooFactory` | `True` | `False` (subclass) | migration guide; **unwarnable** |
| mutate attributes via `foo_factory` | persists | lost (bound subclass) | document loudly |
| `foo_factory().author` | fresh / native | shared **iff shareable** | document |
| `foo_factory()` post-generation timing | immediate | deferred engine | document |
| Sub/related target | by model-name inflection | by the target factory's recorded default fixture | unregistered/unset → raise; explicit `None` → native |
| `named_model` | required | unnecessary *after F1* | keep working; deprecate in F1 |
| generic-container `UserWarning` | on | maybe off | decide; keep `-Werror` tests aligned |
| fixture names | `foo`, `foo_factory`, `foo__attr` | unchanged | unchanged |
| `foo_factory` fixture deps | none | factory namespace + shareable sub-factories | document eager setup |
| minimum versions | `pytest>=7.0`, `factory_boy>=2.10` | `pytest>=9.1`, `factory_boy>=3.3` | next major |

Some changes are unwarnable (`is`-identity, attribute mutation), so a migration guide
is required. The minimum-version bump follows from wanting pytest's native fixture
registration (see §8) instead of the `inject_into_caller` shim.

---

## 8. Appendix — pytest capabilities researched (8.4 / 9.0 / 9.1)

| Capability | Version | Implication for us |
| --- | --- | --- |
| `pytest.register_fixture(name, func, node, scope, params, ids, autouse)` | 9.1 | Node-scoped imperative registration; replaces locals-mutation; enables scoping (#81) and programmatic params. Needs pre-item-collection timing. |
| `FixtureDef`, `FixtureRequest`, `FixtureLookupError`, `ScopeName` public | 9.1 | Build/inspect fixtures directly (`FixtureDef.execute`). |
| Fixture override resolution by **visibility** (more specific node wins; same visibility last-wins) | 9.1 (#14513) | Makes programmatic/namespace registration predictable across module/class scopes. |
| `request.fixturenames` includes fixtures requested transitively from overridden fixtures | 9.1.1 (#14248) | Helps compute/validate dynamic closures. |
| `_pytest.fixtures.traverse_fixture_closure(...)` (**private**) | 9.x | Static DFS dependency traversal; could replace parts of `get_deps` / `pytest_generate_tests`. May move. |
| `_resolve_args_directness`, `get_param_argkeys`, `strict_parametrization_ids` ini | 8.4 / 9.0 | Ensure unique generated IDs; understand direct vs indirect args. |
| `FixtureFunctionDefinition` (fixtures as objects) | 8.4 | `fixturedef.func` is an object; verify `_factoryboy_related` forwarding. |
| Subtests | 9.0 | Alternative to parametrization; not needed here. |

**Deprecations to avoid:** `baseid`/`nodeid` in fixture registration → use `node`
(#14004, removed in pytest 10); `FixtureDef.has_location`; `config.inicfg`;
`request.getfixturevalue()` **during teardown** → error in pytest 10 (#12882);
non-`Collection` `argvalues` (#13409); class-scoped instance-method fixtures (#10819).

**Timing:** `register_fixture` must run **before** item collection
(`pytest_pycollect_makeitem` / `pytest_collectstart` work;
`pytest_collection_modifyitems` is too late).

---

## 9. Appendix — factory_boy facts that constrain the design

- `SubFactory` stores extra arguments on **`_defaults`**; `RelatedFactory` has
  `.defaults`. Bareness checks must use the right attribute.
- All creation entry points funnel through `BaseFactory._generate`; `FactoryMetaClass`
  dispatches `__call__` to `create`/`build`/`stub`.
- `FactoryMetaClass` treats non-underscore class attributes as declarations — bind
  request/model-name under underscore-prefixed names.
- Overrides passed as class attributes turn `Transformer`/`SelfAttribute` into plain
  fields; pass them as call-time kwargs instead.
- `Trait`/`Params` live in `_meta.parameters`, not `_meta.declarations`.
- `PostGenerationContext` moved to `factory.declarations` in factory_boy 3.2 (the floor
  bump removes the old `factory.builder` import path).
- `.attributes()` does not exist in factory_boy 3.3.x.

---

## 10. Acceptance criteria

### First PR

- `@parametrize("foo_factory__attr")` + `def test(foo_factory)` →
  `foo_factory().attr == value` (request **only** `foo_factory`).
- `@parametrize("foo__attr")` does **not** affect `foo_factory()`; it still affects
  `foo`.
- `register_factory(Factory, **overrides)` registers a standalone `foo_factory`;
  `register(Factory, name=...)` auto-calls it when absent.
- Namespace resolution (examples 5–7): `foo_factory__<attr>` configures `foo_factory()`
  and is the default for `foo__<attr>`; `foo__<attr>` configures `foo` and overrides
  that default; `foo_factory()` never reads `foo__<attr>`.
- `register_factory(name="A")` + `register(name="B")` → `foo.name == "B"` but
  `foo_factory().name == "A"`.
- `second_book` isolation: `second_book__name` does not leak into `book` or
  `book_factory()`.
- `foo` vs `foo_factory()` parity for the core paths: pre-declaration, bare
  (shareable) `SubFactory`, post-generation, `RelatedFactory`.
- Two `foo_factory()` calls → two **distinct** books (also `is not` the `foo` model
  instance), but `foo_factory().author is foo_factory().author is foo.author` (hard).
- Bare `SubFactory` propagates `author__name` into `foo_factory()`.
- Sub/related target resolution: a registered target with a default fixture is shared;
  `_default_fixture=None` builds natively (fresh per call); an unset/unregistered
  target raises a clear error.
- `foo_factory(**overrides)` (including nested `author__name`) reaches the builder.
- `issubclass(foo_factory, FooFactory)` + `.create/.build/.build_batch/.stub` work;
  `.build()` keeps BUILD semantics.
- No cross-registration leakage: parametrizing one registration leaves another
  untouched.
- Exact-once `_after_postgeneration` for one call and for two calls.
- Nested parametrization: `parametrize("author__name")` with **only** `book_factory`
  requested.
- A genuine-cycle direct call raises a clear error.
- Strategy: `.build()`/`.stub()` under sharing (no create fixtures injected).
- Sequence continuity across two `foo_factory()` calls; repeated calls don't mutate the
  bound subclass `_meta` or double-strip post-declarations.
- `foo__<postgen>__<key>` / `foo_factory__<postgen>__<key>` remain supported declaration
  fixtures (`author__register_user__password`).
- A `SubFactory` to an unregistered target falls back to model-name inflection and
  emits a `DeprecationWarning`.
- `--fixtures` smoke test; mypy for the new `_generate` hook.

### Later PRs (add now, marked `xfail`/`skip`)

- SubFactory-with-kwargs / parent-relative target evaluates natively and preserves args
  (#263/#40) — **F2**.
- Unregistered / unset `SubFactory` target raises (native only when explicitly requested
  via `_default_fixture=None`) — native build path is **F2**.
- Shareable-looking SubFactory whose target references its parent → native, no error —
  **F2**.
- `named_model` emits `DeprecationWarning` and still works — **F1**.
- Same-named factories in different classes resolve SubFactory by identity
  (#257/#218) — **F1**.
- #94 self-reference rule; #82 decorator + forward-ref ordering — **F1**.
- Scoping: `test_namespaces.py` green and same-named factories resolve correctly —
  **F3**.

---

## 11. Implementation plan

### First PR (the headline)

1. **Parity harness.** Port the `deferred-factory` spike onto `master`; add the §10
   tests, marked `xfail`/`skip` while parity is pending.
2. **`_generate` override hook** (standalone pre-PR). The re-entrancy-guarded
   interception plus direct tests; merges on its own.
3. **Factory fixture as a bound subclass.** `factory_fixture` returns a subclass; wire
   in the hook; add a minimal native-build engine and route `model_fixture` through it
   (bypassing the override).
4. **Core resolution + `register_factory`.** Add the namespaces and §3.3 resolution;
   share shareable `SubFactory`s; leave non-shareable/unregistered targets to
   factory_boy.
5. **Per-creation engine + parity.** Deferred/cycle behavior per §4.2; forward
   `params`; strategy-parameterized. Keep `test_circular.py` and exact-once
   `_after_postgeneration` green.

### Follow-ups (independent PRs)

- **F1** factory-anchored identity resolution (drop the inflection fallback), then
  `named_model` deprecation.
- **F2** native evaluation for non-shareable / unregistered `SubFactory`.
- **F3** scoping via `pytest.register_fixture`.
- **F4** Traits/Params/Maybe, model-only attributes, build fixtures.

---

## 12. Issue impact

| # | Title | Outcome |
| --- | --- | --- |
| 223 | Deferred factory evaluation | **solved**; the factory is parametrized via `foo_factory__<attr>`; post-gen parity in the first PR |
| 257 | Ignore which SubFactory | **solved** (identity) — F1 |
| 218 | SubFactory collision | **solved** (identity) — F1 |
| 94 | Self-referencing FK | needs explicit handling (identity alone insufficient) — F1 |
| 225 | factory-function models | addressed by factory anchoring — F1 |
| 263 | SelfAttribute + SubFactory | **solved** for non-shareable SubFactories (native eval) — F2 |
| 40 | SubFactory attr assignment | **solved** for non-shareable SubFactories — F2 |
| 82 | decorator + circular imports | **partial** — needs a lazy dependency graph — F1 |
| 229 | request on factory class | enabled by the design |
| 81 | Scope | **enabled by `register_fixture`** — F3 |
| 220/53 | Traits as fixtures | future |
| 126/196/98 | Maybe/Trait/Params | future |
| 23 | model-only attributes | future |
| 56 | Factory.build fixtures | future |
| 74 | Override sequence counter | not addressed / explain |
| 156 | mute_signals | open; the double-`_after_postgeneration` half was fixed in 2.5.0 |
| 157 | postgen related initiating instance | not addressed |
| 97 | RelatedFactory in fixtures | unchanged |
| 69 | disable SubFactory replacement | future (configurable) |
| 205 | pass scope fixtures to factories | enabled by the design |
| 67/63/59/36/93/187 | unrelated | not addressed |

---

## 13. Risks

- **Per-creation engine (§11 step 5)** is the highest-risk item: test-body calls,
  distinct instances, caching, cycle detection.
- **Recursion** if `model_fixture` is not made override-aware.
- **Shareability semantics** must be crisp; the #263/#40 boundary needs tests.
- **Closure gating**: a non-shareable target forced into `foo_factory`'s closure (or a
  parent-referencing target shared) raises at setup.
- **Minimum-version bump** to `pytest>=9.1` + `factory_boy>=3.3` is a breaking
  prerequisite.
- **Register-time dependency graph (#82/#94)** is a mini-project of its own.
- **Issue #223 parametrization** uses `foo_factory__<attr>` (the factory's own
  namespace); `foo__<attr>` configures only `foo` and defaults to the factory value.
