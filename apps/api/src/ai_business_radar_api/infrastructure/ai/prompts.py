from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from .errors import PromptNotFoundError

PROMPT_ROOT = Path(__file__).parents[6] / "prompts"

RUNTIME_PROMPT_DEFAULTS = {
    "opportunity-consolidation": "v001",
    "relevance-filter": "v001",
    "signal-extractor": "v003",
    "comment-pain-miner": "v001",
    "opportunity-normalizer": "v001",
    "intelligence-translation/zh-CN": "v001",
}


@dataclass(frozen=True)
class ResolvedPrompt:
    family: str
    version: str
    content: str
    sha256: str
    path: Path


def default_prompt_version(family: str) -> str:
    try:
        return RUNTIME_PROMPT_DEFAULTS[family]
    except KeyError as error:
        raise PromptNotFoundError(f"Unknown prompt family: {family}") from error


def resolve_prompt(
    family: str, version: str | None = None, *, root: Path = PROMPT_ROOT
) -> ResolvedPrompt:
    selected = version or default_prompt_version(family)
    if not family or not selected or any(part in {"", ".", ".."} for part in family.split("/")):
        raise PromptNotFoundError("Invalid prompt identity")
    if "/" in selected:
        raise PromptNotFoundError("Invalid prompt identity")
    path = root.joinpath(*family.split("/"), f"{selected}.md")
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise PromptNotFoundError(f"Invalid prompt version: {family}/{selected}") from error
    return ResolvedPrompt(
        family=family,
        version=selected,
        content=content,
        sha256=sha256(content.encode()).hexdigest(),
        path=path,
    )


def load_prompt(task: str, version: str, *, root: Path = PROMPT_ROOT) -> str:
    return resolve_prompt(task, version, root=root).content
