from __future__ import annotations

import dataclasses
import datetime as dt
import enum
import json
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable, Mapping
from uuid import UUID

from pydantic import BaseModel

try:
    import numpy as np  # type: ignore
except Exception:  # numpy not installed
    np = None  # type: ignore


def serialize(
    obj: Any,
    *,
    convert_keys_to_str: bool = True,
    decimal_to_str: bool = True,
    max_depth: int | None = None,
    dump_json: bool = False,
) -> Any | str | bytes:
    """
    Recursively convert `obj` into JSON-serializable Python primitives.

    - Dataclasses -> dict
    - Pydantic BaseModel (v1/v2) -> dict
    - Enums -> value
    - datetime/date/time -> ISO 8601 string
    - Decimal -> str (or float if decimal_to_str=False)
    - UUID/Path -> str
    - sets/tuples -> list
    - numpy scalars/arrays -> python scalars/lists
    - Mappings/Iterables -> dict/list
    - Falls back to __dict__ when sensible

    Args:
        convert_keys_to_str: If True, mapping keys are stringified (JSON requires string keys).
        decimal_to_str: If True, Decimal -> str, else float.
        max_depth: Optional recursion cap; when reached, returns a stub string.
        dump_json: If True, dump the object to a JSON string.
    Returns:
        A structure of only {dict, list, str, int, float, bool, None} suitable for json.dumps.
        If dump_json is True, returns a JSON string.
        Otherwise, returns the object.
    """
    seen: set[int] = set()

    def _numpy_scalar(x: Any) -> bool:
        return np is not None and isinstance(
            x, getattr(np, "generic", ())
        )  # numpy scalar types

    def _convert(o: Any, depth: int) -> Any:
        if max_depth is not None and depth > max_depth:
            return f"<max_depth reached at {type(o).__name__}>"

        oid = id(o)
        if isinstance(o, (dict, list, tuple, set)) or dataclasses.is_dataclass(o):
            # track containers for cycle detection
            if oid in seen:
                return f"<recursion {type(o).__name__}>"
            seen.add(oid)

        # Primitives pass through
        if o is None or isinstance(o, (bool, int, float, str)):
            return o

        # Dataclasses
        if dataclasses.is_dataclass(o):
            o = dataclasses.asdict(o)
            return _convert(o, depth + 1)

        # Pydantic models (v2 has .model_dump, v1 has .dict)
        if isinstance(o, BaseModel):
            try:
                data = o.model_dump(mode="python")  # pydantic v2
            except Exception:
                data = o.dict()  # pydantic v1
            return _convert(data, depth + 1)

        # Enums -> underlying value
        if isinstance(o, enum.Enum):
            return _convert(o.value, depth + 1)

        # datetime/date/time -> ISO
        if isinstance(o, (dt.datetime, dt.date, dt.time)):
            # Preserve timezone info if present
            try:
                return o.isoformat()
            except Exception:
                return str(o)

        # Decimal
        if isinstance(o, Decimal):
            return str(o) if decimal_to_str else float(o)

        # UUID / Path
        if isinstance(o, (UUID, Path)):
            return str(o)

        # bytes / bytearray -> hex string (safe, no encoding assumption)
        if isinstance(o, (bytes, bytearray, memoryview)):
            return bytes(o).hex()

        # NumPy types
        if np is not None:
            if isinstance(o, np.ndarray):
                return _convert(o.tolist(), depth + 1)
            if _numpy_scalar(o):
                return o.item()

        # Mapping
        if isinstance(o, Mapping):
            if convert_keys_to_str:
                return {str(k): _convert(v, depth + 1) for k, v in o.items()}
            else:
                return {k: _convert(v, depth + 1) for k, v in o.items()}

        # Iterables (list/tuple/set/tuple-like)
        if isinstance(o, (list, tuple, set, frozenset)):
            return [_convert(i, depth + 1) for i in o]

        if isinstance(o, Iterable) and not isinstance(o, (str, bytes, bytearray)):
            # Catch-all for other iterables/generators
            return [_convert(i, depth + 1) for i in o]

        # Objects with __dict__ (as a last resort)
        if hasattr(o, "__dict__"):
            return _convert(vars(o), depth + 1)

        # Fallback: string representation
        return str(o)

    if dump_json:
        return json.dumps(_convert(obj, depth=0))
    else:
        return _convert(obj, depth=0)
