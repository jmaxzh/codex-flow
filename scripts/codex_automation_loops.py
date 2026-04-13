#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from string import Template

SCRIPT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PROMPT_DIR = SCRIPT_ROOT / "prompts"
CODEX_EXEC_CMD = ["codex", "exec", "--skip-git-repo-check"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Automate codex loops (fast-fail mode).")
    sub = parser.add_subparsers(dest="mode", required=True)

    def add_common(
        p: argparse.ArgumentParser,
        need_spec: bool = False,
        need_review_extra_prompt: bool = False,
    ) -> None:
        if need_spec:
            p.add_argument(
                "--spec",
                required=True,
                help="Spec reference path (file or directory, no type validation)",
            )
            p.add_argument(
                "--implement-extra-prompt",
                default="",
                help="Extra instruction text used as implement instruction (overrides default when set)",
            )
        if need_review_extra_prompt:
            p.add_argument(
                "--review-extra-prompt",
                default="",
                help="Extra instruction text used as review scope instruction (overrides default when set)",
            )
        p.add_argument("--project-root", default=".", help="Target project root directory")
        p.add_argument("--state-dir", default=".codex-loop-state", help="State directory")
        p.add_argument("--max-iterations", type=int, default=20, help="Maximum iterations")
        p.add_argument(
            "--prompt-dir",
            default=str(DEFAULT_PROMPT_DIR),
            help="Prompt template directory (absolute, or relative to project root)",
        )

    add_common(sub.add_parser("implement-loop"), need_spec=True)
    add_common(sub.add_parser("review-loop"), need_review_extra_prompt=True)
    add_common(sub.add_parser("all"), need_spec=True, need_review_extra_prompt=True)
    return parser.parse_args()


def load_template(prompt_dir: Path, name: str) -> Template:
    path = prompt_dir / name
    if not path.is_file():
        raise FileNotFoundError(f"Prompt template not found: {path}")
    return Template(path.read_text(encoding="utf-8"))


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def resolve_path(path_value: str | Path, base_dir: Path) -> Path:
    path = Path(path_value).expanduser()
    if not path.is_absolute():
        path = base_dir / path
    return path.resolve()


def make_codex_log_path(task_log_dir: Path, task_type: str, iteration: int) -> Path:
    start_ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    return task_log_dir / f"{task_type}__iter{iteration:02d}__{start_ts}.log"


def run_codex(
    project_root: Path,
    prompt: str,
    out_file: Path,
    task_log_dir: Path,
    task_type: str,
    iteration: int,
) -> Path:
    log_path = make_codex_log_path(task_log_dir, task_type, iteration)
    process = subprocess.Popen(
        CODEX_EXEC_CMD + ["--cd", str(project_root), "--output-last-message", str(out_file), "-"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=project_root,
    )

    assert process.stdin is not None
    assert process.stdout is not None

    with log_path.open("wb") as log_file:
        process.stdin.write(prompt.encode("utf-8"))
        process.stdin.close()

        while True:
            chunk = process.stdout.read(8192)
            if not chunk:
                break
            # Keep raw codex output as-is while duplicating it to terminal and log file.
            sys.stdout.buffer.write(chunk)
            sys.stdout.buffer.flush()
            log_file.write(chunk)
            log_file.flush()

    return_code = process.wait()
    if return_code != 0:
        raise RuntimeError(f"codex failed: exit={return_code}, log={log_path}")
    if not out_file.is_file():
        raise RuntimeError(f"codex output file missing: {out_file}, log={log_path}")
    return log_path


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


def implement_loop(
    spec: Path,
    project_root: Path,
    state_dir: Path,
    task_log_dir: Path,
    prompt_dir: Path,
    max_iterations: int,
    implement_extra_prompt: str,
) -> None:
    initial_tpl = load_template(prompt_dir, "implement_initial.prompt.md")
    continue_tpl = load_template(prompt_dir, "implement_continue.prompt.md")
    check_tpl = load_template(prompt_dir, "check.prompt.md")
    implement_instruction = implement_extra_prompt.strip() or f"根据 {spec} 实施。"

    todo_file = state_dir / "todo.txt"
    write_text(todo_file, "")

    for i in range(1, max_iterations + 1):
        print(f"[implement-loop] iteration {i}", flush=True)

        if i == 1:
            implement_prompt = initial_tpl.safe_substitute(
                implement_instruction=implement_instruction,
            )
        else:
            implement_prompt = continue_tpl.safe_substitute(todo=todo_file.read_text(encoding="utf-8"))

        render_to_state(state_dir, "implement_prompt.txt", implement_prompt)
        run_codex(
            project_root,
            implement_prompt,
            state_dir / f"implement_{i}.out",
            task_log_dir,
            "implement",
            i,
        )

        check_prompt = check_tpl.safe_substitute(spec=str(spec))
        render_to_state(state_dir, "check_prompt.txt", check_prompt)
        check_out = state_dir / f"check_{i}.out"
        run_codex(project_root, check_prompt, check_out, task_log_dir, "check", i)

        todo = parse_str_list_json(check_out.read_text(encoding="utf-8"), "todo")
        write_text(todo_file, "\n".join(todo))

        if not todo:
            print(f"[implement-loop] {spec} fully implemented.", flush=True)
            return

    raise RuntimeError(f"[implement-loop] reached max iterations: {max_iterations}")


def review_loop(
    project_root: Path,
    state_dir: Path,
    task_log_dir: Path,
    prompt_dir: Path,
    max_iterations: int,
    review_extra_prompt: str,
) -> None:
    review_tpl = load_template(prompt_dir, "review.prompt.md")
    fix_tpl = load_template(prompt_dir, "fix.prompt.md")
    review_scope_instruction = review_extra_prompt.strip() or "请查看项目工作树中的所有代码变更。"

    issues_file = state_dir / "issues.txt"
    write_text(issues_file, "")

    for i in range(1, max_iterations + 1):
        print(f"[review-loop] iteration {i}", flush=True)

        review_prompt = review_tpl.safe_substitute(
            review_scope_instruction=review_scope_instruction
        )
        render_to_state(state_dir, "review_prompt.txt", review_prompt)
        review_out = state_dir / f"review_{i}.out"
        run_codex(project_root, review_prompt, review_out, task_log_dir, "review", i)

        issues = parse_str_list_json(review_out.read_text(encoding="utf-8"), "issues")
        write_text(issues_file, "\n".join(issues))

        if not issues:
            print("[review-loop] all issues fixed.", flush=True)
            return

        fix_prompt = fix_tpl.safe_substitute(issues=issues_file.read_text(encoding="utf-8"))
        render_to_state(state_dir, "fix_prompt.txt", fix_prompt)
        run_codex(project_root, fix_prompt, state_dir / f"fix_{i}.out", task_log_dir, "fix", i)

    raise RuntimeError(f"[review-loop] reached max iterations: {max_iterations}")


def main() -> int:
    args = parse_args()
    project_root = resolve_path(args.project_root, Path.cwd())
    if not project_root.is_dir():
        print(f"Project root not found: {project_root}", file=sys.stderr)
        return 2

    state_dir = resolve_path(args.state_dir, project_root)
    prompt_dir = resolve_path(args.prompt_dir, project_root)
    state_dir.mkdir(parents=True, exist_ok=True)
    task_start_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    task_log_dir = state_dir / "logs" / f"{args.mode}__{task_start_ts}"
    task_log_dir.mkdir(parents=True, exist_ok=True)
    print(f"[logs] task log dir: {task_log_dir}", flush=True)

    try:
        if args.mode == "implement-loop":
            spec_path = resolve_path(args.spec, project_root)
            implement_loop(
                spec_path,
                project_root,
                state_dir,
                task_log_dir,
                prompt_dir,
                args.max_iterations,
                args.implement_extra_prompt,
            )
        elif args.mode == "review-loop":
            review_loop(
                project_root,
                state_dir,
                task_log_dir,
                prompt_dir,
                args.max_iterations,
                args.review_extra_prompt,
            )
        elif args.mode == "all":
            spec_path = resolve_path(args.spec, project_root)
            implement_loop(
                spec_path,
                project_root,
                state_dir,
                task_log_dir,
                prompt_dir,
                args.max_iterations,
                args.implement_extra_prompt,
            )
            review_loop(
                project_root,
                state_dir,
                task_log_dir,
                prompt_dir,
                args.max_iterations,
                args.review_extra_prompt,
            )
        else:
            raise ValueError(f"Unknown mode: {args.mode}")
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
