from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any


def _resolve_prompt_input(path_value: Any, prompt_inputs: dict[str, Any], resolve_dotted_path_func: Any) -> Any:
    if not isinstance(path_value, str):
        raise RuntimeError(f"prompt_input(path) expects string path, got {type(path_value).__name__}")
    input_path = path_value.strip()
    if not input_path:
        raise RuntimeError("prompt_input(path) expects non-empty path, got empty string")
    return resolve_dotted_path_func({"inputs": prompt_inputs}, f"inputs.{input_path}")


def _resolve_include_path(path_value: Any, config_dir: Path, resolve_path_func: Any) -> tuple[str, Path]:
    if not isinstance(path_value, str):
        raise RuntimeError(f"prompt_file(path) expects string path, got {type(path_value).__name__}")
    include_raw = path_value.strip()
    if not include_raw:
        raise RuntimeError("prompt_file(path) expects non-empty relative path, got empty string")

    path_obj = Path(include_raw).expanduser()
    if path_obj.is_absolute():
        raise RuntimeError(
            f"prompt_file(path) only supports relative path, got absolute path: {include_raw}. "
            "Use a path relative to the workflow config file."
        )
    return include_raw, resolve_path_func(path_obj, config_dir)


def build_prompt_helpers(
    *,
    prompt_inputs: dict[str, Any],
    config_dir: Path,
    resolve_dotted_path_func: Any,
    resolve_path_func: Any,
    read_text_func: Any,
    render_included_text: Callable[[str, Path], str],
) -> tuple[Callable[[Any], Any], Callable[[Any], str]]:
    render_stack: list[Path] = []

    def prompt_input(path_value: Any) -> Any:
        return _resolve_prompt_input(path_value, prompt_inputs, resolve_dotted_path_func)

    def prompt_file(path_value: Any) -> str:
        include_raw, include_path = _resolve_include_path(path_value, config_dir, resolve_path_func)
        if include_path in render_stack:
            cycle = " -> ".join([*map(str, render_stack), str(include_path)])
            raise RuntimeError(f"prompt_file(path) recursive include detected: {cycle}")
        try:
            render_stack.append(include_path)
            include_text = read_text_func(include_path)
            return render_included_text(include_text, include_path)
        except FileNotFoundError as exc:
            raise RuntimeError(
                f"prompt_file(path) file not found: {include_raw}. Check the path relative to the workflow config file."
            ) from exc
        except OSError as exc:
            raise RuntimeError(
                f"prompt_file(path) cannot read file: {include_raw} ({exc}). Check file permissions and UTF-8 content."
            ) from exc
        finally:
            if render_stack and render_stack[-1] == include_path:
                render_stack.pop()

    return prompt_input, prompt_file


def build_finalize_func(undefined_type: type[Any]) -> Callable[[Any], Any]:
    def _finalize(value: Any) -> Any:
        from _codex_orchestrator.prompt.values import finalize_prompt_value

        return finalize_prompt_value(value, undefined_type)

    return _finalize
