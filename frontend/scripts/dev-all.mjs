// `npm run dev`: starts the scientific API (port 8000) and the Vite dev server together.
//
// - Reuses an API that is already answering on port 8000.
// - Runs the API with `uv` when available (it installs requirements.txt itself),
//   otherwise with `py` (Windows) or `python3`, which need `pip install -r requirements.txt`.
// - If the API can't start, the site still runs; the timeline then explains how to start it.
// - Ctrl+C stops both.
import { spawn, spawnSync } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const frontend = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const root = resolve(frontend, "..");
const API_PORT = 8000;
const API_PROBE = `http://127.0.0.1:${API_PORT}/api/positions?date=2032-11-01`;
const windows = process.platform === "win32";

const children = [];
let stopping = false;

function log(message) {
  console.log(`\x1b[36m[dev]\x1b[0m ${message}`);
}

function has(command) {
  return spawnSync(command, ["--version"], { stdio: "ignore", shell: windows }).status === 0;
}

// "running": our API answers; "taken": something else holds the port; "free": nothing answers.
async function apiStatus() {
  try {
    const response = await fetch(API_PROBE, { signal: AbortSignal.timeout(1500) });
    return response.ok ? "running" : "taken";
  } catch {
    return "free";
  }
}

function start(name, command, args, cwd) {
  const child = spawn(command, args, { cwd, stdio: "inherit", shell: windows });
  child.on("exit", (code) => {
    if (stopping) return;
    if (name === "web") {
      log(`site stopped (code ${code}); stopping the API too`);
      shutdown(code ?? 0);
    } else {
      log(`API stopped (code ${code}). The site keeps running; the timeline will say how to start the API.`);
    }
  });
  children.push(child);
  return child;
}

function shutdown(code = 0) {
  stopping = true;
  for (const child of children) {
    if (child.exitCode === null) child.kill("SIGTERM");
  }
  process.exit(code);
}

process.on("SIGINT", () => shutdown(0));
process.on("SIGTERM", () => shutdown(0));

const uvicorn = ["-m", "uvicorn", "backend.api:app", "--host", "127.0.0.1", "--port", String(API_PORT)];
const status = await apiStatus();

if (status === "running") {
  log(`API already running on port ${API_PORT}; reusing it`);
} else if (status === "taken") {
  log(`port ${API_PORT} is used by another program (not the STAMINA API); stop it to get the timeline`);
} else if (has("uv")) {
  log(`starting the API with uv on port ${API_PORT}`);
  start("api", "uv", ["run", "--with-requirements", "requirements.txt", "python", ...uvicorn], root);
} else {
  const python = windows ? "py" : "python3";
  log(`uv not found; starting the API with ${python} (needs: pip install -r requirements.txt)`);
  start("api", python, uvicorn, root);
}

start("web", windows ? "npx.cmd" : "npx", ["vite", ...process.argv.slice(2)], frontend);
