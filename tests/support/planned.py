from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any

from tests.support.contracts import require_python_symbol, trace_message


def planned_callable(relative_path: str, symbol: str, trace_id: str) -> Callable[..., Any]:
    target = require_python_symbol(relative_path, symbol, trace_id)
    assert callable(target), trace_message(trace_id, f"planned symbol is not callable: {symbol}")
    return target


def planned_signature(
    relative_path: str,
    symbol: str,
    required_parameters: tuple[str, ...],
    trace_id: str,
) -> inspect.Signature:
    target = planned_callable(relative_path, symbol, trace_id)
    signature = inspect.signature(target)
    missing = [name for name in required_parameters if name not in signature.parameters]
    assert not missing, trace_message(trace_id, f"signature lacks parameters: {missing}")
    return signature
