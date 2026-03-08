"""
Conversation Temperature Scoring Engine

Computes a 0.0-1.0 score indicating how "hot" the conversation is,
which calibrates the agent's threshold for responding vs staying silent.

Based on research from:
- Apple DDSD (2024): 20-40% improvement modeling conversation context
- Amazon Science: ASR decoder features alone achieve ~9% error rate
- Frontiers 2022 review (23 studies): composite signals outperform any single feature
- Prosodic research: device-directed speech is hyper-articulated → higher ASR confidence

v2 tuning notes (from live testing):
- Temporal decay extended to 30s hot window (TTS delivery takes 20-60s)
- Dialog state weight increased (0.20 → 0.30) — exchange momentum matters most
- Barge-in treated as strong engagement signal (+0.15 bonus)
- Conversation floor prevents active exchanges from reading "cool"
- ASR weight reduced (0.20 → 0.15) — least reliable signal in practice

v3 tuning notes (from live testing):
- Three-tier closing signal detection (terminal, departure, gratitude)
- Closing signals override momentum floor and barge-in bonus
- Based on Schegloff & Sacks (1973) closing sequence structure,
  Amazon/Google built-in exit intents, SWBD-DAMSL fc tag patterns
- Asymmetric design: cool-down is instant, warm-up is gradual
  (Harvard 2021: only 2% of conversations end when both parties want)

v4 tuning notes (temporal cool-down fix):
- Temporal decay switched from piecewise-linear to exponential (math.exp)
- Grace period reduced from 30s to 15s (TTS delivery is faster with streaming)
- Half-life varies by exchange depth: 20s (short), 30s (medium), 40s (deep)
- Momentum floor now decays with temporal score — silence always wins
- Dialog state score multiplied by temporal — no time-independent warmth
- After ~2 minutes of silence, temperature is effectively cold regardless of history

v5 tuning notes (anti-timidity — research-backed):
- ASR weight boosted 0.15 → 0.25 (Amazon DDSD: strongest single signal at 9.3% EER)
- Temporal weight reduced 0.30 → 0.20 (content signals matter more than recency)
- Momentum floors raised: 0.65/0.55/0.45 (software avatar approach: active session = presume directed)
- Third-tier momentum guard loosened: temporal > 0.15 (was 0.30)
- Label thresholds lowered: hot 0.70 (was 0.80), warm 0.40 (was 0.50), cool 0.15 (was 0.20)
- Asymmetric error cost: false rejection 2-3x worse than false acceptance (PwC, CHI 2023)
- Based on: Amazon DDSD, Apple DDSD with LLMs, Google dynamic threshold patent,
  Frontiers 2022 systematic review (23 studies), Soul Machines/Character.ai session model
"""

import math
import re
import time
import logging
from dataclasses import dataclass
from typing import Optional
from collections import deque

logger = logging.getLogger(__name__)


@dataclass
class TemperatureReading:
    """Result of a conversation temperature evaluation."""
    score: float          # 0.0-1.0
    label: str            # hot / warm / cool / cold
    key_signal: str       # Most influential factor for this reading
    components: dict      # Individual signal scores for debugging
    recent_correction: bool = False  # User corrected agent recently
    exchange_count: int = 0          # Completed exchanges — needed by PragmaticAnalyzer
    correction_just_fired: bool = False  # True only on the turn that matched a correction


@dataclass
class ConversationTurn:
    """A single turn in the conversation history."""
    timestamp: float
    text: str
    speaker: str          # "user" or "agent"


# Discourse markers that signal continuation of directed speech
CONTINUATION_MARKERS = {
    "also", "and", "actually", "plus", "another", "additionally",
    "wait", "hold on",
}

# Multi-word continuation markers (checked against first two words)
CONTINUATION_PAIRS = {
    "by the", "oh and", "one more",
}

# Discourse markers that signal NEW directed speech (cold → warm)
INITIATION_MARKERS = {
    "hey", "so", "alright", "listen",
}

INITIATION_PAIRS = {
    "okay so",
}

# Directive structures: imperative verbs, question words, 2nd person
DIRECTIVE_PATTERNS = re.compile(
    r'\b('
    r'can you|could you|would you|will you|'
    r'tell me|show me|give me|help me|let me|'
    r'what|when|where|why|how|who|which|'
    r'do you|are you|is there|have you|'
    r'set|play|open|close|turn|start|stop|find|search|'
    r'remind|schedule|create|delete|send|call|read'
    r')\b',
    re.IGNORECASE
)

# Disfluency markers (more = likely human-to-human, not device-directed)
DISFLUENCIES = {"um", "uh", "like", "you know", "i mean", "sort of", "kind of"}


# === CLOSING SIGNAL DETECTION ===
# Based on Schegloff & Sacks (1973) closing sequence structure,
# Amazon/Google built-in exit intents, and SWBD-DAMSL fc tag patterns.
#
# Asymmetric by design: a single closing signal instantly overrides
# momentum built over many exchanges. Research backing:
# - Harvard (Mastroianni 2021): only 2% of conversations end when
#   both parties want — people chronically overstay
# - Hysteresis principle: exiting a state requires less energy than entering

# Tier 1: Terminal farewells — conversation IS over
# Hard override to ~0.05 (cold). Reset all momentum.
TERMINAL_CLOSINGS = re.compile(
    r'^\s*'
    r'('
    r'bye\b|goodbye|good\s*bye|good\s*night|see\s*(you|ya)|later\b|night\b'
    r'|farewell|ciao|adios|peace(\s*out)?|take\s*care'
    r'|bye\s*bye|buh\s*bye'
    r'|(alright|all\s*right|okay|ok)\s*[,.]?\s*(bye|goodbye|good\s*night|see\s*(you|ya)|later|night|take\s*care)'
    r'|(thanks|thank\s*you)\s*[,.]?\s*(bye|goodbye)'
    r')'
    r'\s*[.!]?\s*$',
    re.IGNORECASE
)

# Tier 2: Departure announcements + session termination — user is leaving
# Override to ~0.20 (cool). Reset momentum.
DEPARTURE_CLOSINGS = re.compile(
    r'('
    r"i('ve| have)?\s*(gotta|got to|have to|need to|should)\s*(go|run|head out|leave|get going|bounce|jet|dip)"
    r"|i('m| am)\s*(out|leaving|heading out|off|done|finished)"
    r"|we('re| are)\s*(done|finished|good|all set|stopping)"
    r"|that('s| is)\s*(all|it|everything)\b"
    r"|nothing\s*(else|more)\b"
    r"|no\s*more\s*questions"
    r"|i('m| am)\s*good\b"
    r"|let('s| us)\s*stop"
    r')',
    re.IGNORECASE
)

# Tier 3: Gratitude closings — "thanks" as conversation-ender
# Standalone thanks or thanks + assessment. Multiply score by 0.35.
# Context-sensitive: only treated as closing when exchange_count >= 2.
GRATITUDE_CLOSINGS = re.compile(
    r'^\s*'
    r'('
    r'(thanks|thank\s*you|thx|appreciate\s*(it|that|this)|much\s*appreciated)'
    r'(\s*(a lot|so much|very much|for\s+(your|the|that|this)\s+help|for everything))?'
    r'[.!]?'
    r')'
    r'\s*$',
    re.IGNORECASE
)

# Correction signals — user telling agent it shouldn't have responded.
# NOT a closing signal (conversation continues). Sets recent_correction flag.
# Triggers per-disposition behavioral adjustment (see AGENT_INSTRUCTIONS.txt).
CORRECTION_SIGNALS = re.compile(
    r'('
    r"not\s+(you|for you)"
    r"|wasn('|o)t\s+talk(ing)?\s+(to|at)\s+you"
    r"|i\s+wasn('|o)t\s+(talking|speaking)\s+to\s+you"
    r"|didn('|o)t\s+(mean|ask)\s+you"
    r"|i('m| am)\s+not\s+talk(ing)?\s+to\s+you"
    r"|shut\s*up"
    r"|be\s+quiet"
    r"|stop\s+(talking|listening|it)"
    r"|not\s+now"
    r"|go\s+away"
    r"|leave\s+me\s+alone"
    r")",
    re.IGNORECASE
)


class ConversationTemperature:
    """
    Scores conversation temperature from 0.0 (cold) to 1.0 (hot).

    Fed by four signal categories:
    1. Temporal proximity - how recently did the last exchange happen?
    2. Lexical directedness - does this text look like directed speech?
    3. ASR quality - Whisper confidence as proxy for device-directedness
    4. Dialog state - is the agent expecting a response? Active thread?

    Plus barge-in as a direct engagement signal, conversation momentum
    floor to prevent active exchanges from reading "cool," and three-tier
    closing signal detection that overrides momentum when the user is
    ending the conversation.
    """

    def __init__(self, history_size: int = 10, boldness: int = 40):
        self._history: deque[ConversationTurn] = deque(maxlen=history_size)
        self._agent_asked_question = False
        self._last_agent_response_time = 0.0
        self._exchange_count = 0
        # Disposition perturbation factors — centered at 40 (default = zero change)
        # Based on Gray's BIS/BAS and Kagan's threshold model
        self._score_bias = (boldness - 40) / 250
        self._momentum_mult = 0.6 + boldness / 100
        self._halflife_mult = 1.0 + (boldness - 40) / 100
        # Correction tracking — mechanical rejection prophecy prevention
        self._last_correction_time = 0.0
        self._exchanges_since_correction = 0

    def score(
        self,
        text: str,
        confidence: Optional[float] = None,
        no_speech_prob: Optional[float] = None,
        compression_ratio: Optional[float] = None,
        is_barge_in: bool = False,
    ) -> TemperatureReading:
        """Compute conversation temperature for a user utterance."""
        now = time.time()

        temporal = self._score_temporal(now)
        lexical = self._score_lexical(text)
        asr = self._score_asr(confidence, no_speech_prob, compression_ratio)
        dialog = self._score_dialog_state(temporal)

        # Cold start: temporal and dialog are both 0.0 (no history), so 60%
        # of the weighted sum is dead weight. Redistribute to content signals
        # so clearly directed speech can score warm/hot on first contact.
        if self._exchange_count == 0 and self._last_agent_response_time == 0:
            raw = (
                0.60 * lexical
                + 0.40 * asr
            )
        else:
            # Weights: ASR boosted (strongest single signal per Amazon DDSD),
            # temporal reduced (still important but shouldn't dominate)
            raw = (
                0.20 * temporal
                + 0.25 * lexical
                + 0.25 * asr
                + 0.30 * dialog
            )

        # --- Closing signal detection (overrides momentum) ---
        closing = self._detect_closing(text)

        if closing != 'none':
            # Closing signals override momentum and barge-in.
            # Asymmetric by design: one closing signal instantly overrides
            # momentum built over many exchanges.
            if closing == 'terminal':
                raw = 0.05                    # Hard kill → cold
                self._exchange_count = 0      # Full reset
                self._agent_asked_question = False
            elif closing == 'departure':
                raw = 0.08                    # Hard kill → cold (not cool!)
                self._exchange_count = 0      # Full reset
                self._agent_asked_question = False
            elif closing == 'gratitude':
                raw *= 0.35                   # Strong reduction
                self._exchange_count = max(0, self._exchange_count - 3)
        else:
            # Normal flow: apply engagement bonuses
            if is_barge_in:
                raw += 0.15
                if self._exchange_count == 0:
                    self._exchange_count = 1

            # Conversation momentum floor: active session biases toward responding
            # v6: reduced floors + higher temporal gate so stale convos cool fast
            # Floors scaled by boldness multiplier (Kagan's excitability threshold)
            if self._exchange_count >= 5 and temporal > 0.3:
                raw = max(raw, 0.55 * self._momentum_mult * temporal)
            elif self._exchange_count >= 3 and temporal > 0.3:
                raw = max(raw, 0.45 * self._momentum_mult * temporal)
            elif self._exchange_count >= 1 and temporal > 0.5:
                raw = max(raw, 0.35 * self._momentum_mult * temporal)

            # Disposition bias (Gray's BIS/BAS model) — applied last, after floors
            # Closing signals are immune: a "goodbye" is a "goodbye" regardless
            raw += self._score_bias

        score = max(0.0, min(1.0, raw))

        # Asymmetric error cost: false rejection (silence when addressed)
        # is 2-3x more damaging than false acceptance (responding to side talk).
        # Lower thresholds = agent responds more readily.
        if score >= 0.70:
            label = "hot"
        elif score >= 0.40:
            label = "warm"
        elif score >= 0.15:
            label = "cool"
        else:
            label = "cold"

        components = {
            "temporal": temporal,
            "lexical": lexical,
            "asr": asr,
            "dialog": dialog,
        }
        key_signal = max(components, key=components.get)

        # Override key_signal if closing detected
        if closing != 'none':
            key_signal = f"closing:{closing}"

        # Detect correction signals (false positive feedback from user)
        is_correction = self._detect_correction(text)
        if is_correction:
            self._last_correction_time = now
            self._exchanges_since_correction = 0

        self._history.append(ConversationTurn(now, text, "user"))

        reading = TemperatureReading(
            score=round(score, 2),
            label=label,
            key_signal=key_signal,
            components={k: round(v, 2) for k, v in components.items()},
            recent_correction=self.recent_correction,
            exchange_count=self._exchange_count,
            correction_just_fired=is_correction,
        )
        logger.info(f"Temperature: {reading.score} ({reading.label}) — {reading.components}")
        return reading

    def _detect_closing(self, text: str) -> str:
        """Detect conversation closing signals using tiered classification.

        Returns: 'terminal', 'departure', 'gratitude', or 'none'

        Terminal: regex-based (unambiguous farewells like bye, goodbye)
        Departure: context-scored — combines lexical signals, utterance
          brevity, and conversation state instead of rigid regex matching.
          Catches "that'll do", "we're done", "I'm finished" etc. without
          needing an exact pattern for every possible closing phrase.
        Gratitude: regex-based (standalone thanks after exchanges)
        """
        lower = text.lower().strip()

        if TERMINAL_CLOSINGS.match(lower):
            return 'terminal'

        # Context-scored departure detection
        if self._score_closing_intent(text) >= 0.7:
            return 'departure'

        # Gratitude is only a closing signal during active conversations
        if self._exchange_count >= 2 and GRATITUDE_CLOSINGS.match(lower):
            return 'gratitude'

        return 'none'

    def _score_closing_intent(self, text: str) -> float:
        """Score closing/departure intent from content + conversation context.

        Uses multiple lightweight signals rather than exact regex matches,
        so phrases like "that'll do", "we're good here", "I think we're set"
        are caught without needing a pattern for each one.
        """
        lower = text.lower().strip()
        words = [w.rstrip(".,!?") for w in lower.split()]
        if not words:
            return 0.0

        score = 0.0

        # Signal 1: Completion/satisfaction vocabulary
        _COMPLETION = {"done", "finished", "complete", "enough", "do", "good",
                       "fine", "set", "all", "perfect", "great", "works",
                       "sufficient", "wrap", "end", "stop"}
        if any(w in _COMPLETION for w in words):
            score += 0.15

        # Signal 2: Departure/leaving vocabulary
        _DEPARTURE = {"go", "going", "leave", "leaving", "out", "off",
                      "done", "finished", "stop", "stopping", "end"}
        if any(w in _DEPARTURE for w in words):
            score += 0.1

        # Signal 3: Brevity — closings are short. This is the strongest
        # differentiator from mid-conversation uses of the same words.
        # "We're done" (2 words) vs "I'm done with setup, let's move on" (9 words)
        if len(words) <= 4:
            score += 0.35
        elif len(words) <= 8:
            score += 0.1

        # Signal 4: No question mark — not asking for more
        if "?" not in text:
            score += 0.1

        # Signal 5: Conversation depth — closings happen after exchanges
        if self._exchange_count >= 2:
            score += 0.15
        elif self._exchange_count >= 1:
            score += 0.1

        # Signal 6: First-person + departure verb
        _FIRST_PERSON = {"i", "i'm", "we", "we're", "im"}
        if any(w in _FIRST_PERSON for w in words) and any(w in _DEPARTURE for w in words):
            score += 0.15

        # Signal 7: "That" + completion verb (that'll do, that's enough, etc.)
        # Skip leading discourse markers: "Okay, that'll do" → check from "that'll"
        _DISCOURSE_PREFIX = {"okay", "ok", "alright", "well", "so", "right"}
        check_idx = 0
        while check_idx < len(words) and words[check_idx] in _DISCOURSE_PREFIX:
            check_idx += 1
        if check_idx < len(words) and words[check_idx] in {"that", "that's", "that'll", "thats"}:
            rest = {w for w in words[check_idx + 1:]}
            if rest & {"do", "does", "work", "works", "enough", "all",
                       "it", "fine", "good", "will", "suffice"}:
                score += 0.3

        # Signal 8: Closure idioms — these appear WITHIN longer utterances
        # ("I think we'll leave it at that") where brevity signal fails.
        # Check the tail end of the utterance, not just the first word.
        if "leave it at that" in lower or "leave it there" in lower:
            score += 0.5
        elif "that'll do it" in lower or "that'll do" in lower or "that will do" in lower:
            score += 0.45
        elif "call it a day" in lower or "wrap it up" in lower:
            score += 0.4
        elif "leave it" in lower and any(w in _COMPLETION for w in words):
            score += 0.3

        # Signal 9: Compound closing — departure vocabulary + gratitude in same utterance
        # "Okay, that'll do it. Thank you." — each alone might score below threshold,
        # but together they're unambiguous.
        _GRATITUDE = {"thanks", "thank", "appreciate", "cheers"}
        has_gratitude = any(w in _GRATITUDE for w in words)
        has_completion = any(w in _COMPLETION for w in words)
        if has_gratitude and has_completion and self._exchange_count >= 1:
            score += 0.2

        return min(1.0, score)

    def _detect_correction(self, text: str) -> bool:
        """Detect user correction signals (false positive feedback)."""
        return bool(CORRECTION_SIGNALS.search(text))

    @property
    def recent_correction(self) -> bool:
        """Whether a correction happened recently (within 5 min and < 3 exchanges since)."""
        if self._last_correction_time == 0:
            return False
        age = time.time() - self._last_correction_time
        return age < 300 and self._exchanges_since_correction < 3

    def record_agent_response(self, text: str = "") -> None:
        """Call this when the agent produces a spoken response."""
        now = time.time()
        self._history.append(ConversationTurn(now, text, "agent"))
        self._last_agent_response_time = now
        self._exchange_count += 1
        # Track exchanges since last correction for auto-clearing
        if self._last_correction_time > 0:
            self._exchanges_since_correction += 1

        if text:
            # Check if agent asked a question (ends with ?)
            stripped = text.strip().rstrip('."\'')
            self._agent_asked_question = stripped.endswith("?")
        else:
            # No text available (common — Ears can't read Mouth's output).
            # In conversational mode, most good assistant responses end with
            # a question or offer. Assume True to maintain adjacency pair
            # tracking. This is a reasonable heuristic: if the agent responded
            # at all, it likely invited further interaction.
            self._agent_asked_question = True

    def record_agent_silence(self) -> None:
        """Call this when the agent stays silent (no response)."""
        self._agent_asked_question = False

    # --- Individual Signal Scorers ---

    def _score_temporal(self, now: float) -> float:
        """Score based on time since last exchange.

        Exponential decay after a short grace period. The grace period
        accounts for TTS delivery time (user can't reply while agent
        is speaking). Half-life varies by conversation depth: deeper
        conversations stay warm slightly longer, but silence always wins.

        Decay examples (5+ exchanges, half_life=40s):
          15s → 1.0,  55s → 0.5,  95s → 0.25,  135s → 0.125

        Short conversations (half_life=20s):
          15s → 1.0,  35s → 0.5,  55s → 0.25,  75s → 0.125
        """
        if self._last_agent_response_time == 0:
            recent_user = [t for t in self._history if t.speaker == "user"]
            if not recent_user:
                return 0.0
            elapsed = now - recent_user[-1].timestamp
        else:
            elapsed = now - self._last_agent_response_time

        # Grace period: user can't reply while TTS is delivering
        grace = 15.0
        if elapsed <= grace:
            return 1.0

        # Half-life varies by conversation depth
        # v6: shortened — after ~90s of silence, temp should be cold
        # Scaled by boldness half-life multiplier (social persistence)
        if self._exchange_count >= 5:
            half_life = 25.0 * self._halflife_mult
        elif self._exchange_count >= 3:
            half_life = 20.0 * self._halflife_mult
        else:
            half_life = 15.0 * self._halflife_mult

        t = elapsed - grace
        return math.exp(-0.693 * t / half_life)

    def _score_lexical(self, text: str) -> float:
        """Score based on text content - directive structure, discourse markers."""
        score = 0.0
        lower = text.lower().strip()
        words = lower.split()
        if not words:
            return 0.0

        # Directive patterns (questions, commands, 2nd person)
        if DIRECTIVE_PATTERNS.search(lower):
            score += 0.5

        # Question mark
        if text.strip().endswith("?"):
            score += 0.3

        # Continuation markers (signals active thread)
        first_word = words[0]
        first_two = " ".join(words[:2]) if len(words) >= 2 else ""
        if first_word in CONTINUATION_MARKERS or first_two in CONTINUATION_PAIRS:
            score += 0.3

        # Initiation markers (signals new directed speech)
        if first_word in INITIATION_MARKERS or first_two in INITIATION_PAIRS:
            score += 0.2

        # Disfluency penalty (more disfluencies = more likely human-to-human)
        # Reduced penalty during active conversations — natural speech has disfluencies
        disfluency_count = sum(1 for d in DISFLUENCIES if d in lower)
        if self._exchange_count == 0:
            # Cold start: full penalty
            if disfluency_count >= 2:
                score -= 0.3
            elif disfluency_count == 1:
                score -= 0.1
        else:
            # Active conversation: halved penalty
            if disfluency_count >= 2:
                score -= 0.15
            elif disfluency_count == 1:
                score -= 0.05

        # Short imperative (1-4 words, no disfluencies) = likely device-directed
        if len(words) <= 4 and disfluency_count == 0:
            score += 0.2

        return max(0.0, min(1.0, score))

    def _score_asr(
        self,
        confidence: Optional[float],
        no_speech_prob: Optional[float],
        compression_ratio: Optional[float],
    ) -> float:
        """Score based on Whisper quality metrics as proxy for device-directedness.

        Research: device-directed speech is hyper-articulated, producing higher
        ASR confidence. Amazon found ASR decoder features alone get ~9% error rate.
        """
        score = 0.5  # Neutral baseline when no metrics available

        if confidence is not None:
            # avg_logprob: closer to 0 = higher confidence
            if confidence > -0.3:
                score = 1.0
            elif confidence > -0.5:
                score = 0.8
            elif confidence > -0.7:
                score = 0.5
            else:
                score = 0.2

        if no_speech_prob is not None:
            if no_speech_prob > 0.3:
                score *= 0.5
            elif no_speech_prob > 0.1:
                score *= 0.8

        if compression_ratio is not None:
            if compression_ratio > 2.0:
                score *= 0.5

        return max(0.0, min(1.0, score))

    def _score_dialog_state(self, temporal: float = 1.0) -> float:
        """Score based on conversation state - adjacency pairs, exchange count.

        This is the primary momentum signal. After several exchanges, the
        conversation is clearly active and should stay warm. However, the
        dialog state now decays with temporal proximity — a stale dialog
        state (minutes of silence) should not keep the conversation warm.
        """
        score = 0.0

        # Agent asked a question → strong adjacency pair expectation
        if self._agent_asked_question:
            score += 0.7

        # Active exchange session (multiple back-and-forth turns)
        if self._exchange_count >= 5:
            score += 0.5
        elif self._exchange_count >= 3:
            score += 0.35
        elif self._exchange_count >= 1:
            score += 0.2

        # Recent agent response exists at all
        if self._last_agent_response_time > 0:
            score += 0.1

        # Dialog state decays with temporal proximity
        score *= temporal

        return max(0.0, min(1.0, score))
