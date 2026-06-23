const { spawn } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const workspaceRoot = path.resolve(__dirname, "..");
const frontendDistIndex = path.join(workspaceRoot, "frontend", "dist", "index.html");
const isWindows = process.platform === "win32";
const host = process.env.DASHBOARD_HOST ?? "127.0.0.1";
const port = process.env.DASHBOARD_PORT ?? "8095";
const showHelp = process.argv.includes("--help") || process.argv.includes("-h");
const dryRun = process.argv.includes("--dry-run");

let shuttingDown = false;
let backendStarted = false;
let frontendWatcher = null;
let backendServer = null;

function printHelp() {
  console.log("Usage: npm run dashboard:watch [-- --dry-run]");
  console.log("");
  console.log("Builds the frontend bundle in watch mode, waits for the first bundle,");
  console.log("then starts the FastAPI backend with reload enabled on the merged /app surface.");
  console.log("");
  console.log("Environment overrides:");
  console.log("  DASHBOARD_HOST   Backend host (default: 127.0.0.1)");
  console.log("  DASHBOARD_PORT   Backend port (default: 8095)");
}

function resolvePythonCommand() {
  const candidates = [
    path.join(workspaceRoot, ".venv", "Scripts", "python.exe"),
    path.join(workspaceRoot, ".venv-py313", "Scripts", "python.exe"),
  ];

  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }

  return "python";
}

function prefixStream(stream, prefix, onLine) {
  let buffer = "";
  stream.setEncoding("utf8");
  stream.on("data", (chunk) => {
    buffer += chunk;
    const lines = buffer.split(/\r?\n/);
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (!line) {
        continue;
      }

      console.log(`${prefix} ${line}`);
      if (onLine) {
        onLine(line);
      }
    }
  });
  stream.on("end", () => {
    if (!buffer) {
      return;
    }

    console.log(`${prefix} ${buffer}`);
    if (onLine) {
      onLine(buffer);
    }
  });
}

function killProcessTree(childProcess) {
  if (!childProcess || childProcess.exitCode !== null || childProcess.killed) {
    return;
  }

  if (isWindows) {
    const killer = spawn("taskkill", ["/pid", String(childProcess.pid), "/t", "/f"], {
      stdio: "ignore",
      windowsHide: true,
    });
    killer.on("error", () => {
      childProcess.kill("SIGTERM");
    });
    return;
  }

  childProcess.kill("SIGTERM");
}

function spawnNpm(args, options) {
  if (isWindows) {
    return spawn(process.env.ComSpec ?? "cmd.exe", ["/d", "/s", "/c", "npm", ...args], options);
  }

  return spawn("npm", args, options);
}

function shutdown(exitCode) {
  if (shuttingDown) {
    return;
  }

  shuttingDown = true;
  killProcessTree(backendServer);
  killProcessTree(frontendWatcher);

  setTimeout(() => {
    process.exit(exitCode);
  }, 50);
}

function maybeStartBackend(line) {
  if (backendStarted || !fs.existsSync(frontendDistIndex)) {
    return;
  }

  if (!/built in/i.test(line)) {
    return;
  }

  backendStarted = true;
  const pythonCommand = resolvePythonCommand();
  const backendArgs = [
    "-m",
    "uvicorn",
    "app.main:app",
    "--host",
    host,
    "--port",
    port,
    "--reload",
  ];

  console.log(`[dashboard] Frontend bundle ready at /app. Starting backend on http://${host}:${port}/app`);

  if (dryRun) {
    console.log(`[dashboard] Dry run backend command: ${pythonCommand} ${backendArgs.join(" ")}`);
    shutdown(0);
    return;
  }

  backendServer = spawn(pythonCommand, backendArgs, {
    cwd: workspaceRoot,
    env: process.env,
    stdio: ["inherit", "pipe", "pipe"],
    windowsHide: false,
  });

  prefixStream(backendServer.stdout, "[backend]");
  prefixStream(backendServer.stderr, "[backend]");

  backendServer.on("error", (error) => {
    console.error(`[dashboard] Failed to start backend: ${error.message}`);
    shutdown(1);
  });

  backendServer.on("exit", (code, signal) => {
    if (shuttingDown) {
      return;
    }

    const detail = signal ? `signal ${signal}` : `exit code ${code ?? 0}`;
    console.error(`[dashboard] Backend stopped with ${detail}`);
    shutdown(code ?? 0);
  });
}

function start() {
  if (showHelp) {
    printHelp();
    return;
  }

  console.log(`[dashboard] Watching frontend bundle and serving merged app from http://${host}:${port}/app`);
  if (dryRun) {
    console.log("[dashboard] Dry run mode enabled.");
  }

  frontendWatcher = spawnNpm(["--prefix", "frontend", "run", "build:watch"], {
    cwd: workspaceRoot,
    env: process.env,
    stdio: ["inherit", "pipe", "pipe"],
    windowsHide: false,
  });

  prefixStream(frontendWatcher.stdout, "[frontend]", maybeStartBackend);
  prefixStream(frontendWatcher.stderr, "[frontend]", maybeStartBackend);

  frontendWatcher.on("error", (error) => {
    console.error(`[dashboard] Failed to start frontend watcher: ${error.message}`);
    shutdown(1);
  });

  frontendWatcher.on("exit", (code, signal) => {
    if (shuttingDown) {
      return;
    }

    const detail = signal ? `signal ${signal}` : `exit code ${code ?? 0}`;
    console.error(`[dashboard] Frontend watcher stopped with ${detail}`);
    shutdown(code ?? 0);
  });
}

process.on("SIGINT", () => shutdown(0));
process.on("SIGTERM", () => shutdown(0));

start();