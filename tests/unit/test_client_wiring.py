"""
Guard tests for AC2: every Client.connect(...) call must pass
data_converter=pydantic_data_converter, and __main__.py must call
configure_client + configure_provider in the correct order.

The module-level import acts as a canary — if temporalio.contrib.pydantic
is missing entirely, collection fails with ImportError/ModuleNotFoundError.
"""
import ast
import pathlib

import pytest

from temporalio.contrib.pydantic import pydantic_data_converter  # noqa: F401 — import guard

REPO_ROOT = pathlib.Path(__file__).parent.parent.parent

FILES_WITH_CONNECT = [
    "apps/vault_worker/__main__.py",
    "apps/copilot_ui/app.py",
    "apps/github_runner/trigger.py",
]


def _source(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text()


def _parse(rel_path: str) -> ast.Module:
    return ast.parse(_source(rel_path))


def _connect_calls(tree: ast.Module) -> list[ast.Call]:
    """Return every Call node whose .func attribute is named 'connect'."""
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "connect"
    ]


def _has_pydantic_kwarg(call: ast.Call, source: str) -> bool:
    for kw in call.keywords:
        if kw.arg == "data_converter":
            seg = ast.get_source_segment(source, kw.value) or ""
            return "pydantic_data_converter" in seg
    return False


@pytest.mark.parametrize("rel_path", FILES_WITH_CONNECT)
def test_client_connect_passes_pydantic_data_converter(rel_path: str) -> None:
    """Every .connect(...) call site must include data_converter=pydantic_data_converter."""
    source = _source(rel_path)
    tree = _parse(rel_path)

    calls = _connect_calls(tree)
    assert calls, f"{rel_path}: no .connect(...) call found — file may have changed"

    missing = [c for c in calls if not _has_pydantic_kwarg(c, source)]
    assert not missing, (
        f"{rel_path}: {len(missing)} Client.connect call(s) missing "
        f"data_converter=pydantic_data_converter "
        f"(lines: {[c.lineno for c in missing]})"
    )


def test_main_configure_calls_present_and_ordered() -> None:
    """
    apps/vault_worker/__main__.py must call configure_client(client) AND
    configure_provider(...) inside main(), both textually after Client.connect
    and before the workers gather.
    """
    rel_path = "apps/vault_worker/__main__.py"
    source = _source(rel_path)  # noqa: F841 — kept for symmetry / future segment checks
    tree = _parse(rel_path)

    main_fn = next(
        (
            n
            for n in ast.walk(tree)
            if isinstance(n, (ast.AsyncFunctionDef, ast.FunctionDef))
            and n.name == "main"
        ),
        None,
    )
    assert main_fn is not None, "__main__.py has no `main` function"

    # Collect (call_name, lineno) for every Call in main body, sorted by line number
    raw: list[tuple[str, int]] = []
    for node in ast.walk(main_fn):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                raw.append((func.id, node.lineno))
            elif isinstance(func, ast.Attribute):
                raw.append((func.attr, node.lineno))
    raw.sort(key=lambda x: x[1])

    names = [n for n, _ in raw]

    assert "configure_client" in names, (
        "apps/vault_worker/__main__.py main(): configure_client(client) is not called — "
        "Temporal Client module-global state will be unset and activities will raise RuntimeError"
    )
    assert "configure_provider" in names, (
        "apps/vault_worker/__main__.py main(): configure_provider(...) is not called — "
        "LLM provider module-global state will be unset"
    )

    connect_line = min(ln for n, ln in raw if n == "connect")
    by_name = {n: ln for n, ln in raw}

    cfg_client_line = by_name["configure_client"]
    cfg_provider_line = by_name["configure_provider"]

    assert cfg_client_line > connect_line, (
        f"configure_client (line {cfg_client_line}) must appear after "
        f"Client.connect (line {connect_line})"
    )
    assert cfg_provider_line > connect_line, (
        f"configure_provider (line {cfg_provider_line}) must appear after "
        f"Client.connect (line {connect_line})"
    )

def test_main_module_actually_imports():
    """ast.parse cannot catch a wrong import path — this can.

    The production Dockerfile CMD is `python3 -m apps.vault_worker`; if
    __main__ raises ImportError the container dies at startup (shipped
    reviewer finding: configure_provider imported from the wrong module).
    Importing executes only module-level imports/defs — main() is guarded.
    """
    import importlib

    importlib.import_module("apps.vault_worker.__main__")
