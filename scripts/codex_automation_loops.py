#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from string import Template

PROMPT_ARG_CACHE: dict[str, str] = {}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Automate codex-cli loops (fast-fail mode).")
    sub = parser.add_subparsers(dest="mode", required=True)

    def add_common(p: argparse.ArgumentParser, need_spec: bool = False) -> None:
        if need_spec:
            p.add_argument("--spec", required=True, help="Path to xxx.md spec file")
        p.add_argument("--state-dir", default=".codex-loop-state", help="State directory")
        p.add_argument("--max-iterations", type=int, default=20, help="Maximum iterations")
        p.add_argument("--prompt-dir", default="prompts", help="Prompt template directory")
        p.add_argument("--codex-cmd", default=None, help="Override CODEX_CMD / codex-cli")

    add_common(sub.add_parser("implement-loop"), need_spec=True)
    add_common(sub.add_parser("review-loop"))
    add_common(sub.add_parser("all"), need_spec=True)
    return parser.parse_args()


def load_template(prompt_dir: Path, name: str) -> Template:
    path = prompt_dir / name
    if not path.is_file():
        raise FileNotFoundError(f"Prompt template not found: {path}")
    return Template(path.read_text(encoding="utf-8"))


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def run_codex(codex_cmd: str, prompt: str, prompt_file: Path, out_file: Path) -> None:
    tokens = shlex.split(codex_cmd)
    if not tokens:
        raise ValueError("Empty codex command")

    used_placeholder = False
    resolved: list[str] = []
    for token in tokens:
        if "{PROMPT_FILE}" in token:
            token = token.replace("{PROMPT_FILE}", str(prompt_file))
            used_placeholder = True
        if "{PROMPT}" in token:
            token = token.replace("{PROMPT}", prompt)
            used_placeholder = True
        resolved.append(token)

    if not used_placeholder:
        prompt_mode = discover_prompt_mode(tokens)
        if prompt_mode == "prompt-file":
            resolved.extend(["--prompt-file", str(prompt_file)])
        elif prompt_mode == "prompt":
            resolved.extend(["--prompt", prompt])
        else:
            raise RuntimeError("Unable to determine prompt argument mode for codex command")

    result = subprocess.run(resolved, capture_output=True, text=True, check=False)
    write_text(out_file, result.stdout)

    if result.returncode != 0:
        err = out_file.with_suffix(out_file.suffix + ".stderr")
        write_text(err, result.stderr)
        raise RuntimeError(f"codex failed: exit={result.returncode}, stderr={err}")


def discover_prompt_mode(tokens: list[str]) -> str:
    cache_key = " ".join(tokens)
    if cache_key in PROMPT_ARG_CACHE:
        return PROMPT_ARG_CACHE[cache_key]

    help_result = subprocess.run(tokens + ["--help"], capture_output=True, text=True, check=False)
    help_text = f"{help_result.stdout}\n{help_result.stderr}"

    if "--prompt-file" in help_text:
        PROMPT_ARG_CACHE[cache_key] = "prompt-file"
        return "prompt-file"
    if "--prompt" in help_text:
        PROMPT_ARG_CACHE[cache_key] = "prompt"
        return "prompt"

    raise RuntimeError(
        f"Cannot find --prompt-file/--prompt in help output for command: {cache_key}. "
        "Set --codex-cmd with {PROMPT} or {PROMPT_FILE} explicitly."
    )


def parse_str_list_json(text: str, required_field: str) -> list[str]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON output: {exc}") from exc

    if not isinstance(data, dict):
        raise RuntimeError("Output JSON must be an object")
    if set(data.keys()) != {required_field}:
        raise RuntimeError(f"Output keys must be exactly ['{required_field}']")

    value = data[required_field]
    if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
        raise RuntimeError(f"Field '{required_field}' must be string list")
    return [x.strip() for x in value if x.strip()]


def render_to_state(state_dir: Path, filename: str, content: str) -> Path:
    path = state_dir / filename
    write_text(path, content)
    return path


def build_scope_diff(state_dir: Path) -> Path:
    scope_path = state_dir / "scope.diff"

    tracked = subprocess.run(
        ["git", "diff", "--no-color", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if tracked.returncode != 0:
        raise RuntimeError("git diff HEAD failed")

    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
        capture_output=True,
        check=False,
    )
    if untracked.returncode != 0:
        raise RuntimeError("git ls-files --others failed")

    diff_parts: list[str] = [tracked.stdout]
    untracked_files = [p for p in untracked.stdout.decode("utf-8", errors="strict").split("\x00") if p]
    for rel_path in untracked_files:
        udiff = subprocess.run(
            ["git", "diff", "--no-color", "--no-index", "/dev/null", rel_path],
            capture_output=True,
            text=True,
            check=False,
        )
        if udiff.returncode not in (0, 1):
            raise RuntimeError(f"git diff --no-index failed for untracked file: {rel_path}")
        diff_parts.append(udiff.stdout)

    merged = "".join(diff_parts).strip()
    if not merged:
        raise RuntimeError("scope.diff is empty; review-loop requires tracked/staged/untracked changes")

    write_text(scope_path, merged + "\n")
    return scope_path


def implement_loop(spec: Path, state_dir: Path, prompt_dir: Path, codex_cmd: str, max_iterations: int) -> None:
    if not spec.is_file():
        raise FileNotFoundError(f"Spec file not found: {spec}")

    initial_tpl = load_template(prompt_dir, "implement_initial.prompt.txt")
    continue_tpl = load_template(prompt_dir, "implement_continue.prompt.txt")
    check_tpl = load_template(prompt_dir, "check.prompt.txt")

    todo_file = state_dir / "todo.txt"
    write_text(todo_file, "")

    for i in range(1, max_iterations + 1):
        print(f"[implement-loop] iteration {i}")

        if i == 1:
            implement_prompt = initial_tpl.safe_substitute(spec=str(spec))
        else:
            implement_prompt = continue_tpl.safe_substitute(todo=todo_file.read_text(encoding="utf-8"))

        implement_prompt_file = render_to_state(state_dir, "implement_prompt.txt", implement_prompt)
        run_codex(codex_cmd, implement_prompt, implement_prompt_file, state_dir / f"implement_{i}.out")

        check_prompt = check_tpl.safe_substitute(spec=str(spec))
        check_prompt_file = render_to_state(state_dir, "check_prompt.txt", check_prompt)
        check_out = state_dir / f"check_{i}.out"
        run_codex(codex_cmd, check_prompt, check_prompt_file, check_out)

        todo = parse_str_list_json(check_out.read_text(encoding="utf-8"), "todo")
        write_text(todo_file, "\n".join(todo))

        if not todo:
            print(f"[implement-loop] {spec} fully implemented.")
            return

    raise RuntimeError(f"[implement-loop] reached max iterations: {max_iterations}")


def review_loop(state_dir: Path, prompt_dir: Path, codex_cmd: str, max_iterations: int) -> None:
    review_tpl = load_template(prompt_dir, "review.prompt.txt")
    fix_tpl = load_template(prompt_dir, "fix.prompt.txt")

    issues_file = state_dir / "issues.txt"
    write_text(issues_file, "")

    for i in range(1, max_iterations + 1):
        print(f"[review-loop] iteration {i}")

        scope_path = build_scope_diff(state_dir)
        review_prompt = review_tpl.safe_substitute(scope_path=str(scope_path))
        review_prompt_file = render_to_state(state_dir, "review_prompt.txt", review_prompt)
        review_out = state_dir / f"review_{i}.out"
        run_codex(codex_cmd, review_prompt, review_prompt_file, review_out)

        issues = parse_str_list_json(review_out.read_text(encoding="utf-8"), "issues")
        write_text(issues_file, "\n".join(issues))

        if not issues:
            print("[review-loop] all issues fixed.")
            return

        fix_prompt = fix_tpl.safe_substitute(issues=issues_file.read_text(encoding="utf-8"))
        fix_prompt_file = render_to_state(state_dir, "fix_prompt.txt", fix_prompt)
        run_codex(codex_cmd, fix_prompt, fix_prompt_file, state_dir / f"fix_{i}.out")

    raise RuntimeError(f"[review-loop] reached max iterations: {max_iterations}")


def main() -> int:
    args = parse_args()
    state_dir = Path(args.state_dir)
    prompt_dir = Path(args.prompt_dir)
    state_dir.mkdir(parents=True, exist_ok=True)

    codex_cmd = args.codex_cmd or os.environ.get("CODEX_CMD", "codex-cli")

    try:
        if args.mode == "implement-loop":
            implement_loop(Path(args.spec), state_dir, prompt_dir, codex_cmd, args.max_iterations)
        elif args.mode == "review-loop":
            review_loop(state_dir, prompt_dir, codex_cmd, args.max_iterations)
        elif args.mode == "all":
            implement_loop(Path(args.spec), state_dir, prompt_dir, codex_cmd, args.max_iterations)
            review_loop(state_dir, prompt_dir, codex_cmd, args.max_iterations)
        else:
            raise ValueError(f"Unknown mode: {args.mode}")
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
