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

# Hold a decision visible for this many seconds so the viz can display it
DECISION_HOLD_SECONDS = 2.0


class CrowdControlNotifier:
    """Writes crowd control status to a JSON file for external consumers."""

    def __init__(self, status_file: Path):
        self._status_file = status_file
        self._status_file.parent.mkdir(parents=True, exist_ok=True)
        self._held_gate_state = "idle"
        self._held_decision = "pending"
        self._held_similarity = 0.0
        self._held_until = 0.0

    def update(self, rms: float, vad: bool, gate_state: str,
               decision: str, similarity: float, threshold: float,
               buffered_ms: int, enrolled: bool, enabled: bool) -> None:
        """Write current crowd control state to disk (atomic).

        Holds 'decided' state for DECISION_HOLD_SECONDS so the viz
        can catch it even though the capture loop resets to 'idle' each frame.
        """
        now = time.time()

        # Latch new decisions
        if gate_state == "decided":
            self._held_gate_state = "decided"
            self._held_decision = decision
            self._held_similarity = similarity
            self._held_until = now + DECISION_HOLD_SECONDS

        # Use held state if still within hold window
        if now < self._held_until:
            gate_state = self._held_gate_state
            decision = self._held_decision
            similarity = self._held_similarity
        elif gate_state != "accumulating":
            # Hold expired, reset
            self._held_gate_state = "idle"
            self._held_decision = "pending"
            self._held_similarity = 0.0

        data = {
            "ts": now,
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
