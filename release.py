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

import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

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


def build_exe() -> None:
    print("\n=== Building exe (this takes ~60 sec) ===")
    run([sys.executable, "-m", "PyInstaller",
         "--onefile", "--windowed",
         "--name", "BudgetPlanner",
         "--icon", "icon.ico",
         "--add-data", "icon.png;.",
         "--add-data", "icon.ico;.",
         "--hidden-import", "pypdf",
         "--noconfirm",
         "budget_gui.py"])
    if not EXE_PATH.exists():
        fail(f"PyInstaller did not produce {EXE_PATH}")


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    if len(sys.argv) < 2:
        fail('Usage: python release.py "what changed in this release"')
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

    # 1. Bump version
    old_ver, text = read_version()
    new_ver = bump_patch(old_ver)
    print(f"\nVersion: {old_ver}  ->  {new_ver}")
    write_version(new_ver, text)

    # 2. Build
    build_exe()

    # 3. SHA256
    sha = sha256_of(EXE_PATH)
    print(f"sha256: {sha}")

    # 4. Manifest
    owner, repo = detect_repo()
    download_url = f"https://github.com/{owner}/{repo}/releases/download/v{new_ver}/BudgetPlanner.exe"
    manifest = {
        "version": new_ver,
        "download_url": download_url,
        "sha256": sha,
        "notes": notes,
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
