"""
Environment Memory — Persistent Cross-Session Entity Memory

Learns about entities in the user's environment (pets, people) from corrections.
When the user says "I wasn't talking to you, I was talking to my dog," the system
extracts the entity (pet:dog) and stores associated phrases for future matching.

Persists to ~/Library/Application Support/molt-speak/environment_memory.json.

Design: enhance information, don't restrict behavior. This data feeds into the
PragmaticAnalyzer's composite score, which the agent uses to make its own decision.
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, List

logger = logging.getLogger(__name__)


def _get_memory_path() -> Path:
    """Memory file lives alongside social_cues_lifespan.json."""
    support_dir = Path.home() / "Library" / "Application Support" / "molt-speak"
    support_dir.mkdir(parents=True, exist_ok=True)
    return support_dir / "environment_memory.json"


_MEMORY_DEFAULT = {
    "version": 1,
    "updated_at": "",
    "entities": [],
}

MAX_ENTITIES = 10
MAX_PHRASES = 20

# Entity extraction patterns from correction text
_PET_PATTERN = re.compile(
    r"(?:talk(?:ing|ed)?\s+to|for)\s+(?:my|the|our)\s+"
    r"(dog|cat|pet|bird|parrot|hamster|rabbit|fish|puppy|kitten|kitty)",
    re.IGNORECASE,
)

_PERSON_PATTERN = re.compile(
    r"(?:talk(?:ing|ed)?\s+to|for)\s+"
    r"(?:my\s+(?:friend|wife|husband|partner|kid|son|daughter|mom|dad|brother|sister|roommate|colleague)\s+)?"
    r"([A-Z][a-z]+)",
)

_GENERIC_PET_PATTERN = re.compile(
    r"(?:that\s+was\s+for|talking\s+to)\s+(?:the\s+)?(dog|cat|pet|bird|puppy|kitten|kitty)",
    re.IGNORECASE,
)


class EnvironmentMemory:
    """
    Persistent memory of entities in the user's environment.

    Learns from corrections and uses phrase matching to identify
    when an utterance is likely directed at a known entity.
    """

    def __init__(self):
        self._data = self._load()
        self._last_correction_time = 0.0
        self._pending_prev_text = ""

    # ── I/O ────────────────────────────────────────────────────────────

    @staticmethod
    def _load() -> dict:
        path = _get_memory_path()
        if path.exists():
            try:
                data = json.loads(path.read_text())
                for k, v in _MEMORY_DEFAULT.items():
                    if k not in data:
                        data[k] = v
                return data
            except (json.JSONDecodeError, OSError):
                pass
        return _MEMORY_DEFAULT.copy()

    def _save(self) -> None:
        path = _get_memory_path()
        self._data["updated_at"] = datetime.now().isoformat()
        try:
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._data, indent=2))
            tmp.replace(path)  # atomic on POSIX
        except OSError as e:
            logger.warning(f"Failed to save environment memory: {e}")

    # ── Public API ─────────────────────────────────────────────────────

    def get_known_entities(self) -> list[str]:
        """Return entity labels for context_analysis JSON.

        Returns list like ['dog', 'person:Lisa'].
        """
        result = []
        for entity in self._data.get("entities", []):
            etype = entity.get("type", "")
            if etype == "pet":
                species = entity.get("species", "pet")
                result.append(species)
            elif etype == "person":
                names = entity.get("names", [])
                if names:
                    result.append(f"person:{names[0]}")
                else:
                    result.append("person")
        return result

    def match_entity(self, text: str) -> str:
        """Check if text matches known entity phrases.

        Returns entity type string (e.g., 'dog') if matched, empty string otherwise.
        """
        lower = text.lower().strip()
        best_match = ""
        best_score = 0

        for entity in self._data.get("entities", []):
            phrases = entity.get("associated_phrases", [])
            for phrase in phrases:
                if phrase.lower() in lower:
                    # Longer phrase matches are stronger
                    score = len(phrase)
                    if score > best_score:
                        best_score = score
                        if entity.get("type") == "pet":
                            best_match = entity.get("species", "pet")
                        elif entity.get("type") == "person":
                            names = entity.get("names", [])
                            best_match = f"person:{names[0]}" if names else "person"

            # Also match entity names directly
            for name in entity.get("names", []):
                if name.lower() in lower:
                    score = len(name)
                    if score > best_score:
                        best_score = score
                        if entity.get("type") == "pet":
                            best_match = entity.get("species", "pet")
                        elif entity.get("type") == "person":
                            best_match = f"person:{name}"

        return best_match

    def learn_from_correction(self, correction_text: str, prev_text: str) -> None:
        """Learn entities from a correction utterance.

        Args:
            correction_text: The correction utterance (e.g., "I wasn't talking to you, I was talking to my dog")
            prev_text: The previous utterance that was falsely accepted (e.g., "hey buddy what's up")
        """
        self._last_correction_time = time.time()
        self._pending_prev_text = prev_text
        self._extract_and_store(correction_text, prev_text)

    def check_followup_learning(self, text: str) -> None:
        """Call on every utterance. If within 15s of a correction, try entity extraction.

        Handles multi-utterance corrections where entity info arrives in a follow-up:
        "I wasn't talking to you." (pause) "I was talking to my dog."
        """
        if self._last_correction_time and (time.time() - self._last_correction_time) < 15:
            extracted = self._extract_and_store(text, self._pending_prev_text)
            if extracted:
                self._last_correction_time = 0  # consume the window
        else:
            # Window expired
            self._last_correction_time = 0

    # ── Internal ───────────────────────────────────────────────────────

    def _extract_and_store(self, text: str, prev_text: str) -> bool:
        """Extract entity from text and store it. Returns True if entity found."""
        entity_info = self._extract_entity(text)
        if not entity_info:
            return False

        etype, species_or_name = entity_info

        # Find or create entity
        entities = self._data.get("entities", [])
        existing = None
        for e in entities:
            if e.get("type") == etype:
                if etype == "pet" and e.get("species") == species_or_name:
                    existing = e
                    break
                elif etype == "person" and species_or_name in e.get("names", []):
                    existing = e
                    break

        if existing:
            existing["observation_count"] = existing.get("observation_count", 0) + 1
            # Add the falsely-accepted phrase
            if prev_text:
                phrases = existing.get("associated_phrases", [])
                normalized = prev_text.lower().strip()
                if normalized and normalized not in phrases:
                    phrases.append(normalized)
                    if len(phrases) > MAX_PHRASES:
                        phrases = phrases[-MAX_PHRASES:]
                    existing["associated_phrases"] = phrases
        else:
            # Create new entity
            if len(entities) >= MAX_ENTITIES:
                # Prune oldest by first_observed
                entities.sort(key=lambda e: e.get("first_observed", ""))
                entities.pop(0)

            new_entity = {
                "type": etype,
                "first_observed": datetime.now().isoformat(),
                "observation_count": 1,
                "associated_phrases": [],
                "names": [],
            }

            if etype == "pet":
                new_entity["species"] = species_or_name
            elif etype == "person":
                new_entity["names"] = [species_or_name]

            if prev_text:
                new_entity["associated_phrases"] = [prev_text.lower().strip()]

            entities.append(new_entity)

        self._data["entities"] = entities
        self._save()
        logger.info(f"EnvironmentMemory learned: {etype}={species_or_name} "
                     f"(phrase: '{prev_text[:50]}')")
        return True

    @staticmethod
    def _extract_entity(text: str) -> tuple[str, str] | None:
        """Extract entity type and identifier from correction text.

        Returns ('pet', 'dog') or ('person', 'Lisa') or None.
        """
        # Try pet patterns first (most common case)
        m = _PET_PATTERN.search(text)
        if m:
            return ("pet", m.group(1).lower())

        m = _GENERIC_PET_PATTERN.search(text)
        if m:
            return ("pet", m.group(1).lower())

        # Try person pattern
        m = _PERSON_PATTERN.search(text)
        if m:
            name = m.group(1)
            # Filter out common false positives
            if name.lower() not in {"the", "my", "our", "that", "this", "not"}:
                return ("person", name)

        return None
