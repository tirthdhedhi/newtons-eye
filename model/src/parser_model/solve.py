"""Wrapper around the TypeScript solver CLI (``pnpm solve <file>``).

Exit codes of the CLI: 0 ok, 1 validation failure (``{"issues": [...]}`` on stderr),
2 some query failed (its value is ``null``). pnpm 11 needs Node >= 22, so the wrapper puts the
Node named by the repo's ``.nvmrc`` (found under ``~/.nvm``) first on PATH. Override with the
``NEWTONS_NODE_BIN`` (a bin directory) and ``NEWTONS_SOLVE_CMD`` environment variables.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .paths import repo_root

DEFAULT_CMD = "pnpm --silent solve"
TIMEOUT_S = 120


@dataclass
class SolveResult:
    exit_code: int
    answers: dict[str, Any] | None = None
    warnings: list[str] = field(default_factory=list)
    issues: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    stderr: str = ""

    @property
    def ok(self) -> bool:
        return self.exit_code == 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def node_bin_dir() -> Path | None:
    """Bin directory of the Node version in ``.nvmrc``, if one is installed under ``~/.nvm``."""
    override = os.environ.get("NEWTONS_NODE_BIN")
    if override:
        return Path(override)
    nvmrc = repo_root() / ".nvmrc"
    if not nvmrc.exists():
        return None
    major = nvmrc.read_text().strip().lstrip("v").split(".")[0]
    versions = Path.home() / ".nvm" / "versions" / "node"
    candidates = sorted(versions.glob(f"v{major}.*"), key=_version_key)
    return candidates[-1] / "bin" if candidates else None


def _version_key(path: Path) -> tuple[int, ...]:
    return tuple(int(p) for p in path.name.lstrip("v").split(".") if p.isdigit())


def _env() -> dict[str, str]:
    env = dict(os.environ)
    node = node_bin_dir()
    if node and node.exists():
        env["PATH"] = f"{node}{os.pathsep}{env.get('PATH', '')}"
    return env


def solver_available() -> bool:
    try:
        out = subprocess.run(
            ["pnpm", "--version"], capture_output=True, text=True, env=_env(), timeout=30
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return out.returncode == 0


def solve_scene(scene: dict[str, Any] | str | Path, cmd: str | None = None) -> SolveResult:
    """Solve a scene dict or file. Never raises on solver failures: they are in the result."""
    if isinstance(scene, dict):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scene.json"
            path.write_text(json.dumps(scene))
            return _run(path, cmd)
    return _run(Path(scene).resolve(), cmd)


def _run(path: Path, cmd: str | None) -> SolveResult:
    argv = [*shlex.split(cmd or os.environ.get("NEWTONS_SOLVE_CMD", DEFAULT_CMD)), str(path)]
    try:
        proc = subprocess.run(
            argv,
            cwd=repo_root(),
            env=_env(),
            capture_output=True,
            text=True,
            timeout=TIMEOUT_S,
        )
    except FileNotFoundError:
        return SolveResult(exit_code=127, errors=[f"cannot run {argv[0]!r}: not on PATH"])
    except subprocess.TimeoutExpired:
        return SolveResult(exit_code=124, errors=[f"solver timed out after {TIMEOUT_S}s"])
    return parse_output(proc.returncode, proc.stdout, proc.stderr)


def parse_output(exit_code: int, stdout: str, stderr: str) -> SolveResult:
    """Turn raw CLI output into a SolveResult (separate from ``_run`` so it is unit-testable)."""
    result = SolveResult(exit_code=exit_code, stderr=stderr)
    stderr_text = stderr.strip()
    for line in stderr_text.splitlines():
        if line.startswith("warning:"):
            result.warnings.append(line[len("warning:") :].strip())
        elif line.startswith("error:"):
            result.errors.append(line[len("error:") :].strip())
    if exit_code == 1 and stderr_text.startswith("{"):
        try:
            result.issues = json.loads(stderr_text).get("issues", [])
        except json.JSONDecodeError:
            result.errors.append("unparseable validation issues on stderr")
    if exit_code in (0, 2):
        try:
            parsed = json.loads(stdout)
            result.answers = parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            result.errors.append(f"unparseable solver stdout: {stdout[:200]!r}")
    return result
