"""Local process supervisor: regular-file output, never a session-owned pipe.

Execution helper only; callers retain all dataset/release/approval gates.
Receipts describe process execution, not scientific or Data Gate success.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def write_receipt(path, value):
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, sort_keys=True, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def launch(argv, cwd, directory):
    if not argv or any(type(arg) is not str or not arg for arg in argv):
        raise ValueError("nonempty argument vector required")
    cwd = Path(cwd).resolve(strict=True)
    directory = Path(directory).absolute()
    directory.mkdir(mode=0o700)  # Existing attempts must never be reused.
    write_receipt(directory / "REQUEST.json", dict(argv=argv, cwd=str(cwd)))
    with (directory / "runtime.log").open("xb", buffering=0) as output:
        process = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "--supervise", str(directory)],
            cwd=cwd, stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT,
            start_new_session=True, close_fds=True)
    # Popen returning is not child success; RETURNED.json is the terminal receipt.
    return process.pid


def supervise(directory):
    directory = Path(directory).resolve(strict=True)
    request = json.loads((directory / "REQUEST.json").read_text())
    start = time.monotonic()
    write_receipt(directory / "STARTED.json", dict(supervisor_pid=os.getpid(), started_unix=time.time()))
    try:
        # stdout/stderr are the regular log inherited from launch(), not pipes.
        child = subprocess.run(request["argv"], cwd=request["cwd"],
                               stdin=subprocess.DEVNULL, close_fds=True)
    except Exception as exc:
        write_receipt(directory / "LAUNCH_ERROR.json", dict(error_type=type(exc).__name__))
        raise
    write_receipt(directory / "RETURNED.json", dict(child_returncode=child.returncode,
                  elapsed_seconds=time.monotonic()-start, finished_unix=time.time()))
    return child.returncode


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--supervise", required=True)
    result = supervise(parser.parse_args().supervise)
    sys.exit(result if result >= 0 else 128-result)
