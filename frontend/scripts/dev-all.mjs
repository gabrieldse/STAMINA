// Optional npm shortcut for the canonical Python launcher; API defaults to 8001.
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const windows = process.platform === "win32";
const localPython = resolve(root, ".venv", windows ? "Scripts/python.exe" : "bin/python");
const python = existsSync(localPython) ? localPython : windows ? "py" : "python3";
const child = spawn(python, ["scripts/manage.py", "dev", ...process.argv.slice(2)], {
  cwd: root,
  stdio: "inherit",
});
child.on("error", (error) => {
  console.error(`Cannot start STAMINA: ${error.message}. Follow the root README to install Python dependencies.`);
  process.exitCode = 1;
});
child.on("exit", (code) => { process.exitCode = code ?? 1; });
process.on("SIGINT", () => { child.kill("SIGINT"); });
process.on("SIGTERM", () => { child.kill("SIGTERM"); });
