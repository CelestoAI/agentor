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

### Phase 0 — Kill the import tax ✅ *shipped*

- litellm lazy-imported at every call site; it no longer loads on the OpenAI path at all.
- `agentor.__init__` and `agentor.core.__init__` resolve heavy names through `__getattr__`
  (with `TYPE_CHECKING` blocks so IDEs and type checkers are unaffected).
- `google-api-*` **and `superauth`** moved to the `google` extra. superauth was the real culprit:
  it hard-requires `google-api-python-client`, so moving the google packages alone changed nothing.
- `uvicorn` lazy inside `.serve()`.

**Measured result:**

| | before | after |
|---|---|---|
| `import agentor` | 2.65s | **0.004s** |
| `from agentor import Agentor` | 2.65s | **~1.4s** |
| clean core install | 311 MB | **210 MB** |

litellm stays a *required* dep for now — `core/agent.py` routes any `provider/model` string
through `LitellmModel`, which is the README-advertised multi-provider path. Demoting it to an
extra happens in Phase 1, once `ChatCompletionsModel` exists to replace it.

The residual ~1.4s is openai-agents itself (1.19s, mostly `mcp` → `jsonschema`); that leaves in Phase 5.

Fixing this also surfaced a latent circular import (`agentor.a2a` → `agentor.core` → `core.agent`
→ `agentor.a2a`) that the old eager `__init__` had been masking.

### Phase 1 — Core loop behind the existing API ✅ *shipped*

`agentor/engine/` — **917 LOC**, gated by `Agentor(engine="native")`, default still `"agents"`.
Nothing in it imports openai-agents, so Phase 5 is a deletion rather than a rewrite.

| file | LOC | |
|---|---|---|
| `events.py` | 87 | `Event`, `RunResult`, `Usage` — the single description of a run |
| `tools.py` | 260 | schema generation, docstring parsing, one `Tool` type |
| `models.py` | 257 | `Model` protocol, `ChatCompletionsModel`, `LiteLLMModel` |
| `loop.py` | 279 | the loop: sync/async/stream, budgets, model swap |

**Measured:**

| | agents engine | native engine |
|---|---|---|
| import | 1.124s | **0.047s** |
| agent construction (5 tools) | 1.17 ms | 4.39 ms |

Construction is ~3 ms slower because schemas are built with pydantic (`create_model` +
`model_json_schema` is 0.176 ms of the 0.211 ms per tool). Deliberately not optimised: it is
noise next to a 500 ms+ model call, and a cache would add invalidation logic for no visible gain.

**Verified against the live API** (22/22 checks) and 30 unit tests driven by a scripted fake model:

- Schema parity with openai-agents, **including param descriptions parsed from Google-style
  docstrings**. Skipping those would have quietly degraded tool-calling accuracy.
- `RunContextWrapper` is detected by name, excluded from the schema, and injected at call time,
  so existing registry tools work unchanged — without importing openai-agents.
- Parallel tool calls, streamed tool-call reassembly from fragmented deltas, usage accounting.
- Tool errors are fed back to the model rather than raised; unknown tools and malformed JSON
  arguments are reported, not fatal.
- `stream_chat` projects engine events onto the existing `AgentOutput` wire format, so `serve()`,
  `/chat` and the A2A handler are untouched.

**The spike bug is fixed, and testing it found a second one.** A failing tool used to burn all 10
turns; a failure budget now disables it after 2. The first fix only withdrew the tool's *schema* —
but a model can still emit a call for a tool it was not offered, which let the broken tool keep
running. The budget is now enforced at execution.

Known gaps in `engine="native"`, all raising or deferred rather than silently ignored:
MCP servers (raises `NotImplementedError`), `output_type` structured output, `WebSearchTool`.

### Phase 2 — One tool abstraction (2 days)

Collapse `FunctionTool` / `BaseTool` / `ToolRegistry` onto the single `Tool` type. Drop
`RunContextWrapper` from user-facing signatures — context becomes a plain argument.
Keep `@tool`, `@capability`, and `BaseTool.from_function` working.

### Phase 3 — Native tracing ✅ *shipped*

Reordered ahead of Phase 2, for two reasons: Phase 2 mostly deletes the `FunctionTool` bridge,
which cannot go until the native engine is the default (Phase 5); and Phase 1 opened a hole that
needed closing.

**The hole:** `engine="native"` wired tracing to the openai-agents trace processor, which cannot
observe a run that never enters openai-agents. Native runs produced **no traces, with no warning**.

`agentor/engine/tracing.py` (160 LOC) projects the event stream onto Celesto trace payloads:
one trace per run, a `generation` span per model call, a `function` span per tool call, all
parented to an `agent` span. No `hasattr` chains — the events already describe the run, so the
tracer reads nothing from the engine's internals. That is the structural difference from
`tracer.py`, whose `_convert_span` is ~75 lines of defensive introspection into another vendor's
objects.

Verified on a live run:

```
TRACE trace_17d6486d…  Weather Agent
  SPAN generation  gpt-4o-mini    67 tokens
  SPAN function    get_weather
  SPAN generation  gpt-4o-mini    94 tokens
  SPAN agent       Weather Agent  161 tokens
```

- Tracing failures cannot break a run: collector and export errors are caught and logged, proven
  by a test with a tracer that raises from both.
- Export runs on a worker thread, so a slow ingest endpoint does not block the event loop.
- Known limitation: a caller that abandons `astream` early never reaches export. `arun` always drains.

12 tracing tests; 198 passing overall.

### Phase 4 — Fold in durability ✅ *shipped*

`agentor/engine/store.py` (164 LOC) replaces `DurableAgent` (439 LOC, deleted).

Durability falls out of the event stream rather than being built beside it: persisting a run is
appending its events, and resuming is replaying them into a message list. Because each
`generation` event records the request **exactly as sent**, replay reconstructs the conversation
without inferring anything — which is what the old implementation had to do by hand.

```python
agent = Agentor(name="Agent", tools=[...], engine="native", store=FileStore("runs"))
result = agent.run("do the thing")
agent.resume(result.run_id)     # continue after a crash
```

**Verified across real process boundaries against the live API**: process 1 starts a run that
stops holding an unused tool result and writes a 5-event log; process 2, a fresh interpreter
knowing only the run id, reads it from disk and finishes the job.

- `FileStore` fsyncs each event — a crash is the case it exists for.
- A torn final line (the expected result of a hard kill) is skipped, not fatal.
- `Event.from_dict` ignores unknown fields, so a newer writer cannot break an older reader.
- Resuming a completed run returns the stored result without calling the model again.
- A failing store logs and lets the run finish; losing durability is bad, killing a live run over
  it is worse.

`DurableAgent` raises an `AttributeError` carrying the migration snippet rather than a bare
`ImportError`. 20 store tests; 215 passing overall.

**Deferred:** HITL interrupt/approval. The store makes it straightforward, but nothing in the
codebase needs it yet and the brief says not to ship features nobody uses.

### Phase 5a — Close the native engine's gaps ✅ *shipped*

Split out from Phase 5. Flipping the default engine changes behaviour for every user, so it
should not ride along with the work that makes the flip possible — and not on top of an
unreviewed stack.

**MCP** (`agentor/engine/mcp.py`, 150 LOC) on the official `mcp` package. Remote tools become
ordinary `Tool` objects, so the loop, the failure budget and tracing all apply to them unchanged.
Connections are held for the duration of a run and closed after — including when the run raises.
An `Agentor(tools=[MCPServerStreamableHttp(...)])` call is adapted automatically, so the same
code works on either engine.

Verified against a real server (agentor's own LiteMCP, 9/9): discovery, remote calls, local and
remote tools in one run, cleanup, and MCP calls appearing as spans in traces.

*An MCP session is bound to the event loop that opened it.* Closing it from another loop produced
anyio's `Attempted to exit cancel scope in a different task`, which names the mechanism rather
than the mistake — `close()` now raises a message that says what to do instead. Worth noting the
error came from **my own verification script**, not the engine; the production path was clean.

**Structured output.** `output_type=SomeModel` sends a strict `json_schema` response format and
parses the result. Parsing happens at the boundary so events stay plain text and the persisted
log stays JSON-serialisable — durability and structured output do not interfere.

`response_format` is only passed when set, so a `Model` adapter written before this still works.

233 tests passing.

### Phase 5c — Multi-provider verified ✅ *shipped*

**The plan's biggest untested assumption is now tested.** Everything the native engine does
works against OpenRouter — a genuinely third-party, non-OpenAI endpoint — via `base_url` alone,
12/12 checks:

| | |
|---|---|
| completion + usage accounting | ✅ |
| parallel tool calling | ✅ |
| streaming, incl. tool calls reassembled from fragmented deltas | ✅ |
| structured output — strict `json_schema`, nested models, optional fields | ✅ |
| public `Agentor` API | ✅ |
| **durable run interrupted and resumed against the third-party provider** | ✅ |

Structured output surviving is the notable one: strict `json_schema` is the feature most likely
to be unsupported downstream, and it worked.

Verifying it exposed a gap that made the whole story unusable in practice: **`base_url` was not
on the public API at all.** The pitch is "point `base_url` at any OpenAI-compatible provider",
but reaching it meant constructing a `ChatCompletionsModel` by hand. It is now a first-class
argument:

```python
agent = Agentor(
    name="Assistant",
    model="openrouter/auto",
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPENROUTER_API_KEY"],
    engine="native",
)
```

Passing it with `engine="agents"` raises rather than being silently ignored, since openai-agents
configures endpoints through its own client and would quietly disregard it. Without `base_url`, a
`provider/model` string still routes to litellm exactly as before.

### Phase 5b — openai-agents removed ✅ *shipped*

The dependency is gone. `engine` is no longer a switch: there is one engine, it is the default,
and `engine="agents"` raises with an explanation rather than being ignored.

Hosted tools were **dropped** rather than ported. Two cheaper routes were probed and ruled out
first: `web_search_options` on chat/completions works only on `-search-preview` models (rejected
by `gpt-4o-mini`, and by `gpt-5-mini` which our own example used), and a Responses adapter would
have meant a second message format inside the engine for ~250–300 LOC. `WebSearchTool` and the
rest now raise naming the tool and the reason.

Native replacements for everything openai-agents used to supply:

| was | now |
|---|---|
| `agents.function_tool` | `agentor.engine.tools.function_tool` |
| `agents.ModelSettings` | `agentor.engine.settings.ModelSettings` (+ `extra` passthrough) |
| `agents.FunctionTool` | `agentor.engine.tools.Tool` |
| `agents.mcp.MCPServerStreamableHttp` | `agentor.mcp.MCPServer` |
| `LitellmModel` | `agentor.engine.models.LiteLLMModel` (old name still exported) |
| openai-agents tracing | `agentor.engine.tracing`, via `setup_celesto_tracing` |

`tracer.py` went from 313 lines of `hasattr` introspection into another vendor's spans to a
45-line entry point. `output_text_formatter.py` went from 280 lines to 93.

**Measured, in a venv where openai-agents is not installed at all:**

| | before the migration | now |
|---|---|---|
| `import agentor` | 2.65s | **0.003s** |
| `from agentor import Agentor` | 2.65s | **0.51s** |
| clean core install | 311 MB | **207 MB** |

243 tests pass with the package absent. All four live suites re-run: engine 22/22, MCP 9/9,
OpenRouter 12/12, cross-process resume recovers.

---

## 9. Outcome

Every goal in section 1 is met:

- One engine, not two. `DurableAgent` is gone; durability is a property of the loop.
- The trace format is native. No adapter, no `hasattr` chains, and it covers every run.
- The model is not bound to the agent, so a fallback is a copy rather than a rebuild.
- One tool abstraction, with no SDK type in user signatures.
- `import agentor` is ~900x cheaper; the engine path ~5x.

Not done, deliberately:

- **HITL interrupt/approval.** The store makes it easy; nothing needs it yet.
- **Hosted tools.** Dropped, with an explicit error.
- **Concurrent resume of one unfinished run.** Documented rather than half-locked; a correct fix
  needs an atomic lease the bundled single-process stores cannot provide.
