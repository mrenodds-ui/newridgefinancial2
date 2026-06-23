const { spawn } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const workspaceRoot = path.resolve(__dirname, "..");
const host = process.env.DASHBOARD_HOST ?? "127.0.0.1";
const port = process.env.DASHBOARD_PORT ?? "8095";
const reload = process.argv.includes("--reload");

function resolvePythonCommand() {
  const candidates = [
    path.join(workspaceRoot, ".venv", "Scripts", "python.exe"),
    path.join(workspaceRoot, ".venv-py313", "Scripts", "python.exe"),
    path.join(workspaceRoot, ".venv", "bin", "python"),
    path.join(workspaceRoot, ".venv-py313", "bin", "python"),
  ];

  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }

  return "python";
}

const pythonCommand = resolvePythonCommand();
const args = ["-m", "uvicorn", "app.main:app", "--host", host, "--port", port];

if (reload) {
  args.push("--reload");
}

const child = spawn(pythonCommand, args, {
  cwd: workspaceRoot,
  env: process.env,
  stdio: "inherit",
  windowsHide: false,
});

child.on("error", (error) => {
  console.error(`[backend] Failed to start backend host: ${error.message}`);
  process.exit(1);
});

child.on("exit", (code, signal) => {
  if (signal) {
    console.error(`[backend] Backend host stopped with signal ${signal}`);
    process.exit(1);
  }
  process.exit(code ?? 0);
});