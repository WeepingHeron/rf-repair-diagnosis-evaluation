"""Native ngspice execution and S-parameter evidence parsing."""

from __future__ import annotations

import math
import shutil
import subprocess
from pathlib import Path
from typing import Any


def _generated_deck(source: str, data_path: Path) -> str:
    lines = source.splitlines()
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines or lines[-1].strip().lower() != ".end":
        raise ValueError("source netlist must end with .end")
    body = "\n".join(lines[:-1])
    return (
        f"{body}\n"
        ".control\n"
        "set wr_singlescale\n"
        "set wr_vecnames\n"
        "run\n"
        f"wrdata {data_path} db(s_1_1) db(s_2_1) db(s_2_2)\n"
        "quit\n"
        ".endc\n"
        ".end\n"
    )


def _read_table(path: Path) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    with path.open(encoding="utf-8") as handle:
        header = handle.readline().split()
        expected = ["frequency", "db(s_1_1)", "db(s_2_1)", "db(s_2_2)"]
        if header != expected:
            raise ValueError(f"unexpected ngspice columns: {header!r}")
        for line in handle:
            values = [float(value) for value in line.split()]
            if len(values) != len(expected):
                raise ValueError(f"unexpected ngspice row: {line!r}")
            rows.append(dict(zip(expected, values, strict=True)))
    if not rows:
        raise ValueError("ngspice produced an empty S-parameter table")
    return rows


def _nearest(rows: list[dict[str, float]], frequency: float) -> dict[str, float]:
    return min(rows, key=lambda row: abs(row["frequency"] - frequency))


def _measure(rows: list[dict[str, float]], spec: dict[str, Any]) -> dict[str, Any]:
    if not rows or not all(
        all(math.isfinite(row[key]) for key in
            ("frequency", "db(s_1_1)", "db(s_2_1)", "db(s_2_2)")) for row in rows
    ):
        raise ValueError("S-parameter evidence must contain finite samples")
    if any(a["frequency"] >= b["frequency"] for a, b in zip(rows, rows[1:])):
        raise ValueError("frequency grid must be strictly increasing")
    frequencies = spec["measurement_frequencies_hz"]
    if not isinstance(frequencies, dict):
        raise TypeError("measurement_frequencies_hz must be an object")

    peak = max(rows, key=lambda row: row["db(s_2_1)"])
    samples: dict[str, dict[str, float]] = {}
    for name, requested in frequencies.items():
        row = _nearest(rows, float(requested))
        tolerance = float(spec.get("measurement_frequency_tolerance_hz", 1.0))
        if not math.isfinite(tolerance) or tolerance < 0:
            raise ValueError("invalid measurement frequency tolerance")
        if abs(row["frequency"] - float(requested)) > tolerance:
            raise ValueError(f"missing required measurement frequency: {name}")
        samples[name] = {
            "requested_frequency_hz": float(requested),
            "measured_frequency_hz": row["frequency"],
            "s11_db": row["db(s_1_1)"],
            "s21_db": row["db(s_2_1)"],
            "s22_db": row["db(s_2_2)"],
        }

    target = float(spec["target_center_frequency_hz"])
    metrics = {
        "simulation_converged": True,
        "point_count": len(rows),
        "peak_s21_db": peak["db(s_2_1)"],
        "peak_frequency_hz": peak["frequency"],
        "peak_frequency_relative_error": abs(peak["frequency"] - target) / target,
        "samples": samples,
    }
    if not math.isfinite(float(metrics["peak_s21_db"])):
        raise ValueError("simulation produced a non-finite peak S21")
    return metrics


def run_sparameter_simulation(
    source_netlist: Path,
    spec: dict[str, Any],
    output_dir: Path,
    *,
    cwd: Path,
    timeout_seconds: int = 30,
) -> dict[str, Any]:
    """Run ngspice and return measured evidence or an explicit failure record."""

    executable = shutil.which("ngspice")
    if executable is None:
        raise RuntimeError("ngspice was not found on PATH")

    output_dir.mkdir(parents=True, exist_ok=True)
    data_path = output_dir / "sparams.tsv"
    log_path = output_dir / "ngspice.log"
    generated_netlist = output_dir / f"{source_netlist.stem}.generated.cir"
    data_path.unlink(missing_ok=True)
    generated_netlist.write_text(
        _generated_deck(source_netlist.read_text(encoding="utf-8"), data_path),
        encoding="utf-8",
    )

    try:
        completed = subprocess.run(
            [executable, "-b", "-o", str(log_path), str(generated_netlist)],
            cwd=cwd,
            check=False,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return {
            "simulation_converged": False,
            "failure_reason": "SIMULATION_TIMEOUT",
        }

    if completed.returncode != 0:
        return {
            "simulation_converged": False,
            "failure_reason": "NGSPICE_NONZERO_EXIT",
            "returncode": completed.returncode,
        }
    if not data_path.is_file() or data_path.stat().st_size == 0:
        return {
            "simulation_converged": False,
            "failure_reason": "MISSING_SPARAMETER_EVIDENCE",
        }
    try:
        return _measure(_read_table(data_path), spec)
    except (ValueError, OverflowError):
        return {
            "simulation_converged": False,
            "failure_reason": "INVALID_SPARAMETER_EVIDENCE",
        }
