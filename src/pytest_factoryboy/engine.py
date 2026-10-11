"""The generation engine behind the factory fixture.

:func:`bind_factory` returns a request-bound subclass of the user's factory with a
``_generate`` hook installed (see :mod:`.generate`). The hook is the engine's single
interception point for *top-level* generation on the direct ``foo_factory()`` path. The
model fixture deliberately builds from the original factory (see
:data:`ORIGINAL_FACTORY_ATTR`) and does not enter the engine.

This is the skeleton described in ``specs/factory-fixtures.md`` §6/§11: for now
:func:`generate` simply delegates to factory_boy. Later changes resolve shareable
sub-factories and manage post-generation deferral here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar, cast

from .generate import install_generate_hook

if TYPE_CHECKING:
    from collections.abc import Mapping

    from _pytest.fixtures import SubRequest
    from factory.base import Factory

T = TypeVar("T")

# Bound on the subclass; underscore-prefixed so factory_boy does not mistake them for
# declarations.
REQUEST_ATTR = "_factoryboy_request"
MODEL_NAME_ATTR = "_factoryboy_model_name"
ORIGINAL_FACTORY_ATTR = "_factoryboy_original_factory"

__all__ = ("MODEL_NAME_ATTR", "ORIGINAL_FACTORY_ATTR", "REQUEST_ATTR", "bind_factory", "generate")


def bind_factory(
    factory_class: type[Factory[T]],
    request: SubRequest,
    model_name: str,
) -> type[Factory[T]]:
    """Return a request-bound subclass of ``factory_class`` with the engine hook installed.

    :param factory_class: The user's factory.
    :param request: The pytest request to bind (used to resolve fixtures later).
    :param model_name: The model fixture name, bound for later resolution.
    :return: A subclass of ``factory_class`` whose ``_generate`` goes through the engine.
    """
    bound = install_generate_hook(factory_class, generate)
    bound._factoryboy_request = request  # type: ignore[attr-defined]
    bound._factoryboy_model_name = model_name  # type: ignore[attr-defined]
    # The model fixture unwraps this to build from the original factory, bypassing the
    # engine hook (it resolves sub-factories and post-generation itself).
    bound._factoryboy_original_factory = factory_class  # type: ignore[attr-defined]
    return bound


def generate(cls: type[Factory[T]], strategy: str, params: Mapping[str, object]) -> T:
    """Engine entry point for a top-level generation.

    Minimal implementation: delegate to factory_boy. Called by the ``_generate`` hook,
    so ``cls._generate`` runs factory_boy's generation without re-entering this function.
    """
    return cast("T", cls._generate(strategy, params))
