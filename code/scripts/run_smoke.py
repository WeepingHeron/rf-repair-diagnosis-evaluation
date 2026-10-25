"""Run a minimal ngspice batch simulation and retain native evidence."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NETLIST = ROOT / "circuits" / "smoke" / "rc_lowpass.cir"
OUTPUT_DIR = ROOT / "build" / "smoke"
LOG_PATH = OUTPUT_DIR / "ngspice.log"
RAW_PATH = OUTPUT_DIR / "rc_lowpass.raw"


def main() -> int:
    executable = shutil.which("ngspice")
    if executable is None:
        raise SystemExit("ngspice was not found on PATH")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [executable, "-b", "-o", str(LOG_PATH), "-r", str(RAW_PATH), str(NETLIST)],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
        timeout=30,
    )

    if completed.returncode != 0:
        raise SystemExit(
            "ngspice smoke test failed "
            f"(exit={completed.returncode}, stderr={completed.stderr.strip()!r})"
        )
    if not RAW_PATH.is_file() or RAW_PATH.stat().st_size == 0:
        raise SystemExit("ngspice exited successfully but produced no raw evidence")

    print(f"PASS: ngspice produced {RAW_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

