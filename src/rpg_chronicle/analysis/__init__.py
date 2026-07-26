"""Model-backed analysis, assembled from three separable concerns.

- `backend` — how a model is reached, and which model it is. Vendor names live only in
  backend implementations such as `claude_cli`.
- `decompose` — how a transcript too large for one request is split and recombined.
- `prompts` — what is asked, in RPG terms, of whichever model answers.

`provider.ModelAnalysisProvider` composes them into an `AnalysisProvider`. Nothing
under `rpg_chronicle.pipeline` imports anything from this package.
"""

from __future__ import annotations

from .backend import (
    BackendCredentialError,
    BackendError,
    BackendResponseError,
    BackendUnavailableError,
    ModelBackend,
    ModelRequest,
    ModelResponse,
    TokenUsage,
    require_env_credential,
)
from .decompose import TokenBudget, Window, plan_windows
from .provider import (
    DEFAULT_MAX_QUESTIONS,
    AnalysisCost,
    AnalysisFormatError,
    ModelAnalysisProvider,
)

__all__ = [
    "DEFAULT_MAX_QUESTIONS",
    "AnalysisCost",
    "AnalysisFormatError",
    "BackendCredentialError",
    "BackendError",
    "BackendResponseError",
    "BackendUnavailableError",
    "ModelAnalysisProvider",
    "ModelBackend",
    "ModelRequest",
    "ModelResponse",
    "TokenBudget",
    "TokenUsage",
    "Window",
    "plan_windows",
    "require_env_credential",
]
