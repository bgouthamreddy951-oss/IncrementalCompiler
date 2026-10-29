"""
Benchmark the Incremental Compiler project.

Save this file as benchmark.py in the same folder as compiler.py, then run:
    python benchmark.py

The script runs five trials each for:
  1. Cached builds (no source changes)
  2. Incremental builds (change math.lang each trial)
  3. Full builds (temporarily hide the cache for each trial)

It records wall-clock time for the complete Python compiler process, including
Python startup. It restores math.lang and .compiler_cache.json at the end.
"""
import os
import re
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EXAMPLES = ROOT / "examples"
MATH_FILE = EXAMPLES / "math.lang"
CACHE_FILE = ROOT / ".compiler_cache.json"
TRIALS = 5

RETURN_PATTERN = re.compile(
    r"(return\s+a\s*\+\s*b\s*\+\s*)(-?\d+)(\s*;)",
    re.IGNORECASE,
)


def run_compiler():
    start = time.perf_counter()
    result = subprocess.run(
        [sys.executable, "compiler.py", "examples"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    elapsed_ms = (time.perf_counter() - start) * 1000
    output = result.stdout + ("\n" + result.stderr if result.stderr else "")
    return elapsed_ms, result.returncode, output


def median(values):
    return statistics.median(values) if values else float("nan")


def get_output_number(output):
    match = re.search(
        r"\[run\]\s+Program output:\s*\n\s*(-?\d+(?:\.\d+)?)",
        output,
    )
    return match.group(1) if match else "not detected"


def print_trial(label, index, elapsed, output, expected_recompile=None):
    if expected_recompile == "incremental":
        verified = (
            "[build] Recompiled 3 of 4 modules." in output
            and "math.lang" in output
            and "util.lang" in output
            and "main.lang" in output
        )
        status = "VERIFIED incremental rebuild" if verified else "NOT VERIFIED"
    elif expected_recompile == "full":
        verified = "[build] Recompiled 4 of 4 modules." in output
        status = "VERIFIED full rebuild" if verified else "NOT VERIFIED"
    elif expected_recompile == "cached":
        verified = (
            "[hash] No AST changes detected." in output
            and "[cache] All modules are up to date." in output
        )
        status = "VERIFIED cached build" if verified else "NOT VERIFIED"
    else:
        verified = True
        status = "setup"

    print(
        f"{label} run {index}: {elapsed:.2f} ms | "
        f"output={get_output_number(output)} | {status}"
    )
    if not verified:
        print("  Build log did not match the expected scenario.")
        for line in output.splitlines():
            if any(tag in line for tag in ("[hash]", "[cache]", "[build]", "Changed modules:", "Modules requiring recompilation:", "[run] Program output:", "Execution failed", "Compilation failed", "Semantic errors:", "Dependency error:")):
                print("   ", line)
    return verified


def main():
    if not (ROOT / "compiler.py").exists() or not MATH_FILE.exists():
        print("ERROR: Save benchmark.py beside compiler.py in the project root.")
        raise SystemExit(1)

    original_math = MATH_FILE.read_text(encoding="utf-8")
    original_cache_exists = CACHE_FILE.exists()
    original_cache = CACHE_FILE.read_bytes() if original_cache_exists else None

    match = RETURN_PATTERN.search(original_math)
    if not match:
        print(
            "ERROR: Could not find a line like 'return a + b + 13;' in "
            "examples/math.lang. No files were changed."
        )
        raise SystemExit(1)

    original_constant = int(match.group(2))
    cached_times = []
    incremental_times = []
    full_times = []
    all_verified = True

    try:
        print("=== 1. CACHED BUILD: five trials ===")
        # Bring the cache in sync with the source before measuring cache hits.
        setup_ms, setup_code, setup_output = run_compiler()
        if setup_code != 0 or "Execution completed successfully." not in setup_output:
            print("ERROR: Setup build did not complete successfully.")
            print(setup_output)
            raise RuntimeError("Setup build failed.")

        for i in range(1, TRIALS + 1):
            elapsed, code, output = run_compiler()
            cached_times.append(elapsed)
            verified = print_trial("Cached", i, elapsed, output, "cached")
            all_verified &= (code == 0 and verified)

        print("\n=== 2. INCREMENTAL BUILD: five source changes ===")
        for i in range(1, TRIALS + 1):
            # Use a different integer each time so the AST really changes.
            new_constant = original_constant + i
            current = MATH_FILE.read_text(encoding="utf-8")
            current_match = RETURN_PATTERN.search(current)
            if not current_match:
                raise RuntimeError("Could not find the arithmetic return statement.")
            changed = RETURN_PATTERN.sub(
                lambda m: f"{m.group(1)}{new_constant}{m.group(3)}",
                current,
                count=1,
            )
            MATH_FILE.write_text(changed, encoding="utf-8")

            elapsed, code, output = run_compiler()
            incremental_times.append(elapsed)
            verified = print_trial("Incremental", i, elapsed, output, "incremental")
            all_verified &= (code == 0 and verified)

        print("\n=== 3. FULL BUILD: five trials with cache disabled ===")
        for i in range(1, TRIALS + 1):
            cache_was_present = CACHE_FILE.exists()
            trial_cache = CACHE_FILE.read_bytes() if cache_was_present else None
            hidden_cache = ROOT / ".compiler_cache.benchmark_backup"
            if hidden_cache.exists():
                hidden_cache.unlink()
            if cache_was_present:
                os.replace(CACHE_FILE, hidden_cache)
            try:
                elapsed, code, output = run_compiler()
            finally:
                # Remove the cache created by this trial and restore the prior cache.
                if CACHE_FILE.exists():
                    CACHE_FILE.unlink()
                if cache_was_present and hidden_cache.exists():
                    os.replace(hidden_cache, CACHE_FILE)
            full_times.append(elapsed)
            verified = print_trial("Full", i, elapsed, output, "full")
            all_verified &= (code == 0 and verified)

    except Exception as exc:
        print(f"\nBenchmark stopped: {exc}")
    finally:
        # Restore the exact source file and cache state present before the test.
        MATH_FILE.write_text(original_math, encoding="utf-8")
        if CACHE_FILE.exists():
            CACHE_FILE.unlink()
        if original_cache_exists and original_cache is not None:
            CACHE_FILE.write_bytes(original_cache)

    print("\n=== MEDIAN WALL-CLOCK TIMES ===")
    print(f"Cached build median:      {median(cached_times):.2f} ms")
    print(f"Incremental build median: {median(incremental_times):.2f} ms")
    print(f"Full build median:        {median(full_times):.2f} ms")
    print("\nNote: times include Python startup and process overhead.")
    print("Each scenario is verified from the compiler's own build log.")
    print("Source file and cache have been restored to their original state.")
    if not all_verified:
        print("WARNING: At least one trial did not match the expected build scenario.")
        print("Do not report that scenario as verified until its build logs are checked.")


if __name__ == "__main__":
    main()
