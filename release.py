"""
release.py - one-command release workflow for Budget Planner.

    python release.py "fixed bank account sizing"

What it does:
    1. Bumps APP_VERSION in budget_gui.py (e.g. 1.0.0 -> 1.0.1)
    2. Builds BudgetPlanner.exe with PyInstaller
    3. Computes the exe's SHA256
    4. Writes version.json with the new version, download URL, sha, notes
    5. Commits budget_gui.py + version.json, pushes to GitHub
    6. Creates a GitHub Release and uploads the exe

After this runs, every user running the .exe will see
"Update available" on their next launch and can install with one click.

One-time setup required (see SETUP section in the chat).
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

HISTORY_LIMIT = 30  # keep the most recent N releases in version.json

HERE = Path(__file__).parent
BUDGET_GUI = HERE / "budget_gui.py"
VERSION_JSON = HERE / "version.json"
EXE_PATH = HERE / "dist" / "BudgetPlanner.exe"


def fail(msg: str) -> None:
    print(f"\n!! {msg}", file=sys.stderr)
    sys.exit(1)


def run(cmd, **kw):
    print(f"$ {' '.join(str(c) for c in cmd)}")
    r = subprocess.run(cmd, check=False, **kw)
    if r.returncode != 0:
        fail(f"Command failed (exit {r.returncode}): {cmd}")
    return r


def require_tool(name: str, hint: str) -> None:
    if shutil.which(name) is None:
        fail(f"'{name}' not found on PATH. {hint}")


def read_version() -> tuple[str, str]:
    text = BUDGET_GUI.read_text(encoding="utf-8")
    m = re.search(r'^APP_VERSION\s*=\s*"([\d.]+)"', text, re.M)
    if not m:
        fail("APP_VERSION = \"X.Y.Z\" line not found in budget_gui.py")
    return m.group(1), text


def bump_patch(v: str) -> str:
    parts = v.split(".")
    while len(parts) < 3:
        parts.append("0")
    parts[2] = str(int(parts[2]) + 1)
    return ".".join(parts[:3])


def write_version(new_version: str, text: str) -> None:
    new_text = re.sub(
        r'^APP_VERSION\s*=\s*"[\d.]+"',
        f'APP_VERSION = "{new_version}"',
        text, count=1, flags=re.M,
    )
    BUDGET_GUI.write_text(new_text, encoding="utf-8")


def detect_repo() -> tuple[str, str]:
    r = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        fail("No git remote 'origin'. See setup instructions.")
    url = r.stdout.strip()
    m = re.search(r"github\.com[:/]([\w.-]+?)/([\w.-]+?)(?:\.git)?$", url)
    if not m:
        fail(f"Couldn't parse GitHub URL from remote: {url}")
    return m.group(1), m.group(2)


def git_clean_check() -> None:
    r = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
    dirty = [ln for ln in r.stdout.splitlines()
             if ln.strip() and not any(ln.endswith(f) for f in
                 ("budget_gui.py", "version.json", "release.py"))]
    if dirty:
        print("\n!! You have uncommitted changes other than budget_gui.py / version.json:")
        for ln in dirty:
            print(" ", ln)
        ans = input("Continue anyway? [y/N]: ").strip().lower()
        if ans != "y":
            fail("Aborted — commit or stash other changes first.")


def check_exe_not_running() -> None:
    """If BudgetPlanner.exe is running (or the file is otherwise locked),
    PyInstaller can't overwrite it. Detect this BEFORE bumping the version."""
    if not EXE_PATH.exists():
        return
    try:
        # Open-for-append with truncate semantics — Windows refuses this on
        # a running exe. We only test the lock; we don't actually modify.
        with open(EXE_PATH, "ab"):
            pass
        # On Windows, even a successful open isn't conclusive — try a rename-
        # in-place which does fail on a running exe.
        try:
            EXE_PATH.rename(EXE_PATH)
        except OSError:
            fail(f"{EXE_PATH.name} appears to be running. Close it and re-run.")
    except PermissionError:
        fail(f"{EXE_PATH.name} appears to be running. Close it and re-run.")


def mypyc_hidden_imports() -> list[str]:
    """charset_normalizer (a pdfminer.six dependency) is mypyc-compiled and
    imports a hashed top-level helper module (e.g. 81d243bd2c585b0f4821__mypyc)
    that PyInstaller's analysis can't see. Without it the frozen app raises
    ModuleNotFoundError the first time the pdfminer fallback is used, which
    surfaces as "Install the fallback parser" in the import dialog."""
    import glob
    import site
    names: set[str] = set()
    dirs = list(site.getsitepackages()) + [site.getusersitepackages()]
    for d in dirs:
        for f in glob.glob(str(Path(d) / "*__mypyc*.pyd")):
            names.add(Path(f).name.split(".")[0])
    args: list[str] = []
    for n in sorted(names):
        args += ["--hidden-import", n]
    return args


def pyinstaller_args() -> list[str]:
    return [sys.executable, "-m", "PyInstaller",
            "--onefile", "--windowed",
            "--name", "BudgetPlanner",
            "--icon", "icon.ico",
            "--add-data", "icon.png;.",
            "--add-data", "icon.ico;.",
            "--hidden-import", "pypdf",
            "--hidden-import", "pdfminer.high_level",
            "--collect-all", "pdfminer",
            "--collect-all", "charset_normalizer",
            *mypyc_hidden_imports(),
            "--noconfirm",
            "budget_gui.py"]


def build_exe() -> None:
    print("\n=== Building exe (this takes ~60 sec) ===")
    run(pyinstaller_args())
    if not EXE_PATH.exists():
        fail(f"PyInstaller did not produce {EXE_PATH}")


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "--build-only":
        # Rebuild dist/BudgetPlanner.exe from the working tree. No version
        # bump, no commit, nothing published.
        check_exe_not_running()
        build_exe()
        print(f"\nBuilt {EXE_PATH} (no version bump, nothing published).")
        return
    if len(sys.argv) < 2:
        fail('Usage: python release.py "what changed in this release"  |  python release.py --build-only')
    notes = sys.argv[1].strip()
    if not notes:
        fail("Release notes can't be empty.")

    require_tool("git", "Install git: https://git-scm.com/download/win")
    require_tool("gh",  "Install GitHub CLI: winget install GitHub.cli  (then: gh auth login)")
    if not BUDGET_GUI.exists():
        fail(f"budget_gui.py not found next to release.py")
    if not (HERE / "icon.ico").exists():
        fail("icon.ico missing — first run once:  python -c \"from PIL import Image; Image.open('icon.png').convert('RGBA').save('icon.ico', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])\"")

    git_clean_check()

    # Fail fast if the exe is running — PyInstaller can't overwrite it.
    check_exe_not_running()

    # 1. Bump version
    old_ver, text = read_version()
    new_ver = bump_patch(old_ver)
    print(f"\nVersion: {old_ver}  ->  {new_ver}")
    write_version(new_ver, text)

    # 2. Build — roll back the version bump if it fails, so the next attempt
    # doesn't skip a number.
    try:
        build_exe()
    except SystemExit:
        print(f"\n!! Build failed — rolling back version to {old_ver}")
        write_version(old_ver, text)
        raise

    # 3. SHA256
    sha = sha256_of(EXE_PATH)
    print(f"sha256: {sha}")

    # 4. Manifest (with rolling history of past releases)
    owner, repo = detect_repo()
    download_url = f"https://github.com/{owner}/{repo}/releases/download/v{new_ver}/BudgetPlanner.exe"
    today = _dt.date.today().isoformat()

    history: list = []
    if VERSION_JSON.exists():
        try:
            prev = json.loads(VERSION_JSON.read_text(encoding="utf-8"))
            history = list(prev.get("history") or [])
            # seed history with the previous release if it wasn't recorded there
            if not history and prev.get("version"):
                history.append({
                    "version": str(prev.get("version")),
                    "date": str(prev.get("date") or today),
                    "notes": str(prev.get("notes") or ""),
                })
        except Exception:
            history = []

    history.insert(0, {"version": new_ver, "date": today, "notes": notes})
    history = history[:HISTORY_LIMIT]

    manifest = {
        "version": new_ver,
        "date": today,
        "download_url": download_url,
        "sha256": sha,
        "notes": notes,
        "history": history,
    }
    VERSION_JSON.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {VERSION_JSON}")

    # 5. Commit + push
    print("\n=== Git commit + push ===")
    run(["git", "add", "budget_gui.py", "version.json"])
    run(["git", "commit", "-m", f"Release v{new_ver}: {notes}"])
    run(["git", "push"])

    # 6. GitHub Release + exe upload
    print("\n=== Publishing GitHub Release ===")
    run(["gh", "release", "create", f"v{new_ver}",
         str(EXE_PATH),
         "--title", f"v{new_ver}",
         "--notes", notes])

    print(f"\nDone. v{new_ver} released.")
    print("Running .exe instances will see the update on next launch.")
    print(f"Release page: https://github.com/{owner}/{repo}/releases/tag/v{new_ver}")


if __name__ == "__main__":
    main()
