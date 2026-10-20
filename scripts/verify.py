"""No credentials or cloud calls. Stop at the first failed verification stage."""

from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
commands = [
    [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
    [shutil.which("node") or "node", "tests/audio.test.mjs"],
    [sys.executable, "-m", "build", "--wheel"],
]
for command in commands:
    print("Running:", " ".join(command), flush=True)
    try:
        result = subprocess.run(command, cwd=ROOT)
    except FileNotFoundError:
        sys.exit("Install Node 22+ and the Python dev extra before verifying.")
    if result.returncode:
        sys.exit(result.returncode)
wheel = max((ROOT / "dist").glob("*.whl"), key=lambda path: path.stat().st_mtime)
with zipfile.ZipFile(wheel) as package:
    names = package.namelist()
    for asset in ("index.html", "style.css", "app.js", "audio.js", "capture-worklet.js", "mark.svg", "galaxy.css", "workspace.css", "integration.css", "orb.js", "fonts/Manrope.ttf", "fonts/Manrope-OFL.txt", "fonts/Newsreader-OFL.txt", "images/thread-sphere.png"):
        assert "thread_voice/web/" + asset in names, f"Missing packaged asset: {asset}"
    assert not any(name.endswith((".env", ".sqlite3")) for name in names)
    assert any(name.endswith("/THIRD_PARTY_NOTICES.md") for name in names), "Restored frontend notices must ship in the wheel"
print("Verified backend, browser audio, wheel build, and packaged web assets.")
