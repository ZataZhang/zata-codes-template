"""Agent 与 Run 快照使用的稳定内容摘要。"""

from __future__ import annotations

import hashlib
import json


def _checksum(value: object) -> str:
    """计算稳定 JSON 值的 SHA-256。"""
    serialized_value = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized_value.encode("utf-8")).hexdigest()
