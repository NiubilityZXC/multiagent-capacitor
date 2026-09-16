import json
from pathlib import Path
import subprocess
import sys
import time

import pytest
from experiments.audit_cap import durable_local_job as job


def returned(path):
    deadline = time.monotonic()+10
    while time.monotonic()<deadline:
        try:
            return json.loads((path/"RETURNED.json").read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            time.sleep(.02)
    raise AssertionError("missing terminal receipt")


def test_parent_exit_does_not_break_child_stdout(tmp_path):
    run = tmp_path/"job"
    script = Path(job.__file__).resolve()
    code = (
        "import sys; sys.path.insert(0,sys.argv[1]); import durable_local_job as j; "
        "print(j.launch([sys.executable,'-u','-c',"
        "\"import time; time.sleep(.3); print('AFTER_PARENT_EXIT'); import sys; print('STDERR',file=sys.stderr)\"],"
        "sys.argv[2],sys.argv[3]),flush=True)"
    )
    parent = subprocess.run([sys.executable,"-c",code,str(script.parent),str(tmp_path),str(run)],
                            capture_output=True, text=True, timeout=5)
    assert parent.returncode == 0 and parent.stdout.strip().isdigit()
    assert returned(run)["child_returncode"] == 0
    assert "AFTER_PARENT_EXIT" in (run/"runtime.log").read_text()
    assert "STDERR" in (run/"runtime.log").read_text()


@pytest.mark.parametrize("code",[0,7])
def test_actual_exit_and_append_only(tmp_path,code):
    path=tmp_path/"job"
    job.launch([sys.executable,"-c",f"raise SystemExit({code})"],tmp_path,path)
    assert returned(path)["child_returncode"]==code
    with pytest.raises(FileExistsError):
        job.launch([sys.executable,"-c","pass"],tmp_path,path)


def test_missing_executable_never_success(tmp_path):
    path=tmp_path/"job"
    job.launch([str(tmp_path/"absent")],tmp_path,path)
    deadline=time.monotonic()+10
    while not (path/"LAUNCH_ERROR.json").exists() and time.monotonic()<deadline:
        time.sleep(.02)
    assert (path/"LAUNCH_ERROR.json").exists()
    assert not (path/"RETURNED.json").exists()
