#!/usr/bin/env node
import { spawn } from "node:child_process";
import { mkdirSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const packageRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const launcher = join(packageRoot, "run-doc-reader");
const cacheRoot =
  process.env.DOC_READER_CACHE_DIR ||
  process.env.XDG_CACHE_HOME ||
  (process.platform === "darwin"
    ? join(homedir(), "Library", "Caches")
    : join(homedir(), ".cache"));
const venvDir = process.env.DOC_READER_VENV_DIR || join(cacheRoot, "doc-reader", "npm-venv");

mkdirSync(dirname(venvDir), { recursive: true });

const env = {
  ...process.env,
  DOC_READER_VENV_DIR: venvDir,
  PYTHONPATH: packageRoot + (process.env.PYTHONPATH ? `:${process.env.PYTHONPATH}` : ""),
};

function run(command, args) {
  return new Promise((resolveExitCode) => {
    const child = spawn(command, args, {
      env,
      stdio: "inherit",
    });

    child.on("error", (error) => {
      console.error(`[doc-reader] Failed to start ${command}: ${error.message}`);
      resolveExitCode(1);
    });

    child.on("exit", (code, signal) => {
      if (signal) {
        process.kill(process.pid, signal);
        return;
      }
      resolveExitCode(code ?? 0);
    });
  });
}

const args = process.argv.slice(2);
const wantsTray = args.length === 0 || args[0] === "--tray";
const forwardedArgs = args[0] === "--tray" ? args.slice(1) : args;

if (wantsTray) {
  process.exitCode = await run(launcher, forwardedArgs);
} else {
  const prepareExitCode = await run(launcher, ["--prepare-only"]);
  if (prepareExitCode !== 0) {
    process.exitCode = prepareExitCode;
  } else {
    const python = process.platform === "win32"
      ? join(venvDir, "Scripts", "python.exe")
      : join(venvDir, "bin", "python");
    process.exitCode = await run(python, ["-m", "doc_reader", ...forwardedArgs]);
  }
}
