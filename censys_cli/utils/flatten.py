"""
Utilities for flattening nested dictionaries and selecting specific fields.
Used for CSV output and field filtering in the Censys CLI.
"""
from typing import Any, Dict, List

def _stringify(value: Any) -> str:
    """Convert a value to a string representation."""
    if isinstance(value, (list, tuple)):
        return ",".join([_stringify(v) for v in value])
    if isinstance(value, dict):
        items = []
        for k, v in value.items():
            items.append(f"{k}:{_stringify(v)}")
        return "{" + ",".join(items) + "}"
    if value is None:
        return ""
    return str(value)

class FlattenHelper:
    @staticmethod
    def flatten(d: Dict[str, Any], sep: str = ".") -> Dict[str, Any]:
        """Flatten a nested dictionary into a single-level dictionary with dot notation."""
        out: Dict[str, Any] = {}
        def _rec(prefix: str, obj: Any):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    _rec(f"{prefix}{sep}{k}" if prefix else k, v)
            elif isinstance(obj, list):
                if not obj:
                    out[prefix] = ""
                else:
                    for i, v in enumerate(obj):
                        _rec(f"{prefix}[{i}]", v)
            else:
                out[prefix] = obj if isinstance(obj, (int, float, str)) else _stringify(obj)
        _rec("", d)
        return out

    @staticmethod
    def select_fields(d: Dict[str, Any], fields: List[str]) -> Dict[str, Any]:
        """Extract specified fields from a dictionary using dot notation and list indices."""
        def get_path(obj: Any, path: str):
            cur = obj
            import re
            tokens = re.findall(r"[^\.\[\]]+|\[\d+\]", path)
            for t in tokens:
                if t.startswith("[") and t.endswith("]"):
                    idx = int(t[1:-1])
                    if isinstance(cur, list) and 0 <= idx < len(cur):
                        cur = cur[idx]
                    else:
                        return None
                else:
                    if isinstance(cur, dict) and t in cur:
                        cur = cur[t]
                    else:
                        return None
            return cur
        return {f: get_path(d, f) for f in fields}

    @staticmethod
    def stringify(x: Any) -> str:
        """Convert a value to a string, handling complex types."""
        return _stringify(x)