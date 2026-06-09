"""
PromptRegistry: loads versioned prompt templates from the prompts/ directory.

Each agent has a subdirectory under prompts/ containing v1.txt, v2.txt, ...
The active version is controlled by config (e.g. CREDIT_AGENT_PROMPT_VERSION=v2).
Templates use Python str.format() placeholders, so literal braces must be {{ }}.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import structlog

logger = structlog.get_logger()

_PROMPTS_DIR = Path(__file__).parent


class PromptRegistry:
    def __init__(self, prompts_dir: Path) -> None:
        self._dir = prompts_dir
        self._cache: dict[tuple[str, str], str] = {}

    def get(self, agent_name: str, version: str) -> str:
        """Return template text for agent/version. Cached in memory after first load."""
        key = (agent_name, version)
        if key not in self._cache:
            path = self._dir / agent_name / f"{version}.txt"
            if not path.exists():
                raise FileNotFoundError(
                    f"Prompt not found: {path}. "
                    f"Set {agent_name.upper()}_PROMPT_VERSION to a valid version."
                )
            self._cache[key] = path.read_text(encoding="utf-8")
            logger.debug("prompt_loaded", agent=agent_name, version=version)
        return self._cache[key]

    def validate_all(self, versions: dict[str, str]) -> None:
        """Fail fast on startup: verify all agent/version pairs exist on disk."""
        missing: list[str] = []
        for agent_name, version in versions.items():
            path = self._dir / agent_name / f"{version}.txt"
            if not path.exists():
                missing.append(str(path))
        if missing:
            raise FileNotFoundError(
                f"Missing prompt file(s): {missing}. "
                "Add the files or update the version settings."
            )

    def invalidate(self, agent_name: str | None = None) -> None:
        """Clear cached templates — used after hot-swap or in tests."""
        if agent_name is None:
            self._cache.clear()
        else:
            self._cache = {k: v for k, v in self._cache.items() if k[0] != agent_name}


@lru_cache()
def get_prompt_registry() -> PromptRegistry:
    return PromptRegistry(_PROMPTS_DIR)
