---
name: agent-prompt-engineering
description: Guide feature prompt design and development using Claude Code-inspired prompt architecture, style, and evaluation taste. Use when designing or changing system prompts, tool descriptions, agent/subagent prompts, prompt guidelines, slash-command prompts, or agent behavior instructions.
---

# Agent Prompt Engineering

Use this skill when a product feature depends on model behavior shaped by prompts, tool metadata, agent role prompts, examples, or runtime reminders.

## Source Taste

Claude Code-style prompt design is layered, terse, operational, and testable:

- **Tool descriptions** state the tool contract, when to use it, what result comes back, and key caveats.
- **System guidance** gives general behavioral policy, not a pile of exact task routes.
- **Role prompts** define strengths, boundaries, allowed tools, forbidden actions, and expected output.
- **Examples** teach patterns and edge cases without turning them into hardcoded rules.
- **Runtime reminders** are small, situational, and used only when the risk is current.

Prefer prompts that a maintainer can inspect, diff, and evaluate from traces.

## Design Workflow

1. Identify the behavior surface: system prompt, tool description, prompt guideline, role prompt, example, reminder, or generated user prompt.
2. State the job in one sentence: what behavior must change, for whom, and under what trigger.
3. Pick the narrowest prompt layer that owns the behavior. Do not put everything in the global system prompt.
4. Write generic heuristics first. Add examples only when heuristics are too abstract for real models.
5. Use native prompt surfaces when available, such as tool snippets, tool guidelines, schema descriptions, agent metadata, role prompts, and coordinator prompts. Avoid appending one large manual block when the runtime has clearer layers.
6. Keep capability boundaries explicit when the model can act on them: freshness of context, result visibility, tool availability, write permissions, and unsupported modes. Put enforcement details, exact limits, and rejection wording in code or tool results.
7. Run an evaluation that checks behavior, not just text presence. Inspect traces for tool choice, tool arguments, ordering, duplicate work, skipped verification, and final reporting.
8. If a prompt fails, tune toward the underlying decision rule. Avoid patching one fixture with exact task names unless that exact task is the product surface.

## Prompt Layer Rules

- **Tool snippet**: one compact sentence for the available-tools list. It should answer "why would I reach for this tool?"
- **Tool guidelines**: concise heuristics, result handling, fresh-context warnings, parallel-use rules, and "do not use when" boundaries.
- **Tool schema descriptions**: parameter semantics only. Keep UI/routing metadata separate from the full task prompt.
- **Role prompt**: task identity, strengths, prohibited actions, available-tool strategy, and final-report contract.
- **Agent roster**: generate from metadata as `agent-name: description`. This scales to custom agents and avoids hardcoded prose drifting from tool behavior.
- **Coordinator prompt**: global contract, available agents, and a small number of durable examples. Keep exact limits and enforcement details in code/tool results when possible.
- **Examples**: use for patterns such as survey questions, second opinions, parallel fan-out, or mid-wait behavior. Do not rely on examples as the only rule.
- **Runtime reminder**: only for live, local risk. Remove it when the risk is no longer current.

## Style

- Use short imperative bullets. Name the behavior, condition, and expected action.
- Prefer "Use X when..." over "Always use X for task A/B/C."
- Prefer "For a single-fact lookup where you already know the file, search directly" over a long blacklist.
- Say what returns and who sees it. Example: "The agent result is returned to you; relay what matters."
- Say what not to duplicate. If work is delegated, wait for that result instead of repeating the same search.
- Brief fresh agents like capable colleagues: goal, why it matters, known context, constraints, output shape.
- Avoid motivational language, vague virtues, and over-specific fixture phrases.
- Avoid overfitting prompts to passing e2e traces. Passing one trace is evidence, not the design.

## Claude-Like Patterns Worth Reusing

- Use specialized agents when the task matches their description.
- Use subagents for independent parallel work or to protect the main context from large search/read output.
- Do not use subagents excessively; direct lookup is better when the target is known.
- Do not duplicate research already delegated to a subagent.
- Fresh subagents start with no conversation context; prompts must be self-contained.
- Tell agents whether work is read-only research or code-changing work.
- Trust but verify: an agent summary describes what it intended to do, not necessarily what changed.
- Read-only roles must explicitly forbid edits, file creation, shell redirects, installs, and state-changing commands.
- Long-running/background concepts need clear result, resume, polling, and user-visibility semantics. Omit unsupported modes.

## Subagent Prompt Lessons

- Prefer a compact tool description plus richer `promptSnippet` and `promptGuidelines` over a long monolithic tool description.
- Keep model-facing capability text behaviorally meaningful. Avoid saying "not enforced" or "not implemented" unless the model has a useful action to take from that fact.
- For built-in and custom agents, present the same shape: `name`, short routing `description`, and role `prompt`.
- If a specific user phrase is a real product surface, a small example can be appropriate. For example, repo exploration is a common survey request, so an example that routes it to an explorer-style agent is defensible.
- Do not turn every successful eval into a rule. If a broad heuristic fails but the reference agent also handles that case directly, remove the heuristic instead of making it more directive.
- If the model is missing a decision rule, move that rule to the narrowest reliable layer first. Escalate to coordinator prompt only when tool metadata is too weak in real traces.
- Keep direct-search escape hatches prominent. Some codebase audits are faster and more Claude-like as direct grep/read work than as subagent delegation.

## Evaluation Checklist

- Does the model choose the intended tool or prompt path for the right reason?
- Does it avoid the path for a simple lookup or known target?
- Does it preserve user context instead of dumping raw files into the main thread?
- Does it handle parallel independent work in one response when supported?
- Does it keep fresh-agent prompts self-contained?
- Does the final answer faithfully relay tool/agent results and mention skipped or failed checks?
- Are failures explained by a missing general rule rather than by absence of a fixture-specific phrase?
- Does behavior match the reference agent case by case, rather than assuming all broad tasks should delegate?
- Did the evaluation inspect the actual trace, including tool names, arguments, and counts?
- Are interface differences accounted for, such as interactive TUI behavior versus non-interactive CLI behavior?

## Red Flags

- Global prompt carries task examples that belong in tool guidelines or examples.
- Prompt mentions exact test fixtures, repo names, or benchmark labels.
- Prompt says "always" where the right behavior depends on context.
- Prompt hides enforcement details that should live in code or tool errors.
- Prompt asks models to report success without requiring verification.
- Prompt replaces a clear tool contract with broad personality text.
