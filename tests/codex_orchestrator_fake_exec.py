import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast


def make_fake_codex_exec(
    *,
    payload_for_call: Callable[..., Any] | None = None,
    raw_output_for_call: Callable[..., str] | None = None,
    captured_prompts: list[str] | None = None,
) -> Callable[..., str]:
    if (payload_for_call is None) == (raw_output_for_call is None):
        raise ValueError("Provide exactly one of payload_for_call or raw_output_for_call")

    def fake_codex_exec(request: Any) -> str:
        node_id = request.node_id
        step = request.step
        attempt = request.attempt
        prompt = request.prompt
        if captured_prompts is not None:
            captured_prompts.append(prompt)

        kwargs: dict[str, Any] = {
            "node_id": node_id,
            "step": step,
            "attempt": attempt,
            "prompt": prompt,
        }
        if raw_output_for_call is not None:
            out_text = raw_output_for_call(**kwargs)
        else:
            assert payload_for_call is not None
            out_text = json.dumps(payload_for_call(**kwargs), ensure_ascii=False)

        Path(request.out_file).write_text(out_text, encoding="utf-8")
        log_path = Path(request.task_log_dir) / f"fake_{step}_{attempt}.log"
        log_path.write_text("ok", encoding="utf-8")
        return str(log_path)

    return cast(Callable[..., str], fake_codex_exec)
