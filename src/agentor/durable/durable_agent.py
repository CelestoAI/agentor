import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Optional

import litellm

logger = logging.getLogger(__name__)


@dataclass
class RunResult:
    run_id: str
    status: Literal["running", "completed", "failed"]
    final_answer: Optional[str]
    events: List[Dict[str, Any]]


class DurableAgent:
    def __init__(
        self,
        model: str,
        tools: List[Any],
        runs_dir: str = "runs",
        verbose: bool = False,
    ):
        """
        Initialize the DurableAgent.

        Args:
            model: litellm model name (e.g. "gpt-4-turbo")
            tools: List of BaseTool/ToolConvertor objects
            runs_dir: Directory where run logs will be stored
            verbose: If True, print run status to stdout.
        """
        self.model = model
        self.runs_dir = Path(runs_dir)
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.verbose = verbose

        # Parse tools
        self.tools = {}
        self.tool_schemas = []
        self._parse_tools(tools)

    def run(
        self,
        input_text: Optional[str] = None,
        run_id: Optional[str] = None,
        max_steps: int = 10,
    ) -> RunResult:
        """
        Run or resume an agent execution.

        Args:
            input_text: Initial input for a new run. Required if run_id is None.
            run_id: ID of an existing run to resume. If provided, input_text is ignored.
            max_steps: Maximum number of new steps to execute in this call.

        Returns:
            RunResult object containing the run status and output.
        """
        if run_id is None:
            if not input_text:
                raise ValueError("input_text is required for a new run")
            run_id = self._new_run(input_text)
            if self.verbose:
                print(f"--- Starting Run {run_id} ---")
        else:
            if self.verbose:
                print(f"--- Resuming Run {run_id} ---")
        events = self._load_events(run_id)

        # If already completed, just return
        if self._is_completed(events):
            final_answer = self._get_final_answer(events)
            return RunResult(run_id, "completed", final_answer, events)

        steps = 0
        while steps < max_steps:
            steps += 1
            events = self._load_events(
                run_id
            )  # reload each loop in case of external writers

            # 1) Check for pending tool calls
            pending_call = self._find_pending_tool_call(events)
            if pending_call:
                self._execute_tool_call(run_id, pending_call)
                continue

            # 2) Otherwise, ask LLM what to do next
            messages = self._build_messages(events)
            llm_resp = self._call_llm(messages)

            # Store raw response first to ensure we capture exactly what happened
            self._append_event(run_id, "llm_response", {"raw": llm_resp.model_dump()})

            tool_calls = self._extract_tool_calls(llm_resp)

            if tool_calls:
                # log each tool call as pending
                for tc in tool_calls:
                    self._append_event(
                        run_id,
                        "tool_call",
                        {
                            "tool_call_id": tc["id"],
                            "tool_name": tc["name"],
                            "args": tc["args"],
                            "status": "pending",
                        },
                    )

                # If we filtered out everything, we need to continue the loop to let LLM try again with the error message
                continue
            else:
                # no tools -> treat as final answer
                final_answer = self._extract_final_answer(llm_resp)
                self._append_event(
                    run_id,
                    "run_status",
                    {
                        "status": "completed",
                        "final_answer": final_answer,
                    },
                )
                events = self._load_events(run_id)
                return RunResult(run_id, "completed", final_answer, events)

        # max_steps hit, still running
        events = self._load_events(run_id)
        return RunResult(run_id, "running", None, events)

    # ---------- Internal Helpers ----------

    def _new_run(self, input_text: str) -> str:
        run_id = uuid.uuid4().hex
        self._append_event(run_id, "user_message", {"content": input_text})
        return run_id

    def _log_path(self, run_id: str) -> Path:
        return self.runs_dir / f"{run_id}.jsonl"

    def _append_event(self, run_id: str, type_: str, payload: Dict[str, Any]) -> None:
        path = self._log_path(run_id)

        # Calculate step_index
        step_index = 0
        if path.exists():
            with path.open("r", encoding="utf-8") as f:
                step_index = sum(1 for _ in f)

        event = {
            "run_id": run_id,
            "step_index": step_index,
            "type": type_,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "payload": payload,
        }

        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")

    def _load_events(self, run_id: str) -> List[Dict[str, Any]]:
        path = self._log_path(run_id)
        if not path.exists():
            return []

        events = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    events.append(json.loads(line))
        return events

    def _is_completed(self, events: List[Dict[str, Any]]) -> bool:
        return any(
            e["type"] == "run_status" and e["payload"].get("status") == "completed"
            for e in events
        )

    def _get_final_answer(self, events: List[Dict[str, Any]]) -> Optional[str]:
        for e in reversed(events):
            if e["type"] == "run_status":
                return e["payload"].get("final_answer")
        return None

    def _find_pending_tool_call(
        self, events: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        # With in-place updates, we can just look for the first tool_call with status="pending"
        # Note: events are loaded sequentially. If we updated the file, the loaded events should reflect "done".

        for e in events:
            if e["type"] == "tool_call":
                if e["payload"].get("status") == "pending":
                    return e
        return None

    def _execute_tool_call(self, run_id: str, tool_call_event: Dict[str, Any]) -> None:
        payload = tool_call_event["payload"]
        tool_name = payload["tool_name"]
        args = payload["args"]
        tc_id = payload["tool_call_id"]

        if tool_name not in self.tools:
            error_msg = f"Tool '{tool_name}' not found"
            self._append_event(
                run_id,
                "tool_result",
                {
                    "tool_call_id": tc_id,
                    "tool_name": tool_name,
                    "error": error_msg,
                },
            )
            # We treat missing tool as a fatal error for this design
            self._append_event(
                run_id,
                "run_status",
                {"status": "failed", "error": error_msg},
            )
            return

        tool_fn = self.tools[tool_name]

        try:
            output = tool_fn(**args)
            # result
            self._append_event(
                run_id,
                "tool_result",
                {
                    "tool_call_id": tc_id,
                    "tool_name": tool_name,
                    "output": str(output),  # Ensure string
                },
            )

            # Update the original tool_call status to "done" in the file
            self._update_event_payload(
                run_id,
                "tool_call",
                lambda p: p["tool_call_id"] == tc_id,
                {"status": "done"},
            )

        except Exception as e:
            self._append_event(
                run_id,
                "tool_result",
                {
                    "tool_call_id": tc_id,
                    "tool_name": tool_name,
                    "error": str(e),
                },
            )
            self._append_event(
                run_id,
                "run_status",
                {
                    "status": "failed",
                    "error": str(e),
                },
            )
            # Raising exception here to stop execution immediately
            # as per design "raise" in pseudo code
            raise

    def _build_messages(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
        ]

        # We need to track tool calls to match results
        # But for simple reconstruction:

        for e in events:
            if e["type"] == "user_message":
                messages.append({"role": "user", "content": e["payload"]["content"]})
            elif e["type"] == "llm_response":
                # reconstruct from raw
                raw = e["payload"]["raw"]
                # Handle different raw formats if necessary, assuming standard litellm/openai response
                if "choices" in raw and len(raw["choices"]) > 0:
                    msg = raw["choices"][0]["message"]
                    # Clean up keys for litellm input (e.g. remove none values if needed)
                    # For now pass as is, litellm handles it
                    messages.append(msg)
            elif e["type"] == "tool_result":
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": e["payload"]["tool_call_id"],
                        "name": e["payload"]["tool_name"],
                        "content": e["payload"].get("output")
                        or e["payload"].get("error")
                        or "",
                    }
                )

        return messages

    def _call_llm(self, messages: List[Dict[str, Any]]) -> Any:
        # Convert tools to schema
        # Assuming generic function schema generation or user provided valid schema tools?
        # The design says: tools: dict[str, callable].
        # We need to convert these callables to OpenAI tool schemas.
        # For this v1, let's assume we can use a helper or just bare basics.
        # Since I see 'src/agentor/core/tool.py' in the file list earlier,
        # I might use that if available, but for now I'll use litellm's auto-generation or expect the user to have simpler tools.
        # Actually, `litellm` can't automatically convert raw callables to schemas unless we use a helper.
        # BUT the design code commented: # tools=..., # define schema for your scrape_wiki, etc.
        # For this implementation, I should probably try to inspect the functions.
        # However, to keep it simple and robust (matches design "dict[str, callable]"),
        # I will use a simple utility to generate schemas if possible, or just pass them if litellm supports it (it partially does with specific helper).
        # Let's check imports. I have `litellm`.

        # NOTE: Using `litellm.completion` with `tools` requires the tools argument to be a list of schemas.
        # The `DurableAgent` receives `Dict[str, Callable]`.
        # I need to generate schemas.
        # For now, I will add a basic schema generator or check if I can reuse `agentor.utils` or similar.
        # I saw `src/agentor/tool_search.py` and `src/agentor/core/tool.py`.
        # I'll optimistically skip complex schema generation for this specific file write
        # and assume the user takes care of it OR I'll add a minimal introspection.

        # Let's use `openai_agents` or similar if it was in requirements?
        # `agentor` seems to have its own things.
        # I'll implement a VERY basic schema generator here to match `dict[str, callable]` contract
        # so it actually works for simple functions.

        response = litellm.completion(
            model=self.model,
            messages=messages,
            tools=self.tool_schemas if self.tool_schemas else None,
            tool_choice="auto" if self.tool_schemas else None,
        )
        return response

    def _update_event_payload(
        self,
        run_id: str,
        event_type: str,
        match_fn: Callable[[Dict[str, Any]], bool],
        updates: Dict[str, Any],
    ) -> None:
        """
        Rewrites the run log file to update specific events.
        This is an expensive operation (O(N) read/write), but keeps the log clean as requested.
        """
        path = self._log_path(run_id)
        if not path.exists():
            return

        # Read ALL events
        events = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    events.append(json.loads(line))

        # Update matching events
        updated = False
        for e in events:
            if e["type"] == event_type and match_fn(e["payload"]):
                e["payload"].update(updates)
                updated = True

        # Write back ONLY if changed
        if updated:
            # Atomic write pattern to avoid corruption
            temp_path = path.with_suffix(".tmp")
            with temp_path.open("w", encoding="utf-8") as f:
                for e in events:
                    f.write(json.dumps(e) + "\n")
            temp_path.replace(path)

    def _parse_tools(self, tools: List[Any]):
        self.tools = {}
        self.tool_schemas = []
        for t in tools:
            if hasattr(t, "to_openai_function"):  # BaseTool
                # It returns a list of FunctionTool objects
                fns = t.to_openai_function()
                for fn in fns:
                    # Extract the actual callable method from the BaseTool instance
                    try:
                        callable_method = t._get_tool(fn.name)
                        self.tools[fn.name] = callable_method
                        self.tool_schemas.append(
                            {
                                "type": "function",
                                "function": {
                                    "name": fn.name,
                                    "description": fn.description,
                                    "parameters": fn.params_json_schema,
                                },
                            }
                        )
                    except ValueError:
                        logger.error(
                            f"Capability name mismatch or not found for tool: {t.name}"
                        )
                        pass
            elif hasattr(t, "to_llm_function"):  # ToolConvertor
                self.tools[t.name] = t
                self.tool_schemas.append(t.json_schema())
            # Removed direct FunctionTool handling and generic callable fallback as per instructions.

    def _get_tool_schemas(self):
        # Deprecated by _parse_tools populating self.tool_schemas
        return self.tool_schemas

    def _extract_tool_calls(self, llm_resp: Any) -> List[Dict[str, Any]]:
        if not hasattr(llm_resp, "choices") or not llm_resp.choices:
            return []

        msg = llm_resp.choices[0].message
        # Check if attribute exists, fallback to None
        tool_calls = getattr(msg, "tool_calls", None) or []
        result = []
        for tc in tool_calls:
            result.append(
                {
                    "id": tc.id,
                    "name": tc.function.name,
                    "args": json.loads(tc.function.arguments or "{}"),
                }
            )
        return result

    def _extract_final_answer(self, llm_resp: Any) -> str:
        if not hasattr(llm_resp, "choices") or not llm_resp.choices:
            return ""
        return llm_resp.choices[0].message.content or ""
