"""Local STAMINA commands. Run with the project's virtual-environment Python."""
import argparse
import importlib.util
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
MAP_DATA = FRONTEND / "public" / "lunar-map" / "data"


def npm():
    executable = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if not executable:
        raise SystemExit("Node.js/npm is missing. Install Node.js 22.12 or newer.")
    return executable


def run(command, cwd=ROOT):
    subprocess.run(command, cwd=cwd, check=True)


def check_data():
    required = [MAP_DATA / "meta.json", MAP_DATA / "lola_hillshade.bin",
                MAP_DATA / "lola_elevation.bin", ROOT / "lola_2d/data/ldem_75s_240m_dem.tif"]
    required += [MAP_DATA / f"{season}_{stat}.bin" for season in ("summer", "winter")
                 for stat in ("avg", "min", "max", "amplitude")]
    required += [ROOT / "SMEData/Kernels" / name for name in ("naif0012.tls", "de440s.bsp", "pck00011.tpc")]
    missing = [path for path in required if not path.is_file() or path.stat().st_size == 0]
    return missing


def require_data():
    missing = check_data()
    if missing:
        names = "\n".join(f"  {path.relative_to(ROOT)}" for path in missing)
        raise SystemExit(f"Required scientific data is missing:\n{names}\nRun: python scripts/manage.py prepare-data\nSPICE kernels should come from your Git checkout.")


def doctor():
    missing_modules = [name for name in ("fastapi", "uvicorn", "numpy", "rasterio", "spiceypy", "matplotlib", "PIL",
                                        "numba", "rioxarray", "scipy", "solshade", "pyproj", "xarray")
                       if importlib.util.find_spec(name) is None]
    print(f"Python: {sys.version.split()[0]} ({sys.executable})")
    print(f"Node.js: {shutil.which('node') or 'MISSING'}")
    print(f"npm: {shutil.which('npm') or shutil.which('npm.cmd') or 'MISSING'}")
    print(f"Python dependencies: {', '.join(missing_modules) if missing_modules else 'OK'}")
    print(f"Numba acceleration: {'available' if importlib.util.find_spec('numba') else 'not installed (slower fallback)'}")
    print(f"Frontend dependencies: {'OK' if (FRONTEND / 'node_modules').is_dir() else 'run npm ci in frontend/'}")
    missing_data = check_data()
    print(f"Scientific data: {'OK' if not missing_data else 'MISSING; run prepare-data'}")
    print(f"Compiled website: {'available' if (FRONTEND / 'dist/index.html').is_file() else 'run build'}")
    return bool(missing_modules or missing_data or not shutil.which('node') or not (FRONTEND / 'node_modules').is_dir())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="Check dependencies and scientific data; no downloads")
    prepare = commands.add_parser("prepare-data", help="Download NASA data and generate the polar map")
    prepare.add_argument("--size", type=int, choices=(1024, 2048), default=2048)
    prepare.add_argument("--terrain", action="store_true", help="Also build optional detailed contour/terrain tiles")
    api = commands.add_parser("api", help="Run the scientific API")
    api.add_argument("--port", type=int, default=8001)
    api.add_argument("--reload", action="store_true")
    dev = commands.add_parser("dev", help="Run API and Vite together; Ctrl+C stops both")
    dev.add_argument("--api-port", type=int, default=8001)
    dev.add_argument("--web-port", type=int, default=5173)
    commands.add_parser("build", help="Build the frontend for production")
    serve = commands.add_parser("serve", help="Serve the compiled frontend and API together")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()

    if args.command == "doctor":
        return int(doctor())
    if args.command == "prepare-data":
        run([sys.executable, str(ROOT / "lola_2d/diviner_web.py"), "--size", str(args.size), "--no-serve"])
        if args.terrain:
            run([sys.executable, str(ROOT / "lola_2d/build_terrain_tiles.py")])
    elif args.command == "build":
        require_data()
        run([npm(), "run", "build"], FRONTEND)
    elif args.command == "api":
        require_data()
        run([sys.executable, "-m", "uvicorn", "backend.api:app", "--host", "127.0.0.1", "--port", str(args.port)]
            + (["--reload", "--reload-dir", "backend"] if args.reload else []))
    elif args.command == "serve":
        require_data()
        run([sys.executable, "-m", "uvicorn", "backend.web:app", "--host", args.host, "--port", str(args.port)])
    elif args.command == "dev":
        require_data()
        node = npm()
        children = []
        process_group = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
        environment = {**os.environ, "STAMINA_API_TARGET": f"http://127.0.0.1:{args.api_port}"}
        api_command = [
            sys.executable, "-m", "uvicorn", "backend.api:app",
            "--host", "127.0.0.1", "--port", str(args.api_port),
            "--reload", "--reload-dir", "backend",
        ]
        frontend_command = [
            node, "run", "dev", "--", "--host", "127.0.0.1",
            "--port", str(args.web_port), "--strictPort",
        ]
        try:
            children.append(subprocess.Popen(api_command, cwd=ROOT, **process_group))
            children.append(subprocess.Popen(frontend_command, cwd=FRONTEND, env=environment, **process_group))
            print(f"STAMINA: http://localhost:{args.web_port} | API: http://localhost:{args.api_port}/docs", flush=True)
            while all(child.poll() is None for child in children):
                try:
                    children[0].wait(timeout=1)
                except subprocess.TimeoutExpired:
                    pass
            return 1
        finally:
            for child in children:
                if child.poll() is None:
                    try:
                        if os.name == "nt":
                            child.send_signal(signal.CTRL_BREAK_EVENT)
                        else:
                            os.killpg(child.pid, signal.SIGTERM)
                    except OSError:
                        child.terminate()
            for child in children:
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(0)
    except subprocess.CalledProcessError as exc:
        sys.exit(exc.returncode)
