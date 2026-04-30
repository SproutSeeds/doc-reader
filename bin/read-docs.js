#!/usr/bin/env node
import { spawn, spawnSync } from "node:child_process";
import { existsSync, mkdirSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const packageRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const launcher = join(packageRoot, "run-doc-reader");
const managedRoot = join(homedir(), ".doc-reader-managed");
const nativeApp = join(managedRoot, "Doc Reader.app");
const nativeExecutable = join(nativeApp, "Contents", "MacOS", "DocReader");
const launchAgentLabel = "com.docreader.tray";
const launchAgentPlist = join(homedir(), "Library", "LaunchAgents", `${launchAgentLabel}.plist`);
const servicesItem = join(homedir(), "Library", "Services", "Read with Doc Reader.workflow");
const stdoutLog = join(homedir(), "Library", "Logs", "doc-reader-tray.log");
const stderrLog = join(homedir(), "Library", "Logs", "doc-reader-tray.err.log");
const cacheRoot =
  process.env.DOC_READER_CACHE_DIR ||
  process.env.XDG_CACHE_HOME ||
  (process.platform === "darwin"
    ? join(homedir(), "Library", "Caches")
    : join(homedir(), ".cache"));
const venvDir = process.env.DOC_READER_VENV_DIR || join(cacheRoot, "doc-reader", "npm-venv");

const cliEnv = {
  ...process.env,
  DOC_READER_VENV_DIR: venvDir,
  PYTHONPATH: packageRoot + (process.env.PYTHONPATH ? `:${process.env.PYTHONPATH}` : ""),
};
const scriptEnv = { ...process.env };

function usage() {
  console.log(`read-docs

macOS app bootstrapper:
  read-docs install          Install/update the managed app agent and Services item
  read-docs start            Start the installed menu-bar agent
  read-docs restart          Refresh the managed copy and restart the agent
  read-docs stop             Stop the running agent without uninstalling it
  read-docs status           Show managed app, LaunchAgent, and Services status
  read-docs uninstall        Remove LaunchAgent and Services integration

Document CLI:
  read-docs <file> [options] Stream a document through the local reader engine
  read-docs cli <file> [...] Same as above, explicit CLI form

The polished app integration is macOS-first. On other platforms, use the document CLI.`);
}

function run(command, args, options = {}) {
  return new Promise((resolveExitCode) => {
    const child = spawn(command, args, {
      env: options.env || process.env,
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

function macOnly(commandName) {
  if (process.platform === "darwin") {
    return true;
  }
  console.error(`[doc-reader] '${commandName}' is only supported by the macOS app bootstrapper.`);
  console.error("[doc-reader] Use 'read-docs <file>' for the cross-platform document CLI.");
  return false;
}

function uid() {
  return typeof process.getuid === "function" ? process.getuid() : process.env.UID;
}

function launchAgentTarget() {
  return `gui/${uid()}/${launchAgentLabel}`;
}

function launchAgentDomain() {
  return `gui/${uid()}`;
}

function isLaunchAgentLoaded() {
  const result = spawnSync("launchctl", ["print", launchAgentTarget()], {
    stdio: ["ignore", "ignore", "ignore"],
  });
  return result.status === 0;
}

async function runScript(name, args = []) {
  return run(join(packageRoot, name), args, { env: scriptEnv });
}

async function installApp() {
  if (!macOnly("install")) {
    return 1;
  }
  const appExitCode = await runScript("enable-startup");
  if (appExitCode !== 0) {
    return appExitCode;
  }
  return runScript("install-context-menu-service");
}

async function startAgent() {
  if (!macOnly("start")) {
    return 1;
  }
  if (!existsSync(launchAgentPlist)) {
    console.error("[doc-reader] App agent is not installed yet.");
    console.error("[doc-reader] Run 'read-docs install' first.");
    return 1;
  }
  if (!isLaunchAgentLoaded()) {
    const bootstrapExitCode = await run("launchctl", [
      "bootstrap",
      launchAgentDomain(),
      launchAgentPlist,
    ]);
    if (bootstrapExitCode !== 0 && !isLaunchAgentLoaded()) {
      return bootstrapExitCode;
    }
  }
  spawnSync("launchctl", ["enable", launchAgentTarget()], {
    stdio: ["ignore", "ignore", "ignore"],
  });
  return run("launchctl", ["kickstart", "-k", launchAgentTarget()]);
}

async function stopAgent() {
  if (!macOnly("stop")) {
    return 1;
  }
  if (!isLaunchAgentLoaded()) {
    console.log("[doc-reader] App agent is not running.");
    return 0;
  }
  return run("launchctl", ["bootout", launchAgentTarget()]);
}

function status() {
  const lines = [
    "Doc Reader app status",
    `Platform: ${process.platform === "darwin" ? "macOS" : process.platform}`,
    `Managed app: ${existsSync(managedRoot) ? "installed" : "missing"} (${managedRoot})`,
    `Native shell: ${existsSync(nativeExecutable) ? "installed" : "missing"} (${nativeApp})`,
    `LaunchAgent: ${existsSync(launchAgentPlist) ? "installed" : "missing"} (${launchAgentPlist})`,
    `Agent state: ${process.platform === "darwin" && isLaunchAgentLoaded() ? "running" : "not running"}`,
    `Services item: ${existsSync(servicesItem) ? "installed" : "missing"} (${servicesItem})`,
    `Logs: ${stdoutLog}`,
    `Errors: ${stderrLog}`,
  ];
  console.log(lines.join("\n"));
  return 0;
}

async function uninstallApp() {
  if (!macOnly("uninstall")) {
    return 1;
  }
  const serviceExitCode = await runScript("uninstall-context-menu-service");
  const agentExitCode = await runScript("disable-startup");
  return serviceExitCode || agentExitCode;
}

async function runCli(args) {
  mkdirSync(dirname(venvDir), { recursive: true });
  const prepareExitCode = await run(launcher, ["--prepare-only"], { env: cliEnv });
  if (prepareExitCode !== 0) {
    return prepareExitCode;
  }
  const python = process.platform === "win32"
    ? join(venvDir, "Scripts", "python.exe")
    : join(venvDir, "bin", "python");
  return run(python, ["-m", "doc_reader", ...args], { env: cliEnv });
}

const args = process.argv.slice(2);
const command = args[0];

if (!command || command === "--help" || command === "-h" || command === "help") {
  usage();
  process.exitCode = 0;
} else if (command === "install") {
  process.exitCode = await installApp();
} else if (command === "start" || command === "app" || command === "--tray") {
  process.exitCode = await startAgent();
} else if (command === "restart") {
  process.exitCode = await (macOnly("restart") ? runScript("enable-startup") : Promise.resolve(1));
} else if (command === "stop") {
  process.exitCode = await stopAgent();
} else if (command === "status") {
  process.exitCode = status();
} else if (command === "uninstall" || command === "remove") {
  process.exitCode = await uninstallApp();
} else if (command === "disable-startup") {
  process.exitCode = await (macOnly("disable-startup") ? runScript("disable-startup") : Promise.resolve(1));
} else if (command === "install-service") {
  process.exitCode = await (macOnly("install-service") ? runScript("install-context-menu-service") : Promise.resolve(1));
} else if (command === "uninstall-service") {
  process.exitCode = await (macOnly("uninstall-service") ? runScript("uninstall-context-menu-service") : Promise.resolve(1));
} else if (command === "cli") {
  process.exitCode = await runCli(args.slice(1));
} else {
  process.exitCode = await runCli(args);
}
