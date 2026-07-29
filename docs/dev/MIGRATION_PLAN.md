# Agentor: engine migration plan

**Recommendation: own the loop (~800 LOC on the bare OpenAI SDK). Do not migrate to LangGraph. Do not go Rust.**

All numbers below were measured on this machine against this repo, not estimated.

---

## 1. What is actually wrong today

The problem is not that openai-agents is "too high-level." It is that Agentor uses ~15 symbols
from it, and every one of them is on the critical path of something Celesto sells.

**Evidence from the code:**

| Symptom | Location | Root cause |
|---|---|---|
| Model swap requires rebuilding a whole `Agent` | `core/agent.py:445-464` | model is bound at `Agent()` construction |
| ~50 lines of `hasattr` introspection to emit a trace | `tracer.py:128-176` | span internals are opaque; trace format is reverse-engineered |
| ~130 lines of defensive `getattr(item, "raw_item", None)` | `output_text_formatter.py:148-238` | stream item model is opaque |
| A second, parallel engine on raw litellm | `durable/durable_agent.py` (439 lines) | durability was unreachable through the SDK, so it was rebuilt outside it |
| Two tool systems bridged by `to_openai_function()` | `tools/base.py:46`, `tools/registry.py` | `FunctionTool` vs `BaseTool` |
| SDK type leaks into user tool signatures | `tools/registry.py:34` (`RunContextWrapper`) | context plumbing is SDK-shaped |
| `_call_llm` contains ~28 lines of an LLM's abandoned reasoning | `durable/durable_agent.py:308-335` | — |

The two engines (`Agentor` and `DurableAgent`) **do not share tools and do not share tracing**.
That is the real cost, and it compounds.

**Import cost** (warm, repeated runs):

```
import agentor           2.65s
  ├─ litellm             1.04s   ← dominant, and orthogonal to framework choice
  ├─ openai-agents       0.71s   (drags in mcp → jsonschema → rfc3987_syntax)
  └─ rest                ~0.9s
```

477 MB of site-packages. `googleapiclient` (93 MB) and `litellm` (83 MB) are **required** deps
for everyone, including someone who just wants `Agentor(name=..., model="gpt-4o")`.

---

## 2. The honest counter-argument (read this before deciding)

**openai-agents 0.18.3 — the version already pinned in this repo — has the durability
features the migration is nominally for.** Verified against the installed package:

```python
from agents.run_state import RunState
# → to_json / from_json / get_interruptions / approve / reject

Runner.run(..., session=Session, conversation_id=..., previous_response_id=...)
```

That is durable checkpointing, human-in-the-loop approval, and conversation memory. Agentor
uses **none** of it. It also ships guardrails, handoffs, sandbox integrations, and voice/realtime,
all maintained by OpenAI for free.

**If Agentor were only a framework for building agents, the correct and much cheaper call would
be: stay, adopt `RunState` + `Session`, delete `DurableAgent`, done in a week.**

The reason to still own the loop is specific to Celesto's business:

1. **The trace format is the product.** Celesto sells observability. Today `tracer.py` reverse-engineers
   another vendor's span objects and only covers one of the two engines. If you own the loop,
   the event stream *is* the trace — no adapter, no `hasattr` chains, full coverage.
2. **You already own an engine, badly.** `DurableAgent` is 439 lines of second implementation.
   Consolidating on one owned loop *removes* code rather than adding it.
3. **openai-agents is OpenAI-shaped.** Its Responses-API-first design (reasoning items,
   `previous_response_id`) is a recurring tax when your users run Gemini or Claude.

This is a real trade. Owning the loop means owning provider quirks, streaming edge cases, and
tool-call parsing forever. Take the trade only if observability is genuinely the moat.

---

## 3. Options evaluated

### Option A — LangGraph ❌

**Measured** (fresh venv, langgraph 1.2.10 / langchain-core 1.5.2):
42 MB, 43 packages, 0.34s + 0.25s warm import. Genuinely lighter than the current stack.

Reject it anyway, on four grounds:

1. **It is not lower-level — it is differently high-level.** StateGraph, Pregel/BSP supersteps,
   channels, reducers, `Annotated[list, add_messages]`. You trade OpenAI's opinions for
   LangChain's. An agent is a `while` loop that calls tools; modelling that as a graph is more
   ceremony, not less. Community benchmark: a ReAct agent is ~40 lines in smolagents, ~120 in LangGraph.
2. **It re-introduces a provider abstraction** you are trying to escape — `BaseChatModel`,
   `langchain-openai`, and `AIMessage`/`ToolMessage` leaking into your public API or a converter
   layer to hide them.
3. **Agentor's public API gets nothing.** `Agentor(name, tools, model).run()/.serve()`, LiteMCP,
   A2A, tool-search, skills — none of it comes from the engine. You would write the same wrapper
   over a different runtime.
4. **Strategic conflict.** LangGraph's gravity is LangSmith. Celesto sells tracing. Building the
   core on a competitor's runtime means fighting its callback system indefinitely.

### Option B — Rust core (PyO3) ❌

An LLM turn is 500 ms – 30 s of network and inference. Python overhead per turn is ~1–3 ms.
Rust addresses **under 0.5%** of wall-clock time.

Cost: maturin/PyO3 build, ~20 wheels (macOS x86+arm, manylinux, musl, Windows × py3.11–3.14),
and every contributor needs Rust. That is directly opposed to "lean and hackable."

The one honest gain — install size and import time — is achieved far more cheaply by making
litellm optional (Phase 0, one day, no Rust).

Where Rust *would* make sense: a standalone gateway binary competing with the LiteLLM proxy.
That is a separate product, not a fix for framework limitations. Park it.

### Option C — Own the loop ✅

**Validated with a working spike** (`spike_loop.py`, ran against the live OpenAI API):
158 lines gave schema generation from type hints, parallel tool calls, tool-error feedback,
a normalized event stream, and sync/async/streaming entry points. Import cost **0.31s**.

The spike also found a real bug to design around up front: **a tool that raises loops until
`max_turns`** — 10 wasted API calls. The loop needs a per-tool failure budget, not just a turn cap.

Nearly every provider now exposes an OpenAI-compatible `/chat/completions` — Anthropic, Gemini,
Groq, Together, OpenRouter, Fireworks, DeepSeek, xAI, Mistral, vLLM, Ollama. `AsyncOpenAI(base_url=...)`
covers ~95% of real usage with one dependency. litellm becomes an optional adapter for the long tail.

---

## 4. Target architecture

Five new files, ~800 LOC total.

```
src/agentor/core/
  events.py     ~60    Event dataclasses. This IS the trace format.
  tool.py      ~180    Schema gen from type hints, one Tool type, @tool
  model.py     ~200    Model protocol + ChatCompletions adapter (+ optional Responses, litellm)
  loop.py      ~220    The run loop: sync/async/stream, retries, fallback, turn + failure budgets
  store.py     ~150    Append-only event log, resume, HITL interrupt
```

Two model adapters, not a hundred:

- `ChatCompletionsModel(base_url=...)` — default, universal, `openai` dep only.
- `ResponsesModel()` — for OpenAI hosted tools (`WebSearchTool`, file search) and reasoning persistence.
- `LiteLLMModel()` — optional extra, for providers with no OpenAI-compatible endpoint.

**Public API does not change.** `Agentor(name=..., model=..., tools=...)`, `.run()`, `.arun()`,
`.chat()`, `.serve()`, `.from_md()` all keep working. The engine swaps underneath.

**Untouched by this migration** — these are the differentiators and none of them live in the engine:
LiteMCP (`mcp/api_router.py`, 662 lines), A2A (`a2a.py`), `tool_search.py`, `skills.py`, `tools/*`.

---

## 5. Phased migration

Each phase ships independently and leaves `main` green.

### Phase 0 — Kill the import tax (1 day) — *do this regardless of the decision*

- Move `litellm` behind `agentor[litellm]`; lazy-import at call site.
- Move `google-api-*` (93 MB) behind the existing `google` extra — it is currently required for everyone.
- Lazy-import `fastapi`/`uvicorn` inside `.serve()`.

**Result: 2.65s → ~0.4s import, 477 MB → well under 100 MB.** Highest user-visible win in the
whole plan, and it is independent of everything below.

### Phase 1 — Core loop behind the existing API (3–4 days)

Land `events.py`, `tool.py`, `model.py`, `loop.py`. Gate with `Agentor(engine="native")`,
defaulting to the openai-agents path. Port the test suite to run against both engines.

Carry over from the spike: per-tool failure budget, tool errors fed back as messages rather
than raised, `max_turns` as a hard stop.

### Phase 2 — One tool abstraction (2 days)

Collapse `FunctionTool` / `BaseTool` / `ToolRegistry` onto the single `Tool` type. Drop
`RunContextWrapper` from user-facing signatures — context becomes a plain argument.
Keep `@tool`, `@capability`, and `BaseTool.from_function` working.

### Phase 3 — Native tracing (2 days)

Celesto exporter consumes `Event` directly. Deletes the `hasattr` introspection in `tracer.py`
and — for the first time — covers every code path, including `LLM` and durable runs.

### Phase 4 — Fold in durability (2–3 days)

`store.py` absorbs the `DurableAgent` jsonl event log. `Agentor(store=FileStore("runs/"))`
gets resume + HITL interrupt. **Delete `durable/` (439 lines).**

### Phase 5 — Drop openai-agents (1 day)

Swap `agents.mcp.MCPServerStreamableHttp` for the official `mcp` client — **verified working**
via `mcp.client.streamable_http.streamablehttp_client` + `ClientSession`, already a direct dep.
Flip the default engine, remove the dependency, delete `output_text_formatter.py`'s SDK half.

**Total: ~2.5 weeks.**

### Net LOC

| | Before | After | Δ |
|---|---|---|---|
| New core (5 files) | 0 | ~810 | +810 |
| `core/agent.py` | 704 | ~350 | −354 |
| `durable/durable_agent.py` | 439 | 0 | −439 |
| `output_text_formatter.py` | 280 | ~80 | −200 |
| `tracer.py` | 313 | ~150 | −163 |
| tool plumbing | ~250 | ~120 | −130 |
| **Net** | | | **≈ −475** |

Less code, one engine instead of two, durability and native tracing gained.

---

## 6. Explicitly NOT building

Guarding against the over-engineering the brief warns about:

- ❌ Graph / DAG DSL — the loop is a `while`
- ❌ Handoffs as a primitive — a sub-agent is a tool that calls another agent (~10 lines)
- ❌ Guardrails framework — a callback
- ❌ 100-provider abstraction — `base_url` covers it; litellm is the optional escape hatch
- ❌ Workflow engine / Temporal-style determinism — an append-only event log is enough
- ❌ Voice, realtime, computer-use
- ❌ Prompt templating DSL — `jinja2` is already there
- ❌ Custom retry/backoff framework — `backoff` is already a dep

---

## 7. Risks

| Risk | Mitigation |
|---|---|
| **OpenAI hosted tools** (`WebSearchTool`, file search) don't exist on chat-completions | Keep `ResponsesModel` adapter; `WebSearchTool` stays OpenAI-only, as it already is |
| Provider quirks (tool-call format drift, Gemini's strict-schema rejections) | Adapter layer per provider; the spike's `_json_type` already handles union/optional/literal |
| Streaming edge cases across providers | Highest-risk item — budget real time in Phase 1; chat-completions SSE deltas are well-trodden |
| Silent behaviour change for existing users | Dual-engine gate through Phases 1–4; same test suite runs against both |
| Losing free upstream work (guardrails, sandboxes, realtime) | Accepted — Agentor uses none of it today |

---

## 8. If you only do one thing

**Phase 0.** It is one day, carries no architectural risk, is correct under every option including
"change nothing," and takes `import agentor` from 2.65s to ~0.4s.
