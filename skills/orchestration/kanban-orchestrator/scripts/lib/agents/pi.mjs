import { fail, spawnCapture, textBlocks } from "../common.mjs";

export const name = "pi";
export const defaults = { model: "deepseek/deepseek-v4-flash", reasoning: "low" };

export function supportsSandbox(cwd) {
  const result = spawnCapture("pi", ["-h"], { cwd });
  return result.status === 0 && /--sandbox\b/.test(`${result.stdout}\n${result.stderr}`);
}

export function buildArgs({ sandbox, cwd, prompt, model, reasoning, systemPrompt }) {
  const args = ["-p", "--mode", "json"];
  if (systemPrompt) args.push("--append-system-prompt", systemPrompt);
  if (supportsSandbox(cwd)) {
    args.push("--sandbox", sandbox);
  } else if (sandbox === "read-only") {
    args.push("--tools", "read,grep,find,ls,bash");
  } else {
    fail("pi --sandbox is not available in this environment, so workspace-write/danger-full-access cannot be enforced");
  }
  if (model) args.push("--model", model);
  if (reasoning) args.push("--thinking", reasoning);
  args.push(prompt);
  return args;
}

export function eventAction(event) {
  if (!event || typeof event !== "object") return null;
  if (event.type === "session") {
    return { kind: "session", sessionId: event.id ?? null };
  }
  if (event.type === "message_end" && event.message?.role === "assistant") {
    const text = textBlocks(event.message.content);
    if (event.message.stopReason === "error") {
      return { kind: "error", text: event.message.errorMessage ?? "Pi failed", messageText: text || null };
    }
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
  return null;
}
