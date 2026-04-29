from __future__ import annotations

from pathlib import Path
from typing import BinaryIO


def stream_bytes_to_stdout_and_log(chunk: bytes, *, log_file: BinaryIO | Path | None = None) -> None:
    import sys

    sys.stdout.buffer.write(chunk)
    sys.stdout.buffer.flush()
    if log_file is not None:
        if isinstance(log_file, Path):
            with log_file.open("ab") as out:
                out.write(chunk)
                out.flush()
            return
        log_file.write(chunk)
        log_file.flush()
