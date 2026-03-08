"""
Social Cues Meter — Quantified Relationship Dynamics

Tracks behavioral signals that indicate how the conversation is going at
both session level (resets on restart) and lifespan level (persists to disk).
Produces an effective boldness value that dynamically modulates the user's
static boldness setting based on engagement, rapport, frustration, and rhythm.

Design principles (from red-team review):
- Behavioral > Lexical: measure what people DO, not individual word meanings
- VADER gets 49.8% accuracy on spoken language — word-list sentiment is demoted
  to a weak supporting signal (5% weight, 8+ words only)
- Response latency dropped — can't measure accurately from Ears pipeline
  (TTS network jitter dominates the measurement)
- Rapport uses sigmoid acceleration (Peterson's winner effect), not linear
- Signal coherence: when meters disagree, report conflict instead of averaging

Research grounding:
- Stivers et al. (2009): Universal turn-taking timing (~200ms modal gap)
- Tickle-Degnen & Rosenthal (1990): Rapport = attentiveness + positivity + coordination
- Huber et al. (1997): Serotonin reduces retreat decision (not aggression) — winner effect
- Gottman: criticism → contempt → defensiveness → stonewalling progression
- Seligman (1975): Learned helplessness after 2-3 successive failures
- Burgoon (1993): Expectation violation theory — consistency > brilliance
"""

import json
import math
import os
import time
import logging
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# ── Weak sentiment word lists (used only on 8+ word utterances) ──────────

POSITIVE_WORDS = frozenset({
    "great", "awesome", "perfect", "thanks", "thank", "love", "amazing",
    "excellent", "wonderful", "fantastic", "nice", "good", "cool", "sweet",
    "brilliant", "helpful", "appreciate", "impressive", "exactly", "yes",
    "beautiful", "enjoy", "happy", "glad", "pleased", "incredible",
    "outstanding", "superb", "terrific",
})

NEGATIVE_WORDS = frozenset({
    "wrong", "bad", "terrible", "horrible", "awful", "hate", "stupid",
    "useless", "broken", "annoying", "frustrated", "frustrating",
    "confused", "confusing", "disappointed", "disappointing", "slow",
    "worse", "worst", "ugly", "dumb", "ridiculous", "pathetic",
    "failed", "failing", "sucks", "boring", "irritating",
})

NEGATORS = frozenset({
    "not", "no", "never", "don't", "doesn't", "didn't", "isn't",
    "wasn't", "aren't", "won't", "can't", "couldn't", "shouldn't",
})

INTENSIFIERS = frozenset({
    "very", "really", "so", "extremely", "super", "incredibly", "absolutely",
})

# Profanity — context-sensitive (can be positive: "fuck yeah")
PROFANITY = frozenset({
    "fuck", "shit", "damn", "hell", "ass", "crap", "bullshit", "goddamn",
})

# Negation words for frustration detection (behavioral, not sentiment)
FRUSTRATION_NEGATIONS = frozenset({
    "no", "not", "don't", "doesn't", "didn't", "isn't", "wasn't",
    "can't", "won't", "couldn't", "shouldn't", "never", "none",
})

# Repetition markers
REPETITION_MARKERS = frozenset({
    "again", "already", "said", "told", "repeat", "repeating",
})


# ── Data structures ──────────────────────────────────────────────────────

@dataclass
class TurnRecord:
    """A single conversational turn with social metadata."""
    timestamp: float
    text: str
    speaker: str        # "user" or "agent"
    word_count: int
    was_question: bool
    was_correction: bool
    confidence: float   # Whisper avg_logprob (user turns only)
    time_since_last_agent: float  # seconds since agent last spoke


@dataclass
class SocialSnapshot:
    """Complete social cues reading for one scoring event."""
    # Individual meters
    engagement: float = 0.5
    engagement_label: str = "cold_start"
    rapport: float = 0.0
    rapport_label: str = "new"
    frustration: float = 0.0
    frustration_label: str = "calm"
    rhythm: float = 0.5
    rhythm_label: str = "natural"

    # Composite
    warmth: float = 0.0
    signal_conflict: bool = False

    # Effective boldness
    effective_boldness: int = 40
    effective_disposition: str = "somewhat_timid"
    disposition_blend: str = "somewhat_timid"

    # Lifespan context
    lifespan_sessions: int = 0
    competence_ratio: float = 0.0
    engagement_style: str = "unknown"
    rapport_baseline: float = 0.0


# ── Lifespan persistence ─────────────────────────────────────────────────

def _get_lifespan_path() -> Path:
    """Lifespan file lives in ~/Library/Application Support/molt-speak/."""
    support_dir = Path.home() / "Library" / "Application Support" / "molt-speak"
    support_dir.mkdir(parents=True, exist_ok=True)
    return support_dir / "social_cues_lifespan.json"


_LIFESPAN_DEFAULT = {
    "version": 1,
    "updated_at": "",
    "total_sessions": 0,
    "total_exchanges": 0,
    "total_corrections": 0,
    "rapport_baseline": 0.0,
    "competence_ratio": 0.0,
    "engagement_style": {
        "avg_turn_length": 0.0,
        "question_frequency": 0.0,
        "style_label": "unknown",
    },
    "session_summaries": [],
}


# ── Main class ────────────────────────────────────────────────────────────

class SocialCuesMeter:
    """
    Tracks behavioral social dynamics over a session and across the agent's
    lifespan.  Produces an effective boldness value that dynamically modulates
    the user's static boldness setting.

    Call score_user_turn() after each user utterance passes the input filter.
    Call record_agent_turn() / record_agent_silence() when the agent responds
    or stays silent.  Call end_session() on shutdown to persist lifespan data.
    """

    def __init__(self):
        # Session state
        self._session_start = time.time()
        self._turns: deque[TurnRecord] = deque(maxlen=50)
        self._correction_timestamps: list[float] = []
        self._successful_exchanges = 0
        self._failed_exchanges = 0
        self._session_rapport = 0.0
        self._last_agent_time = 0.0
        self._last_sentiment = 0.0
        self._last_sentiment_wc = 0
        self._ended = False  # guard against double end_session

        # Lifespan state
        self._lifespan = self._load_lifespan()

        # Seed session rapport from lifespan baseline (30% weight)
        baseline = self._lifespan.get("rapport_baseline", 0.0)
        self._session_rapport = 0.3 * baseline

        logger.info(f"SocialCuesMeter initialized (lifespan sessions: "
                     f"{self._lifespan.get('total_sessions', 0)}, "
                     f"rapport baseline: {baseline:.2f})")

    # ── Config polling ────────────────────────────────────────────────

    @staticmethod
    def _get_base_boldness() -> int:
        """Read current boldness from ConfigManager (sub-ms JSON read)."""
        try:
            import sys
            from pathlib import Path as _P
            config_dir = _P(__file__).parent.parent.parent.parent / "src" / "config"
            if str(config_dir) not in sys.path:
                sys.path.insert(0, str(config_dir))
            from config_manager import ConfigManager
            return ConfigManager().agent_boldness
        except Exception:
            return 40

    # ── Lifespan I/O ──────────────────────────────────────────────────

    @staticmethod
    def _load_lifespan() -> dict:
        path = _get_lifespan_path()
        if path.exists():
            try:
                data = json.loads(path.read_text())
                # Ensure all keys present
                for k, v in _LIFESPAN_DEFAULT.items():
                    if k not in data:
                        data[k] = v
                return data
            except (json.JSONDecodeError, OSError):
                pass
        return _LIFESPAN_DEFAULT.copy()

    def _save_lifespan(self) -> None:
        path = _get_lifespan_path()
        try:
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._lifespan, indent=2))
            tmp.replace(path)  # atomic on POSIX
        except OSError as e:
            logger.warning(f"Failed to save lifespan: {e}")

    # ── Event recording ───────────────────────────────────────────────

    def score_user_turn(
        self,
        text: str,
        confidence: Optional[float] = None,
        is_correction: bool = False,
        is_barge_in: bool = False,
    ) -> SocialSnapshot:
        """Score a user utterance and return full social snapshot."""
        now = time.time()
        words = text.lower().split()
        word_count = len(words)
        was_question = text.strip().endswith("?")
        time_since_agent = (now - self._last_agent_time) if self._last_agent_time else 0.0

        turn = TurnRecord(
            timestamp=now,
            text=text,
            speaker="user",
            word_count=word_count,
            was_question=was_question,
            was_correction=is_correction,
            confidence=confidence if confidence is not None else -0.5,
            time_since_last_agent=time_since_agent,
        )
        self._turns.append(turn)

        # Track corrections
        if is_correction:
            self._correction_timestamps.append(now)

        # Update rapport
        self._update_rapport_for_agent_outcome()

        # Compute all meters
        engagement, eng_label = self._compute_engagement()
        self._update_session_rapport(is_correction)
        rapport, rap_label = self._get_rapport()
        frustration, frust_label = self._compute_frustration()
        rhythm, rhy_label = self._compute_rhythm()

        # Weak sentiment (only on 8+ words)
        if word_count >= 8:
            self._last_sentiment = self._compute_sentiment(words)
            self._last_sentiment_wc = word_count

        # Composite warmth
        warmth = self._compute_warmth(engagement, rapport, rhythm, frustration)

        # Signal conflict detection
        signal_conflict = (engagement > 0.6 and frustration > 0.5)

        # Effective boldness
        base = self._get_base_boldness()
        eff_bold = self._compute_effective_boldness(base, warmth, frustration)
        eff_disp = self._boldness_to_disposition(eff_bold)
        blend = self._disposition_blend(eff_bold)

        return SocialSnapshot(
            engagement=engagement,
            engagement_label=eng_label,
            rapport=rapport,
            rapport_label=rap_label,
            frustration=frustration,
            frustration_label=frust_label,
            rhythm=rhythm,
            rhythm_label=rhy_label,
            warmth=warmth,
            signal_conflict=signal_conflict,
            effective_boldness=eff_bold,
            effective_disposition=eff_disp,
            disposition_blend=blend,
            lifespan_sessions=self._lifespan.get("total_sessions", 0),
            competence_ratio=self._lifespan.get("competence_ratio", 0.0),
            engagement_style=self._lifespan.get("engagement_style", {}).get(
                "style_label", "unknown"),
            rapport_baseline=self._lifespan.get("rapport_baseline", 0.0),
        )

    def record_agent_turn(self, text: str = "") -> None:
        """Record that the agent produced a spoken response."""
        now = time.time()
        self._last_agent_time = now
        self._turns.append(TurnRecord(
            timestamp=now, text=text, speaker="agent",
            word_count=len(text.split()) if text else 0,
            was_question=text.strip().endswith("?") if text else False,
            was_correction=False, confidence=0.0, time_since_last_agent=0.0,
        ))
        self._successful_exchanges += 1

    def record_agent_silence(self) -> None:
        """Record that the agent stayed silent (timed out without responding)."""
        # Silence after user speech is a mild negative — agent missed an opportunity
        # or correctly stayed silent (can't tell which from here)
        pass  # Don't penalize — silence may be correct. Only corrections penalize.

    def get_snapshot(self) -> SocialSnapshot:
        """Return the most recent social snapshot without re-scoring."""
        # Re-compute from current state (lightweight)
        user_turns = [t for t in self._turns if t.speaker == "user"]
        if not user_turns:
            snap = SocialSnapshot()
            snap.effective_boldness = self._get_base_boldness()
            snap.lifespan_sessions = self._lifespan.get("total_sessions", 0)
            snap.competence_ratio = self._lifespan.get("competence_ratio", 0.0)
            snap.engagement_style = self._lifespan.get("engagement_style", {}).get(
                "style_label", "unknown")
            snap.rapport_baseline = self._lifespan.get("rapport_baseline", 0.0)
            return snap

        engagement, eng_label = self._compute_engagement()
        rapport, rap_label = self._get_rapport()
        frustration, frust_label = self._compute_frustration()
        rhythm, rhy_label = self._compute_rhythm()
        warmth = self._compute_warmth(engagement, rapport, rhythm, frustration)
        signal_conflict = (engagement > 0.6 and frustration > 0.5)
        base = self._get_base_boldness()
        eff_bold = self._compute_effective_boldness(base, warmth, frustration)

        return SocialSnapshot(
            engagement=engagement, engagement_label=eng_label,
            rapport=rapport, rapport_label=rap_label,
            frustration=frustration, frustration_label=frust_label,
            rhythm=rhythm, rhythm_label=rhy_label,
            warmth=warmth, signal_conflict=signal_conflict,
            effective_boldness=eff_bold,
            effective_disposition=self._boldness_to_disposition(eff_bold),
            disposition_blend=self._disposition_blend(eff_bold),
            lifespan_sessions=self._lifespan.get("total_sessions", 0),
            competence_ratio=self._lifespan.get("competence_ratio", 0.0),
            engagement_style=self._lifespan.get("engagement_style", {}).get(
                "style_label", "unknown"),
            rapport_baseline=self._lifespan.get("rapport_baseline", 0.0),
        )

    def get_recent_user_texts(self, n: int = 5) -> list[str]:
        """Return the text of the last N user turns (for pragmatic analysis)."""
        user_turns = [t for t in self._turns if t.speaker == "user"]
        return [t.text for t in user_turns[-n:]]

    # ── Meter computations ────────────────────────────────────────────

    def _compute_engagement(self) -> tuple[float, str]:
        """Engagement trajectory via linear regression over user turn proxies."""
        user_turns = [t for t in self._turns if t.speaker == "user"]
        if len(user_turns) < 2:
            return 0.5, "cold_start"

        recent = list(user_turns)[-10:]
        proxies = []
        for t in recent:
            wc_norm = min(1.0, t.word_count / 30.0)
            q_score = 1.0 if t.was_question else 0.0
            # Inverse gap: faster return = more eager (cap at 60s)
            gap_score = max(0.0, 1.0 - t.time_since_last_agent / 60.0) \
                if t.time_since_last_agent > 0 else 0.5
            # ASR confidence: -0.3 = excellent, -1.0 = poor
            conf_score = max(0.0, min(1.0, (t.confidence + 1.0)))
            proxy = 0.35 * wc_norm + 0.30 * q_score + 0.20 * gap_score + 0.15 * conf_score
            proxies.append(proxy)

        n = len(proxies)
        if n < 2:
            return 0.5, "cold_start"

        # Simple least-squares linear regression (no numpy)
        x_mean = (n - 1) / 2.0
        y_mean = sum(proxies) / n
        num = sum((i - x_mean) * (proxies[i] - y_mean) for i in range(n))
        den = sum((i - x_mean) ** 2 for i in range(n))
        slope = num / den if den != 0 else 0.0

        # Map slope to 0-1 (slope of ±0.1 → full range)
        trajectory = max(0.0, min(1.0, 0.5 + slope * 5.0))

        if trajectory > 0.65:
            return trajectory, "warming"
        elif trajectory > 0.4:
            return trajectory, "steady"
        else:
            return trajectory, "cooling"

    def _update_session_rapport(self, is_correction: bool) -> None:
        """Update rapport with sigmoid acceleration (Peterson's winner effect)."""
        if is_correction:
            # Flat crash: -0.20 regardless of current level
            self._session_rapport = max(0.0, self._session_rapport - 0.20)
            self._failed_exchanges += 1
        else:
            # Sigmoid-shaped increment: faster gains as rapport grows
            # At 0.0: +0.04, at 0.35: +0.07, at 0.6+: +0.10
            sigmoid = 1.0 / (1.0 + math.exp(-8.0 * (self._session_rapport - 0.35)))
            increment = 0.04 + 0.06 * sigmoid
            self._session_rapport = min(1.0, self._session_rapport + increment)

    def _update_rapport_for_agent_outcome(self) -> None:
        """Check if the last user turn was a correction and adjust."""
        # Handled inline in score_user_turn via _update_session_rapport
        pass

    def _get_rapport(self) -> tuple[float, str]:
        """Combine session rapport (70%) with lifespan baseline (30%)."""
        baseline = self._lifespan.get("rapport_baseline", 0.0)
        combined = 0.7 * self._session_rapport + 0.3 * baseline

        if combined > 0.65:
            return combined, "strong"
        elif combined > 0.4:
            return combined, "established"
        elif combined > 0.15:
            return combined, "building"
        else:
            return combined, "new"

    def _compute_frustration(self) -> tuple[float, str]:
        """Frustration from behavioral signals (not word-list sentiment)."""
        now = time.time()
        user_turns = [t for t in self._turns if t.speaker == "user"]

        # 1. Correction frequency in last 3 minutes (50% weight)
        recent_corrections = [t for t in self._correction_timestamps if now - t < 180]
        correction_score = min(1.0, len(recent_corrections) * 0.25)

        # 2. Brevity spike: recent 2 turns much shorter than prior 2 (25% weight)
        brevity_score = 0.0
        if len(user_turns) >= 4:
            recent_wc = sum(t.word_count for t in list(user_turns)[-2:]) / 2
            earlier_wc = sum(t.word_count for t in list(user_turns)[-4:-2]) / 2
            if earlier_wc > 3:
                ratio = recent_wc / earlier_wc
                if ratio < 0.5:
                    brevity_score = min(1.0, (1.0 - ratio) * 1.5)

        # 3. Repetition + negation density in recent 3 turns (25% weight)
        neg_rep_score = 0.0
        recent_user = list(user_turns)[-3:]
        if recent_user:
            total_words = 0
            negation_count = 0
            repetition_count = 0
            for t in recent_user:
                words = set(t.text.lower().split())
                total_words += len(words)
                negation_count += len(words & FRUSTRATION_NEGATIONS)
                repetition_count += len(words & REPETITION_MARKERS)
            if total_words > 0:
                neg_density = negation_count / total_words
                rep_density = repetition_count / total_words
                neg_rep_score = min(1.0, neg_density * 4.0 + rep_density * 6.0)

        frustration = (0.50 * correction_score
                       + 0.25 * brevity_score
                       + 0.25 * neg_rep_score)
        frustration = max(0.0, min(1.0, frustration))

        if frustration > 0.8:
            return frustration, "critical"
        elif frustration > 0.5:
            return frustration, "significant"
        elif frustration > 0.2:
            return frustration, "mild"
        else:
            return frustration, "calm"

    def _compute_rhythm(self) -> tuple[float, str]:
        """Interaction rhythm from turn-length consistency and balance."""
        user_turns = [t for t in self._turns if t.speaker == "user"]
        agent_turns = [t for t in self._turns if t.speaker == "agent"]

        if len(user_turns) < 3:
            return 0.5, "natural"

        # 1. Turn-length consistency: coefficient of variation (60% weight)
        word_counts = [t.word_count for t in list(user_turns)[-10:]]
        mean_wc = sum(word_counts) / len(word_counts)
        if mean_wc > 0:
            variance = sum((wc - mean_wc) ** 2 for wc in word_counts) / len(word_counts)
            cv = (variance ** 0.5) / mean_wc
            consistency = max(0.0, 1.0 - cv)
        else:
            consistency = 0.5

        # 2. Turn-taking balance: user turns / total turns (40% weight)
        total = len(user_turns) + len(agent_turns)
        if total > 2:
            balance_ratio = len(user_turns) / total
            balance = 1.0 - abs(balance_ratio - 0.5) * 2.0
        else:
            balance = 0.5

        rhythm = 0.60 * consistency + 0.40 * balance

        if rhythm > 0.7:
            return rhythm, "natural"
        elif rhythm > 0.5:
            return rhythm, "hesitant"
        elif rhythm > 0.3:
            return rhythm, "rushed"
        else:
            return rhythm, "disengaged"

    def _compute_sentiment(self, words: list[str]) -> float:
        """Weak sentiment from word lists. Only meaningful on 8+ word utterances."""
        if not words:
            return 0.0

        clean = [w.strip(".,!?;:'\"") for w in words]
        score = 0.0
        intensity = 1.0
        negate = False

        for word in clean:
            if word in NEGATORS:
                negate = True
                continue
            if word in INTENSIFIERS:
                intensity = 1.5
                continue
            if word in POSITIVE_WORDS:
                score += 0.3 * intensity * (-1 if negate else 1)
            elif word in NEGATIVE_WORDS:
                score -= 0.3 * intensity * (-1 if negate else 1)
            negate = False
            intensity = 1.0

        normalized = score / max(1.0, len(clean) ** 0.5)
        sentiment = max(-1.0, min(1.0, normalized))

        # Profanity context check
        if any(w.strip(".,!?;:'\"") in PROFANITY for w in words):
            if any(w.strip(".,!?;:'\"") in POSITIVE_WORDS for w in words):
                sentiment = max(sentiment, 0.3)
            else:
                sentiment = min(sentiment, -0.3)

        return sentiment

    def _compute_warmth(self, engagement: float, rapport: float,
                        rhythm: float, frustration: float) -> float:
        """Weighted composite of behavioral meters."""
        warmth = (0.35 * rapport + 0.30 * engagement + 0.20 * rhythm) \
                 - (0.15 * frustration)

        # Weak sentiment nudge (only when we have a meaningful reading)
        if abs(self._last_sentiment) > 0.4 and self._last_sentiment_wc >= 8:
            warmth += 0.05 * self._last_sentiment

        return max(0.0, min(1.0, warmth))

    # ── Effective boldness ────────────────────────────────────────────

    @staticmethod
    def _compute_effective_boldness(base: int, warmth: float,
                                     frustration: float) -> int:
        """Modulate static boldness based on social warmth and frustration.

        Wider swing than v1: warmth can push +25, frustration can pull -30.
        Headroom scaling prevents runaway at extremes.
        """
        headroom_up = (100 - base) / 100.0
        headroom_down = base / 100.0
        warmth_boost = warmth * 25.0 * headroom_up
        frustration_penalty = frustration * 30.0 * headroom_down
        effective = base + warmth_boost - frustration_penalty
        return max(1, min(100, round(effective)))

    @staticmethod
    def _boldness_to_disposition(boldness: int) -> str:
        if boldness <= 15:
            return "very_timid"
        elif boldness <= 35:
            return "timid"
        elif boldness <= 50:
            return "somewhat_timid"
        elif boldness <= 70:
            return "balanced"
        else:
            return "bold"

    @staticmethod
    def _disposition_blend(boldness: int) -> str:
        """Human-readable gradient label (e.g., 'somewhat_timid leaning balanced')."""
        disp = SocialCuesMeter._boldness_to_disposition(boldness)
        # Check proximity to boundaries
        boundaries = [
            (15, "very_timid", "timid"),
            (35, "timid", "somewhat_timid"),
            (50, "somewhat_timid", "balanced"),
            (70, "balanced", "bold"),
        ]
        for threshold, below, above in boundaries:
            distance = abs(boldness - threshold)
            if distance <= 8:
                if boldness < threshold:
                    return f"{below} leaning {above}"
                else:
                    return f"{above} leaning {below}"
        return disp

    # ── Session end / lifespan persistence ────────────────────────────

    def end_session(self) -> None:
        """Persist session data to lifespan store. Called on shutdown."""
        if self._ended:
            return
        self._ended = True

        session_duration = time.time() - self._session_start
        total_exchanges = self._successful_exchanges + self._failed_exchanges

        # Skip micro-sessions
        if session_duration < 30 and total_exchanges == 0:
            logger.info("Micro-session — skipping lifespan update")
            return

        ls = self._lifespan
        ls["total_sessions"] = ls.get("total_sessions", 0) + 1
        ls["total_exchanges"] = ls.get("total_exchanges", 0) + total_exchanges
        ls["total_corrections"] = ls.get("total_corrections", 0) + len(self._correction_timestamps)

        # Asymmetric EMA for rapport baseline
        old_baseline = ls.get("rapport_baseline", 0.0)
        if self._session_rapport > old_baseline:
            alpha = 0.2  # slow build
        else:
            alpha = 0.4  # fast crash
        ls["rapport_baseline"] = (1 - alpha) * old_baseline + alpha * self._session_rapport

        # Competence ratio
        total_all = ls.get("total_exchanges", 0)
        total_corrections = ls.get("total_corrections", 0)
        if total_all > 0:
            ls["competence_ratio"] = max(0.0, (total_all - total_corrections) / total_all)

        # Engagement style (EMA)
        user_turns = [t for t in self._turns if t.speaker == "user"]
        if user_turns:
            avg_wc = sum(t.word_count for t in user_turns) / len(user_turns)
            q_freq = sum(1 for t in user_turns if t.was_question) / len(user_turns)

            es = ls.get("engagement_style", _LIFESPAN_DEFAULT["engagement_style"].copy())
            es["avg_turn_length"] = 0.7 * es.get("avg_turn_length", avg_wc) + 0.3 * avg_wc
            es["question_frequency"] = 0.7 * es.get("question_frequency", q_freq) + 0.3 * q_freq

            if es["avg_turn_length"] > 15 and es["question_frequency"] > 0.3:
                es["style_label"] = "enthusiastic"
            elif es["avg_turn_length"] > 8 or es["question_frequency"] > 0.2:
                es["style_label"] = "engaged"
            else:
                es["style_label"] = "reserved"
            ls["engagement_style"] = es

        # Session summary (keep last 20)
        from datetime import datetime
        summary = {
            "date": datetime.now().isoformat(),
            "duration_seconds": round(session_duration),
            "exchanges": total_exchanges,
            "corrections": len(self._correction_timestamps),
            "end_rapport": round(self._session_rapport, 3),
        }
        summaries = ls.get("session_summaries", [])
        summaries.append(summary)
        ls["session_summaries"] = summaries[-20:]
        ls["updated_at"] = datetime.now().isoformat()

        self._save_lifespan()
        logger.info(f"Lifespan saved: {ls['total_sessions']} sessions, "
                     f"rapport baseline {ls['rapport_baseline']:.2f}, "
                     f"competence {ls.get('competence_ratio', 0):.2f}")
