"""Set up STAMINA as needed, serve the complete site, and open its browser tab."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen
import webbrowser

ROOT = Path(__file__).resolve().parent
STATE = ROOT / ".runtime" / "launcher.json"
PYTHON = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def run(command, cwd=ROOT):
    subprocess.run([str(item) for item in command], cwd=cwd, check=True)


def fingerprint(paths):
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(str(path.relative_to(ROOT)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def frontend_fingerprint():
    # Metadata avoids reading hundreds of MB of generated terrain on every start.
    paths = list((ROOT / "frontend" / "src").rglob("*"))
    paths += list((ROOT / "frontend" / "public").rglob("*"))
    paths += list((ROOT / "frontend").glob("*.json"))
    paths += list((ROOT / "frontend").glob("*.ts"))
    paths += [ROOT / "frontend" / "index.html"]
    digest = hashlib.sha256()
    for path in sorted(path for path in paths if path.is_file()):
        stat = path.stat()
        digest.update(f"{path.relative_to(ROOT)}:{stat.st_size}:{stat.st_mtime_ns}\n".encode())
    return digest.hexdigest()


def save_state(state):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    pending = STATE.with_suffix(".tmp")
    pending.write_text(json.dumps(state), encoding="utf-8")
    pending.replace(STATE)


def setup():
    if sys.version_info < (3, 12):
        raise RuntimeError("Install Python 3.12 or newer from https://www.python.org/downloads/.")
    node = shutil.which("node")
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if not node or not npm:
        raise RuntimeError("Install Node.js 22.12 or newer from https://nodejs.org, then reopen this launcher.")
    version = subprocess.check_output([node, "--version"], text=True).strip()
    if tuple(int(part) for part in version.lstrip("v").split(".")[:2]) < (22, 12):
        raise RuntimeError("Node.js 22.12 or newer is required. Update it at https://nodejs.org.")
    try:
        state = json.loads(STATE.read_text(encoding="utf-8"))
        if not isinstance(state, dict):
            state = {}
    except (OSError, ValueError):
        state = {}
    created = not PYTHON.is_file()
    if created:
        print("Creating the project's Python environment...", flush=True)
        run([sys.executable, "-m", "venv", ROOT / ".venv"])

    requirements = fingerprint([ROOT / "requirements.txt"])
    if created or state.get("requirements") != requirements:
        print("Installing Python dependencies (first launch or updated requirements)...", flush=True)
        run([PYTHON, "-m", "pip", "install", "-r", ROOT / "requirements.txt"])
        state["requirements"] = requirements
        save_state(state)

    packages = fingerprint([ROOT / "frontend" / name for name in ("package.json", "package-lock.json")])
    if not (ROOT / "frontend/node_modules/.package-lock.json").is_file() or state.get("packages") != packages:
        print("Installing website dependencies...", flush=True)
        run([npm, "ci"], ROOT / "frontend")
        state["packages"] = packages
        save_state(state)

    from scripts.manage import check_data
    missing = check_data()
    if any("Kernels" in path.parts for path in missing):
        raise RuntimeError("Bundled SPICE kernels are missing. Download the complete project from GitHub again.")
    if missing:
        print("Preparing NASA map data. The first download can take several minutes; keep this window open.", flush=True)
        run([PYTHON, ROOT / "scripts/manage.py", "prepare-data"])
        if check_data():
            raise RuntimeError("Map preparation is incomplete. Run this launcher again to retry.")

    sources = frontend_fingerprint()
    if not (ROOT / "frontend/dist/index.html").is_file() or state.get("build") != sources:
        print("Building the website...", flush=True)
        run([npm, "run", "build"], ROOT / "frontend")
        state["build"] = sources
        save_state(state)


def available_port(preferred):
    for port in range(preferred, min(preferred + 20, 65536)):
        with socket.socket() as listener:
            try:
                listener.bind(("127.0.0.1", port))
                return port
            except OSError:
                pass
    raise RuntimeError("No free local port found. Close an older STAMINA window or use --port NUMBER.")


def wait_until_ready(child, url, timeout=120):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if child.poll() is not None:
            raise RuntimeError("The STAMINA server stopped during startup. See the error above.")
        try:
            with urlopen(url + "api/health", timeout=1) as response:
                if json.load(response).get("application") == "STAMINA":
                    return
        except (OSError, URLError, ValueError):
            pass
        time.sleep(0.25)
    raise RuntimeError("The server did not become ready within two minutes. See the output above.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-browser", action="store_true", help="Print the address without opening a browser")
    parser.add_argument("--setup-only", action="store_true", help="Prepare everything without starting a server")
    parser.add_argument("--port", type=int, default=8080, help="Preferred local port; uses a nearby free port if busy")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    print("STAMINA | Preparing your lunar explorer", flush=True)
    setup()
    if args.setup_only:
        print("Setup complete. Run this launcher again to open STAMINA.", flush=True)
        return 0
    port = available_port(args.port)
    url = f"http://127.0.0.1:{port}/"
    child = subprocess.Popen([str(PYTHON), "-m", "uvicorn", "backend.web:app",
                              "--host", "127.0.0.1", "--port", str(port)], cwd=ROOT)
    try:
        wait_until_ready(child, url)
        print(f"\nSTAMINA is ready: {url}\nKeep this window open. Press Ctrl+C to stop.\n", flush=True)
        if not args.no_browser:
            webbrowser.open(url)
        return child.wait()
    except KeyboardInterrupt:
        return 0
    finally:
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(0)
    except (RuntimeError, OSError, subprocess.CalledProcessError) as error:
        print(f"\nSTAMINA could not start: {error}\nFix the issue above and run the launcher again.", file=sys.stderr)
        sys.exit(1)
