"""The transport seam: how a model is reached, separated from which model it is.

This module is the answer to "how do we talk to a model", and deliberately nothing
else. It does not know what a transcript is, what a scene is, or how a session too
large for one request is split up. A backend receives text and returns text plus what
the exchange cost.

Three concerns are commonly fused and are kept apart here:

1. *Which model* is being asked -- carried as configuration on the backend, so the same
   transport can address a different model without a code change.
2. *How it is reached* -- a subscription-mediated CLI, an API key, a gateway. That is
   the `ModelBackend` implementation, and it is the only place a vendor name may appear.
3. *How a long transcript is decomposed* -- not here at all. See `decompose.py`.

Adding a gateway backend later means writing one class in this package that satisfies
`ModelBackend`. It must not require touching the prompts, the decomposition, the
provider, or anything under `pipeline.py`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol


class BackendError(RuntimeError):
    """Base class for every failure that originates in the transport."""


class BackendUnavailableError(BackendError):
    """The backend cannot be used at all: missing executable, missing credential.

    Raised by `preflight()` before any work begins, so a misconfigured run fails
    before it can write a partial artifact.
    """


class BackendCredentialError(BackendUnavailableError):
    """A required credential is absent from the environment.

    The message names the environment variable and never its value. Credential
    material must not reach logs, error strings, or the repository.
    """


class BackendResponseError(BackendError):
    """The backend was reached but did not return a usable response."""


@dataclass(frozen=True)
class ModelRequest:
    """One exchange with a model. Plain text in both directions, by design.

    Structured-output APIs differ per vendor. Keeping the request to text means a
    gateway backend is a thin adapter rather than a translation layer, and it keeps
    response parsing in one vendor-neutral place.
    """

    system: str
    user: str


@dataclass(frozen=True)
class TokenUsage:
    """What one exchange consumed.

    `cached_input_tokens` is reported separately because a backend that caches a
    prompt prefix bills it differently, and a cost figure that silently folds the two
    together cannot be compared across backends.
    """

    input_tokens: int
    output_tokens: int
    cached_input_tokens: int = 0

    @property
    def billed_input_tokens(self) -> int:
        """Every input token the request presented, cached or not."""
        return self.input_tokens + self.cached_input_tokens

    def __add__(self, other: TokenUsage) -> TokenUsage:
        return TokenUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cached_input_tokens=self.cached_input_tokens + other.cached_input_tokens,
        )


@dataclass(frozen=True)
class ModelResponse:
    text: str
    usage: TokenUsage
    wall_ms: int


class ModelBackend(Protocol):
    """A way of reaching a model. The only place a vendor name is permitted."""

    name: str
    model: str

    def preflight(self) -> None:
        """Fail before any work begins if this backend cannot run.

        Implementations raise `BackendUnavailableError` (or `BackendCredentialError`)
        and must never emit credential material in the message.
        """
        ...

    def complete(self, request: ModelRequest) -> ModelResponse: ...


def require_env_credential(env_var: str, *, backend_name: str) -> str:
    """Read a credential from the environment, or fail with a non-leaking error.

    Backends that need a key call this from `preflight()`. It is shared rather than
    reimplemented per backend so that the failure message, and the guarantee that the
    value never appears in it, are written once.

    No credential is ever read from the repository, and the returned value must not be
    logged, printed, or embedded in an exception.
    """
    value = os.environ.get(env_var)
    if value is None:
        raise BackendCredentialError(
            f"backend {backend_name!r} requires the environment variable {env_var}, "
            "which is not set. Export it in the environment before running; it must "
            "never be committed to the repository."
        )
    if not value.strip():
        raise BackendCredentialError(
            f"backend {backend_name!r} requires the environment variable {env_var}, "
            "which is set but empty."
        )
    return value
