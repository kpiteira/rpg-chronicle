"""The seam holds only if no vendor detail has leaked out of a backend.

The goal's design test is: adding an OpenRouter backend later must not require
touching the decomposition code, the prompts, or anything under `pipeline.py`. That is
a property of the source, so it is checked against the source. If someone reaches for
a vendor-specific field in the prompts or special-cases a model name in the pipeline,
these tests go red on the commit that does it, not months later when the second
backend is attempted.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).parents[1] / "src" / "rpg_chronicle"

VENDOR_WORDS = (
    "claude",
    "anthropic",
    "sonnet",
    "openai",
    "gpt-",
    "openrouter",
    "gemini",
    "llama",
    "mistral",
    "bedrock",
    "vertex",
)

# Every module that must survive a change of vendor untouched. `claude_cli.py` is the
# backend itself and `cli.py` is the wiring point where a backend is chosen, which
# D-008 already names as the place selection belongs; both are excluded by design.
VENDOR_FREE_MODULES = [
    "pipeline.py",
    "model.py",
    "providers.py",
    "analysis/backend.py",
    "analysis/decompose.py",
    "analysis/prompts.py",
    "analysis/provider.py",
    "analysis/__init__.py",
]


@pytest.mark.parametrize("relative", VENDOR_FREE_MODULES)
def test_module_names_no_vendor(relative):
    text = (SRC / relative).read_text().casefold()
    # `claude_cli` is named in prose in a couple of these files to explain where the
    # vendor *is* allowed to live; only bare vendor words are a leak.
    text = text.replace("claude_cli", "").replace("claude code cli", "")
    found = [word for word in VENDOR_WORDS if word in text]
    assert not found, f"{relative} names a vendor: {found}"


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
            names.update(f"{node.module}.{alias.name}" for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.update(f".{alias.name}" for alias in node.names)
    return names


def test_the_pipeline_does_not_import_the_analysis_package():
    """The pipeline receives providers; it never constructs or inspects one."""
    imports = _imported_modules(SRC / "pipeline.py")
    assert not [name for name in imports if "analysis" in name], imports


def test_the_provider_does_not_import_any_backend_implementation():
    """`ModelAnalysisProvider` holds a backend by protocol, never by class."""
    imports = _imported_modules(SRC / "analysis" / "provider.py")
    assert not [name for name in imports if "claude" in name.casefold()], imports


def test_the_analysis_package_import_pulls_in_no_vendor():
    """Importing the package must not import a vendor module as a side effect."""
    imports = _imported_modules(SRC / "analysis" / "__init__.py")
    assert not [name for name in imports if "claude" in name.casefold()], imports


def test_prompts_and_decomposition_do_not_import_a_backend():
    for relative in ("analysis/prompts.py", "analysis/decompose.py"):
        imports = _imported_modules(SRC / relative)
        assert not [name for name in imports if "backend" in name or "claude" in name], (
            relative,
            imports,
        )


def test_a_backend_satisfies_the_protocol_without_inheriting_it():
    """Structural typing is what makes a third-party backend a drop-in.

    A backend that had to subclass something in this repository would not be addable
    from outside it.
    """
    from rpg_chronicle.analysis.backend import ModelBackend
    from rpg_chronicle.analysis.claude_cli import ClaudeCliBackend

    from .fake_backend import FakeBackend

    for backend in (ClaudeCliBackend(), FakeBackend()):
        assert ModelBackend not in type(backend).__mro__, "backends must not inherit"
        assert callable(backend.complete)
        assert callable(backend.preflight)
        assert isinstance(backend.name, str) and backend.name
        assert isinstance(backend.model, str) and backend.model
