"""
Pragmatic Coherence Analyzer — Contextual Intelligence Layer

Evaluates whether an utterance pragmatically coheres with the ongoing conversation.
When it doesn't — greeting mid-conversation, zero topic overlap, pet-register
vocabulary, physical action commands — the evidence suggests the utterance is
directed at someone else.

Stateless: takes all inputs as arguments, no internal state. String operations
only — runs in microseconds.

Research basis:
- Schegloff & Sacks (1973): Greetings are conversation openers, not continuations
- Bell (1984) Audience Design: Register shifts signal audience change
- Goffman (1974): Frame breaks without transition markers = addressee exit
- Barzilay & Lapata: Entity coherence / topic continuity
- Clark & Carlson: Addressee vs. overhearer distinction

Design philosophy: Enhance information, don't restrict behavior. The agent at
boldness 100 still makes the final call — but with a full tactical display
instead of raw transcription + a temperature number.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Tuple, Set

logger = logging.getLogger(__name__)


# ── Vocabulary sets ────────────────────────────────────────────────────

PHATIC_GREETINGS = frozenset({
    "what's up", "how's it going", "how are you", "how you doing",
    "what's going on", "hey there", "hey buddy", "hey girl", "hey boy",
    "whatcha doing", "how's my", "who's a good", "hey baby",
    "hey sweetie", "hey pup", "hey puppy",
})

PET_REGISTER = frozenset({
    "buddy", "boy", "girl", "baby", "sweetie", "pup", "puppy",
    "kitty", "good boy", "good girl", "who's a good", "come here",
    "treat", "walkies", "fetch",
})

PHYSICAL_ACTIONS = frozenset({
    "come", "sit", "stay", "down", "fetch", "roll", "shake",
    "heel", "leave it", "drop it", "paw", "off", "bed", "crate",
    "outside", "go potty",
})

# Common function words to exclude from topic continuity
_STOP_WORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "dare", "ought",
    "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "as", "into", "through", "during", "before", "after", "above",
    "below", "between", "out", "about", "against", "and", "but", "or",
    "nor", "not", "so", "yet", "both", "either", "neither", "each",
    "every", "all", "any", "few", "more", "most", "other", "some",
    "such", "no", "only", "own", "same", "than", "too", "very",
    "just", "because", "if", "when", "where", "how", "what", "which",
    "who", "whom", "this", "that", "these", "those", "i", "me", "my",
    "we", "our", "you", "your", "he", "him", "his", "she", "her",
    "it", "its", "they", "them", "their", "there", "here", "then",
    "also", "well", "like", "yeah", "okay", "ok", "right", "um",
    "uh", "know", "think", "want", "going", "got", "get", "make",
    "let", "say", "said",
})


# ── Data structures ────────────────────────────────────────────────────

@dataclass
class PragmaticReading:
    """Pragmatic coherence analysis for one utterance."""
    not_for_me_evidence: float = 0.0      # 0.0-1.0 composite
    topic_continuity: float = 1.0          # 0.0-1.0 (1.0 = perfect continuity)
    register_shift: str = "none"           # none / mild / significant / extreme
    greeting_mid_conversation: bool = False
    pet_or_child_directed: bool = False
    physical_action_detected: bool = False
    suspicion_reasons: list = field(default_factory=list)
    known_entity_match: str = ""           # e.g., "dog" if matched


# ── Main class ─────────────────────────────────────────────────────────

class PragmaticAnalyzer:
    """
    Stateless pragmatic coherence scorer.

    Takes all inputs as arguments. No internal state — safe to call
    from any thread, any number of times.
    """

    def analyze(
        self,
        text: str,
        recent_texts: list[str],
        exchange_count: int,
        known_entities: list[str],
        entity_match: str,
    ) -> PragmaticReading:
        """Analyze pragmatic coherence of an utterance.

        Args:
            text: Current utterance text
            recent_texts: Last 5 user utterances (for topic/register comparison)
            exchange_count: Number of completed exchanges in this session
            known_entities: List of known entity labels from EnvironmentMemory
            entity_match: Entity match result from EnvironmentMemory ('' if none)

        Returns:
            PragmaticReading with composite score and individual signals
        """
        # Normalize smart quotes from Whisper
        normalized = text.lower().strip().replace("\u2019", "'").replace("\u2018", "'")

        # Signal 1: Greeting anomaly
        greeting = self._detect_greeting_anomaly(normalized, exchange_count)

        # Signal 2: Topic continuity
        topic_cont = self._compute_topic_continuity(normalized, recent_texts)

        # Signal 3: Register shift
        register, pet_register_detected = self._detect_register_shift(
            normalized, recent_texts
        )

        # Signal 4: Physical action commands (short utterances only)
        physical = self._detect_physical_action(normalized)

        # Signal 5: Known entity match (from EnvironmentMemory)
        has_entity_match = bool(entity_match)

        # Composite score
        score, reasons = self._compute_composite(
            greeting=greeting,
            topic_cont=topic_cont,
            register=register,
            pet_register_detected=pet_register_detected,
            physical_action=physical,
            entity_match=has_entity_match,
            entity_label=entity_match,
        )

        reading = PragmaticReading(
            not_for_me_evidence=round(score, 2),
            topic_continuity=round(topic_cont, 2),
            register_shift=register,
            greeting_mid_conversation=greeting,
            pet_or_child_directed=pet_register_detected,
            physical_action_detected=physical,
            suspicion_reasons=reasons,
            known_entity_match=entity_match,
        )

        return reading

    # ── Signal 1: Greeting Anomaly (Schegloff & Sacks) ─────────────────

    @staticmethod
    def _detect_greeting_anomaly(text: str, exchange_count: int) -> bool:
        """Detect phatic greetings that are sequentially inapposite mid-conversation.

        Greetings are conversation openers. After 2+ completed exchanges,
        a greeting signals addressee change, not continuation.
        """
        if exchange_count < 3:
            return False
        return any(g in text for g in PHATIC_GREETINGS)

    # ── Signal 2: Topic Continuity (Barzilay & Lapata) ─────────────────

    @staticmethod
    def _compute_topic_continuity(text: str, recent_texts: list[str]) -> float:
        """Jaccard similarity of content words between current and recent turns.

        Returns 0.0 (zero overlap) to 1.0 (perfect overlap).
        Cold start returns 1.0 (no basis for comparison → no suspicion).
        """
        if not recent_texts:
            return 1.0

        current_words = _content_words(text)
        recent_words = set()
        for t in recent_texts[-5:]:
            recent_words.update(_content_words(t.lower()))

        if not current_words or not recent_words:
            return 0.5  # can't compute — neutral

        intersection = current_words & recent_words
        union = current_words | recent_words
        return len(intersection) / len(union) if union else 0.5

    # ── Signal 3: Register Shift (Bell's Audience Design) ──────────────

    @staticmethod
    def _detect_register_shift(
        text: str, recent_texts: list[str]
    ) -> tuple[str, bool]:
        """Detect register shift from conversation baseline to pet-talk.

        Returns (shift_label, pet_register_detected).
        """
        # Check for pet-register vocabulary
        pet_detected = any(p in text for p in PET_REGISTER)

        if not recent_texts:
            return ("none", pet_detected)

        # Average word length as register proxy
        words = text.split()
        if not words:
            return ("none", pet_detected)
        curr_avg = sum(len(w) for w in words) / len(words)

        # Baseline from recent turns
        all_recent_words = []
        for t in recent_texts[-5:]:
            all_recent_words.extend(t.lower().split())
        if not all_recent_words:
            return ("none", pet_detected)
        baseline_avg = sum(len(w) for w in all_recent_words) / len(all_recent_words)

        delta = baseline_avg - curr_avg  # positive = current text has shorter words

        if delta > 2.0 and pet_detected:
            shift = "extreme"
        elif delta > 1.5 or (delta > 0.5 and pet_detected):
            shift = "significant"
        elif delta > 0.8:
            shift = "mild"
        else:
            shift = "none"

        return (shift, pet_detected)

    # ── Signal 4: Physical Action Commands ─────────────────────────────

    @staticmethod
    def _detect_physical_action(text: str) -> bool:
        """Detect physical action commands (pet/child directed).

        CRITICAL GATE: Only fires for short utterances (<=4 words).
        Words like 'come', 'down', 'stay', 'fetch' appear constantly in
        normal conversation. Real pet commands are terse imperatives.
        """
        words = text.split()
        if len(words) > 4:
            return False

        # Check single words and bigrams
        word_set = set(words)
        if word_set & {w for w in PHYSICAL_ACTIONS if " " not in w}:
            return True

        # Check multi-word actions
        for action in PHYSICAL_ACTIONS:
            if " " in action and action in text:
                return True

        return False

    # ── Composite Score ────────────────────────────────────────────────

    @staticmethod
    def _compute_composite(
        greeting: bool,
        topic_cont: float,
        register: str,
        pet_register_detected: bool,
        physical_action: bool,
        entity_match: bool,
        entity_label: str,
    ) -> tuple[float, list[str]]:
        """Compute weighted composite not-for-me evidence score.

        Weights:
        - Greeting anomaly: 0.40 (strongest single signal)
        - Topic discontinuity: 0.20 (only when < 0.15 Jaccard)
        - Register shift: 0.15 + pet_register: 0.10
        - Physical action: 0.15
        - Known entity: 0.10
        """
        score = 0.0
        reasons = []

        # Signal 1: Greeting mid-conversation (0.40)
        if greeting:
            score += 0.40
            reasons.append("greeting_mid_conversation")

        # Signal 2: Topic discontinuity (0.20, only on severe breaks)
        if topic_cont < 0.15:
            topic_break = 1.0 - topic_cont
            score += 0.20 * topic_break
            reasons.append("zero_topic_overlap")

        # Signal 3: Register shift (0.15) + pet register (0.10)
        if register in ("significant", "extreme"):
            score += 0.15
            reasons.append(f"register_shift:{register}")
        if pet_register_detected:
            score += 0.10
            reasons.append("pet_register_vocabulary")

        # Signal 4: Physical action command (0.15)
        if physical_action:
            score += 0.15
            reasons.append("physical_action_command")

        # Signal 5: Known entity match (0.10)
        if entity_match:
            score += 0.10
            reasons.append(f"known_entity:{entity_label}")

        return (min(1.0, score), reasons)


# ── Helpers ────────────────────────────────────────────────────────────

def _content_words(text: str) -> set[str]:
    """Extract content words: >3 chars, not in stop words."""
    words = text.lower().split()
    return {
        w.strip(".,!?;:'\"")
        for w in words
        if len(w.strip(".,!?;:'\"")) > 3
        and w.strip(".,!?;:'\"") not in _STOP_WORDS
    }
