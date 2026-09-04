from pathlib import Path

from .errors import PromptNotFoundError

PROMPT_ROOT = Path(__file__).parents[6] / "prompts"


def load_prompt(task: str, version: str, *, root: Path = PROMPT_ROOT) -> str:
    if not task or not version or "/" in task or "/" in version:
        raise PromptNotFoundError("Invalid prompt identity")
    path = root / task / f"{version}.md"
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise PromptNotFoundError(f"Prompt not found: {task}/{version}") from error
