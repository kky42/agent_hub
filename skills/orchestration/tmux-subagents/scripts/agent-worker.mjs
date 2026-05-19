#!/usr/bin/env node
import { spawn, spawnSync } from "node:child_process";
import os from "node:os";
import path from "node:path";

const VALID_AGENTS = new Set(["codex", "claude", "pi"]);
const VALID_SANDBOXES = new Set(["read-only", "workspace-write", "danger-full-access"]);

const CLAUDE_PERMISSION_MODES = {
  "read-only": "plan",
  "workspace-write": "acceptEdits",
  "danger-full-access": "bypassPermissions"
};

function usage() {
  console.log(`Usage:
  agent-worker.mjs run --agent <codex|claude|pi> --sandbox <read-only|workspace-write|danger-full-access> [--cwd DIR] [--session-id ID] [--model MODEL] [--reasoning LEVEL] --prompt TEXT
  agent-worker.mjs launch --agent <codex|claude|pi> --sandbox <read-only|workspace-write|danger-full-access> --name NAME [--cwd DIR] [--session-id ID] [--model MODEL] [--reasoning LEVEL]
  agent-worker.mjs send --name NAME --prompt TEXT
  agent-worker.mjs capture --name NAME [--lines N]
  agent-worker.mjs session --agent <codex|claude|pi> --name NAME
  agent-worker.mjs status [--name NAME]
  agent-worker.mjs close --name NAME

Sandbox modes:
  read-only           inspect only
  workspace-write     allow scoped edits in the working directory
  danger-full-access  no filesystem sandbox / bypass permissions; use only in isolation

Claude does not expose the same filesystem sandbox as Codex/Pi. This helper maps
the three sandbox modes to Claude permission modes: plan, acceptEdits, and
bypassPermissions.
Default cwd: current directory
`);
}

function fail(message, code = 1) {
  console.error(`agent-worker: ${message}`);
  process.exit(code);
}

function parseArgs(argv) {
  if (argv[2] === "--help" || argv[2] === "-h") {
    return { command: "help", opts: { help: true } };
  }
  const command = argv[2];
  const opts = { _: [] };
  for (let i = 3; i < argv.length; i += 1) {
    const arg = argv[i];
    if (!arg.startsWith("--")) {
      opts._.push(arg);
      continue;
    }
    const key = arg.slice(2);
    if (key === "help") {
      opts.help = true;
      continue;
    }
    const value = argv[i + 1];
    if (value === undefined || value.startsWith("--")) {
      opts[key] = true;
      continue;
    }
    opts[key] = value;
    i += 1;
  }
  return { command, opts };
}

function requireCommand(command) {
  const result = spawnSync("command", ["-v", command], {
    shell: true,
    encoding: "utf8"
  });
  if (result.status !== 0) {
    fail(`${command} not found on PATH`);
  }
}

function normalizeAgent(agent) {
  if (!VALID_AGENTS.has(agent)) {
    fail(`--agent must be one of: ${Array.from(VALID_AGENTS).join(", ")}`);
  }
  return agent;
}

function normalizeSandbox(sandbox) {
  if (!sandbox) {
    fail(`--sandbox is required for run and launch`);
  }
  if (!VALID_SANDBOXES.has(sandbox)) {
    fail(`--sandbox must be one of: ${Array.from(VALID_SANDBOXES).join(", ")}`);
  }
  return sandbox;
}

function shellQuote(value) {
  return `'${String(value).replaceAll("'", "'\\''")}'`;
}

function spawnCapture(command, args, options = {}) {
  return spawnSync(command, args, {
    encoding: "utf8",
    ...options
  });
}

function supportsPiSandbox(cwd) {
  const result = spawnCapture("pi", ["-h"], { cwd });
  return result.status === 0 && /--sandbox\b/.test(`${result.stdout}\n${result.stderr}`);
}

function addModelAndReasoning(args, agent, { model, reasoning }) {
  if (model) {
    args.push(agent === "codex" ? "--model" : "--model", model);
  }
  if (!reasoning) {
    return;
  }
  if (agent === "codex") {
    args.push("-c", `model_reasoning_effort=${JSON.stringify(reasoning)}`);
  } else if (agent === "claude") {
    args.push("--effort", reasoning);
  } else {
    args.push("--thinking", reasoning);
  }
}

function codexArgs({ sandbox, mode, sessionId, prompt, model, reasoning }) {
  const args = [];
  if (mode === "run") {
    args.push("exec", "--json");
  } else if (sessionId) {
    args.push("resume");
  } else {
    args.push("--no-alt-screen");
  }

  args.push("--sandbox", sandbox);
  if (mode !== "run") {
    args.push("--ask-for-approval", "on-request");
  }
  addModelAndReasoning(args, "codex", { model, reasoning });

  if (mode === "launch" && sessionId) {
    args.push("--no-alt-screen", sessionId);
  }
  if (mode === "run" && sessionId) {
    args.push("resume", sessionId);
  }
  if (prompt) {
    args.push(prompt);
  }
  return args;
}

function claudeArgs({ sandbox, mode, sessionId, prompt, model, reasoning }) {
  const args = [];
  if (mode === "run") {
    args.push("-p", "--output-format", "stream-json");
  }

  args.push("--permission-mode", CLAUDE_PERMISSION_MODES[sandbox]);
  addModelAndReasoning(args, "claude", { model, reasoning });

  if (sessionId) {
    args.push("--resume", sessionId);
  }
  if (prompt) {
    args.push(prompt);
  }
  return args;
}

function piArgs({ sandbox, mode, sessionId, prompt, cwd, model, reasoning }) {
  const args = [];
  if (mode === "run") {
    args.push("-p", "--mode", "json");
  }

  if (supportsPiSandbox(cwd)) {
    args.push("--sandbox", sandbox);
  } else if (sandbox === "read-only") {
    args.push("--tools", "read,grep,find,ls");
  } else {
    fail("pi --sandbox is not available in this environment, so workspace-write/danger-full-access cannot be enforced");
  }
  addModelAndReasoning(args, "pi", { model, reasoning });

  if (sessionId) {
    args.push("--session", sessionId);
  }
  if (prompt) {
    args.push(prompt);
  }
  return args;
}

function buildAgentArgs({ agent, sandbox, mode, sessionId, prompt, cwd, model, reasoning }) {
  if (agent === "codex") {
    return codexArgs({ sandbox, mode, sessionId, prompt, model, reasoning });
  }
  if (agent === "claude") {
    return claudeArgs({ sandbox, mode, sessionId, prompt, model, reasoning });
  }
  return piArgs({ sandbox, mode, sessionId, prompt, cwd, model, reasoning });
}

function parseJsonLine(line) {
  const trimmed = line.trim();
  if (!trimmed) {
    return null;
  }
  try {
    return JSON.parse(trimmed);
  } catch {
    return null;
  }
}

function textBlocks(content) {
  if (typeof content === "string") {
    return content;
  }
  if (!Array.isArray(content)) {
    return "";
  }
  return content
    .filter((block) => block && block.type === "text" && typeof block.text === "string")
    .map((block) => block.text)
    .join("");
}

function eventAction(agent, event) {
  if (!event || typeof event !== "object") {
    return null;
  }
  if (agent === "codex") {
    if (event.type === "thread.started") {
      return { kind: "session", sessionId: event.thread_id ?? null };
    }
    if (event.type === "item.completed" && event.item?.type === "agent_message") {
      return { kind: "message", text: event.item.text ?? "" };
    }
    if (event.type === "turn.completed") {
      return { kind: "done" };
    }
    if (event.type === "turn.failed" || event.type === "error") {
      return { kind: "error", text: event.error?.message ?? event.message ?? "Codex failed" };
    }
  }
  if (agent === "claude") {
    if (event.type === "system" && event.subtype === "init") {
      return { kind: "session", sessionId: event.session_id ?? null };
    }
    if (event.type === "assistant") {
      const text = textBlocks(event.message?.content);
      return text ? { kind: "message", text } : null;
    }
    if (event.type === "result") {
      return event.is_error
        ? { kind: "error", text: event.errors?.[0] ?? event.subtype ?? "Claude failed" }
        : { kind: "done" };
    }
    if (event.type === "error") {
      return { kind: "error", text: event.message ?? "Claude failed" };
    }
  }
  if (agent === "pi") {
    if (event.type === "session") {
      return { kind: "session", sessionId: event.id ?? null };
    }
    if (event.type === "message_end" && event.message?.role === "assistant") {
      if (event.message.stopReason === "error") {
        return { kind: "error", text: event.message.errorMessage ?? "Pi failed" };
      }
      const text = textBlocks(event.message.content);
      return text ? { kind: "message", text } : null;
    }
    if (event.type === "turn_end" || event.type === "agent_end") {
      return { kind: "done" };
    }
    if (event.type === "compaction_end" && event.errorMessage) {
      return { kind: "error", text: `Pi compaction failed: ${event.errorMessage}` };
    }
    if (event.type === "auto_retry_end" && !event.success && event.finalError) {
      return { kind: "error", text: `Pi retry failed: ${event.finalError}` };
    }
  }
  return null;
}

async function runStructured({ agent, sandbox, cwd, sessionId, prompt, model, reasoning }) {
  requireCommand(agent);
  if (!prompt) {
    fail("--prompt is required for run");
  }
  const args = buildAgentArgs({ agent, sandbox, mode: "run", sessionId, prompt, cwd, model, reasoning });
  const child = spawn(agent, args, {
    cwd,
    env: process.env,
    stdio: ["ignore", "pipe", "pipe"]
  });

  let buffer = "";
  let session = null;
  let finalText = "";
  let done = false;
  const errors = [];
  const stderr = [];
  const rawEvents = [];

  child.stdout.setEncoding("utf8");
  child.stderr.setEncoding("utf8");
  child.stdout.on("data", (chunk) => {
    buffer += chunk;
    const lines = buffer.split(/\r?\n/);
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      const event = parseJsonLine(line);
      if (!event) {
        continue;
      }
      rawEvents.push(event.type);
      const action = eventAction(agent, event);
      if (!action) {
        continue;
      }
      if (action.kind === "session") {
        session = action.sessionId;
      } else if (action.kind === "message") {
        finalText = action.text;
      } else if (action.kind === "done") {
        done = true;
      } else if (action.kind === "error") {
        errors.push(action.text);
      }
    }
  });
  child.stderr.on("data", (chunk) => {
    const text = String(chunk).trim();
    if (text) {
      stderr.push(text);
    }
  });

  const exit = await new Promise((resolve) => {
    child.on("close", (code, signal) => resolve({ code, signal }));
  });

  if (buffer.trim()) {
    const event = parseJsonLine(buffer);
    const action = eventAction(agent, event);
    if (action?.kind === "message") {
      finalText = action.text;
    }
  }

  const output = {
    agent,
    sandbox,
    cwd,
    model: model ?? null,
    reasoning: reasoning ?? null,
    sessionId: session ?? sessionId ?? null,
    exitCode: exit.code,
    signal: exit.signal,
    done,
    ok: exit.code === 0 && errors.length === 0,
    errors,
    stderr,
    finalText,
    eventTypes: rawEvents
  };
  console.log(JSON.stringify(output, null, 2));
  process.exit(output.ok ? 0 : 1);
}

function tmux(args, options = {}) {
  return spawnCapture("tmux", args, { encoding: "utf8", ...options });
}

function launchInteractive({ agent, sandbox, cwd, sessionId, name, model, reasoning }) {
  requireCommand("tmux");
  requireCommand(agent);
  if (!name) {
    fail("--name is required for launch");
  }
  const args = buildAgentArgs({ agent, sandbox, mode: "launch", sessionId, cwd, model, reasoning });
  const command = [agent, ...args].map(shellQuote).join(" ");
  const result = tmux(["new-session", "-d", "-s", name, "-c", cwd, command]);
  if (result.status !== 0) {
    fail(result.stderr.trim() || result.stdout.trim() || `failed to launch ${name}`);
  }
  console.log(JSON.stringify({ name, agent, sandbox, cwd, model: model ?? null, reasoning: reasoning ?? null, command }, null, 2));
}

function capture({ name, lines = "200" }) {
  requireCommand("tmux");
  if (!name) {
    fail("--name is required");
  }
  const n = Number.parseInt(String(lines), 10);
  const start = Number.isFinite(n) && n > 0 ? `-${n}` : "-200";
  const result = tmux(["capture-pane", "-pt", name, "-S", start]);
  if (result.status !== 0) {
    fail(result.stderr.trim() || `failed to capture ${name}`);
  }
  process.stdout.write(result.stdout);
}

function send({ name, prompt }) {
  requireCommand("tmux");
  if (!name || !prompt) {
    fail("--name and --prompt are required");
  }
  const result = tmux(["send-keys", "-t", name, "C-u", prompt, "Enter"]);
  if (result.status !== 0) {
    fail(result.stderr.trim() || `failed to send to ${name}`);
  }
}

function close({ name }) {
  requireCommand("tmux");
  if (!name) {
    fail("--name is required");
  }
  const result = tmux(["kill-session", "-t", name]);
  if (result.status !== 0) {
    fail(result.stderr.trim() || `failed to close ${name}`);
  }
}

function status({ name }) {
  requireCommand("tmux");
  const args = name ? ["list-panes", "-t", name, "-F", "#{session_name}\t#{pane_current_command}\t#{pane_dead}\t#{pane_title}"] : ["list-sessions"];
  const result = tmux(args);
  if (result.status !== 0) {
    if (!name && /no server running/.test(result.stderr)) {
      console.log("[]");
      return;
    }
    fail(result.stderr.trim() || "tmux status failed");
  }
  process.stdout.write(result.stdout);
}

function sessionCommand({ agent, name }) {
  requireCommand("tmux");
  normalizeAgent(agent);
  if (!name) {
    fail("--name is required");
  }
  const command = agent === "pi" ? "/session" : agent === "codex" ? "/status" : "/status";
  const result = tmux(["send-keys", "-t", name, "C-u", command, "Enter"]);
  if (result.status !== 0) {
    fail(result.stderr.trim() || `failed to request session info from ${name}`);
  }
  console.log(JSON.stringify({ name, agent, command }, null, 2));
}

async function main() {
  const { command, opts } = parseArgs(process.argv);
  if (!command || opts.help) {
    usage();
    process.exit(command ? 0 : 1);
  }

  const cwd = path.resolve(opts.cwd ? String(opts.cwd).replace(/^~(?=$|\/)/, os.homedir()) : process.cwd());
  const agent = opts.agent ? normalizeAgent(String(opts.agent)) : null;
  const sandbox = opts.sandbox ? normalizeSandbox(String(opts.sandbox)) : null;
  const prompt = opts.prompt ? String(opts.prompt) : "";
  const sessionId = opts["session-id"] ? String(opts["session-id"]) : null;
  const model = opts.model ? String(opts.model) : null;
  const reasoning = opts.reasoning ? String(opts.reasoning) : null;

  if (command === "run") {
    await runStructured({ agent: normalizeAgent(agent), sandbox: normalizeSandbox(sandbox), cwd, sessionId, prompt, model, reasoning });
  } else if (command === "launch") {
    launchInteractive({ agent: normalizeAgent(agent), sandbox: normalizeSandbox(sandbox), cwd, sessionId, name: opts.name, model, reasoning });
  } else if (command === "send") {
    send({ name: opts.name, prompt });
  } else if (command === "capture") {
    capture({ name: opts.name, lines: opts.lines });
  } else if (command === "session") {
    sessionCommand({ agent: normalizeAgent(agent), name: opts.name });
  } else if (command === "status") {
    status({ name: opts.name });
  } else if (command === "close") {
    close({ name: opts.name });
  } else {
    fail(`unknown command: ${command}`);
  }
}

main().catch((error) => fail(error?.message ?? String(error)));
