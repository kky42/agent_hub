import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { buildAgentRunArgs, eventAction } from "./agents/index.mjs";
import {
  appendText,
  fail,
  parseJsonLine,
  print,
  requireCommand,
  SCRIPT_PATH,
  shellQuote,
  WORKER_PROMPT_TEMPLATE,
  writeJsonAtomic,
  now,
} from "./common.mjs";

export async function runStructuredWorker({ agent, sandbox, cwd, prompt, model, reasoning, liveLog, rawLog }) {
  requireCommand(agent);
  if (!prompt) {
    fail("--prompt or --prompt-file is required for worker-run");
  }
  const workerName = process.env.KANBAN_WORKER_NAME || null;
  const systemPrompt = fs.readFileSync(WORKER_PROMPT_TEMPLATE, "utf8").trim();
  const args = buildAgentRunArgs({ agent, sandbox, cwd, prompt, model, reasoning, systemPrompt });
  const startedAt = now();
  let updatedAt = startedAt;
  const child = spawn(agent, args, {
    cwd,
    env: workerEnv(cwd),
    stdio: ["ignore", "pipe", "pipe"],
  });

  let buffer = "";
  let session = null;
  let finalText = "";
  let done = false;
  const errors = [];
  const stderr = [];
  const stderrTail = [];
  const eventTypes = [];
  let rawLineCount = 0;
  let exit = null;

  const buildOutput = () => ({
    name: workerName,
    agent,
    sandbox,
    cwd,
    model: model ?? null,
    reasoning: reasoning ?? null,
    sessionId: session ?? null,
    pid: child.pid ?? null,
    startedAt,
    updatedAt,
    running: exit === null,
    exitCode: exit?.code ?? null,
    signal: exit?.signal ?? null,
    done,
    ok: exit === null ? null : errors.length === 0 && (done || exit.code === 0),
    errors,
    stderr,
    stderrTail,
    finalText,
    rawLineCount,
    lastEventType: eventTypes.length ? eventTypes[eventTypes.length - 1] : null,
    eventTypes,
  });

  const writeLive = () => {
    updatedAt = now();
    writeJsonAtomic(liveLog, buildOutput());
  };

  writeLive();
  child.stdout.setEncoding("utf8");
  child.stderr.setEncoding("utf8");
  child.stdout.on("data", (chunk) => {
    buffer += chunk;
    const lines = buffer.split(/\r?\n/);
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      appendText(rawLog, `${line}\n`);
      rawLineCount += 1;
      const event = parseJsonLine(line);
      if (!event) continue;
      eventTypes.push(event.type);
      const action = eventAction(agent, event);
      applyAction(action);
    }
    writeLive();
  });
  child.stderr.on("data", (chunk) => {
    const text = String(chunk).trim();
    if (text) {
      stderr.push(text);
      stderrTail.push(text);
      while (stderrTail.length > 20) stderrTail.shift();
      writeLive();
    }
  });

  const applyAction = (action) => {
    if (!action) return;
    if (action.kind === "session") {
      session = action.sessionId;
    } else if (action.kind === "message") {
      finalText = action.text;
    } else if (action.kind === "done") {
      done = true;
      if (agent === "codex" && !child.killed) child.kill("SIGTERM");
    } else if (action.kind === "error") {
      errors.push(action.text);
      if (action.messageText) finalText = action.messageText;
    }
  };

  exit = await new Promise((resolve) => {
    child.on("close", (code, signal) => resolve({ code, signal }));
  });

  if (buffer.trim()) {
    appendText(rawLog, `${buffer.trim()}\n`);
    rawLineCount += 1;
    const event = parseJsonLine(buffer);
    if (event?.type) eventTypes.push(event.type);
    applyAction(eventAction(agent, event));
  }

  const output = buildOutput();
  writeJsonAtomic(liveLog, output);
  print(output);
  process.exit(output.ok ? 0 : 1);
}

function workerEnv(cwd) {
  const cacheRoot = path.join(cwd, ".kanban", "cache");
  const tmpRoot = path.join(cwd, ".kanban", "tmp");
  fs.mkdirSync(cacheRoot, { recursive: true });
  fs.mkdirSync(tmpRoot, { recursive: true });
  return {
    ...process.env,
    UV_CACHE_DIR: process.env.UV_CACHE_DIR ?? path.join(cacheRoot, "uv"),
    XDG_CACHE_HOME: process.env.XDG_CACHE_HOME ?? path.join(cacheRoot, "xdg"),
    TMPDIR: process.env.TMPDIR ?? tmpRoot,
    TMP: process.env.TMP ?? tmpRoot,
    TEMP: process.env.TEMP ?? tmpRoot,
  };
}

export function workerRunArgs({ agent, sandbox, cwd, model, reasoning, promptPath, liveLog, rawLog }) {
  const args = [
    SCRIPT_PATH,
    "worker-run",
    "--agent",
    agent,
    "--sandbox",
    sandbox,
    "--cwd",
    cwd,
    "--prompt-file",
    promptPath,
    "--live-log",
    liveLog,
    "--raw-log",
    rawLog,
  ];
  if (model) args.push("--model", model);
  if (reasoning) args.push("--reasoning", reasoning);
  return args;
}

export function buildWorkerCommand({ name, cwd, agent, sandbox, model, reasoning, promptPath, liveLog, rawLog, runnerLog }) {
  const args = workerRunArgs({ agent, sandbox, cwd, model, reasoning, promptPath, liveLog, rawLog });
  return `KANBAN_WORKER_NAME=${shellQuote(name)} ${[process.execPath, ...args].map(shellQuote).join(" ")} > ${shellQuote(runnerLog)} 2>&1`;
}

export function initialLiveLog({ name, agent, sandbox, cwd, model, reasoning }) {
  return {
    name,
    agent,
    sandbox,
    cwd,
    model: model ?? null,
    reasoning: reasoning ?? null,
    sessionId: null,
    startedAt: now(),
    updatedAt: now(),
    running: true,
    launching: true,
    exitCode: null,
    signal: null,
    done: false,
    ok: null,
    errors: [],
    stderr: [],
    stderrTail: [],
    finalText: "",
    rawLineCount: 0,
    lastEventType: null,
    eventTypes: [],
  };
}
