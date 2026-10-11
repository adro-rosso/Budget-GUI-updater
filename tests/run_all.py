"""Run every smoke test in this folder in a fresh interpreter and report.
Usage:  python tests/run_all.py            (all smoke tests)
        python tests/run_all.py 11 13      (just those numbers)
Each test builds the app against a temp data file; the real budget_data.json is never touched."""
import os, re, subprocess, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
env = dict(os.environ, PYTHONIOENCODING="utf-8")
want = set(sys.argv[1:])
tests = sorted(HERE.glob("smoke_test*.py"), key=lambda p: int(re.sub(r"\D", "", p.stem) or 1))
tests += [HERE / "engine_check11.py", HERE / "engine_check12.py"]
failed = []
for t in tests:
    num = re.sub(r"\D", "", t.stem) or "1"
    if want and num not in want and t.name not in want:
        continue
    t0 = time.time()
    r = subprocess.run([sys.executable, str(t)], capture_output=True, text=True, env=env, timeout=600)
    ok = "PASSED" in r.stdout or r.stdout.strip().endswith("OK") or " OK" in r.stdout.splitlines()[-1:][0] if r.stdout.strip() else False
    ok = ok and r.returncode == 0
    print(f"{'PASS' if ok else 'FAIL'}  {t.name:22s} {time.time() - t0:5.1f}s")
    if not ok:
        failed.append(t.name)
        tail = [ln for ln in (r.stdout + r.stderr).splitlines() if ln.strip() and "invalid command name" not in ln and "while executing" not in ln][-6:]
        for ln in tail:
            print("      " + ln[:160])
print("\n" + ("ALL PASSED" if not failed else f"{len(failed)} FAILED: {', '.join(failed)}"))
sys.exit(1 if failed else 0)
