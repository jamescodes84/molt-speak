"""Crowd Control status notifier for debug visualization.

Writes crowd control state to runtime/crowd_control_status.json
so external tools (debug visualizer) can monitor speaker gate decisions.

Follows the same IPC pattern as EarsStatusNotifier.
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path

logger = logging.getLogger("open_ears.cc_notifier")


class CrowdControlNotifier:
    """Writes crowd control status to a JSON file for external consumers."""

    def __init__(self, status_file: Path):
        self._status_file = status_file
        self._status_file.parent.mkdir(parents=True, exist_ok=True)

    def update(self, rms: float, vad: bool, gate_state: str,
               decision: str, similarity: float, threshold: float,
               buffered_ms: int, enrolled: bool, enabled: bool) -> None:
        """Write current crowd control state to disk (atomic)."""
        data = {
            "ts": time.time(),
            "rms": round(rms, 1),
            "vad": vad,
            "gate_state": gate_state,
            "decision": decision,
            "similarity": round(similarity, 4),
            "threshold": threshold,
            "buffered_ms": buffered_ms,
            "enrolled": enrolled,
            "enabled": enabled,
        }
        try:
            tmp = self._status_file.with_suffix(".tmp")
            tmp.write_text(json.dumps(data))
            tmp.rename(self._status_file)
        except Exception as e:
            logger.debug("Failed to write CC status: %s", e)

    def cleanup(self) -> None:
        """Remove the status file."""
        try:
            if self._status_file.exists():
                self._status_file.unlink()
        except Exception as e:
            logger.debug("Failed to cleanup CC status: %s", e)
