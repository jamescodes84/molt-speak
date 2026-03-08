"""
Input Pre-Filter for OpenClaw Ears

Catches machine-level noise before it reaches the agent's brain.
Think of this as the cochlea — filtering out static before signal reaches the cortex.

Grounded in:
- Whisper ASR hallucination research (55.2% of non-speech audio → "so")
- Backchannel linguistics (Malinowski's phatic communion)
- Acoustic research on non-speech vocalizations
- Hyper-articulation research (device-directed speech → higher ASR confidence)
"""

import re
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class FilterResult:
    """Result of the input filter evaluation."""
    passed: bool
    reason: str


# Known Whisper hallucination phrases that appear when transcribing non-speech audio.
# Research shows these are artifacts from Whisper's training data (YouTube subtitles).
WHISPER_HALLUCINATIONS = [
    "thank you for watching",
    "thanks for watching",
    "thank you so much for watching",
    "thank you so much for listening",
    "thanks so much for watching",
    "subscribe",
    "like and subscribe",
    "please subscribe",
    "thank you for listening",
    "thanks for listening",
    "see you next time",
    "see you in the next video",
    "see you later",
    "we'll see you later",
    "bye bye",
    "the end",
    "music",
    "applause",
    "laughter",
    "silence",
    "subtitles by",
    "copyright",
    "all rights reserved",
    "you",  # Very common single-word hallucination
    "you're welcome",
    "hope you enjoyed",
    "hope this helps",
    "i hope you enjoyed",
    "in this video",
    "don't forget to",
    "link in the description",
    "comment below",
    "for the sake of",
    "and i'll see you",
    "please hit the",
    "if you enjoyed",
    "until next time",
]

# Substring anchors — if ANY of these appear anywhere in the transcription,
# it's almost certainly a Whisper hallucination from YouTube training data.
HALLUCINATION_ANCHORS = [
    "for watching",
    "for listening",
    "for your wish",
    "in the description",
    "next video",
    "hit the bell",
    "like and subscribe",
]

# Isolated backchannel tokens — phatic signals that maintain conversational flow
# without carrying information. Almost never directed at an AI when alone.
BACKCHANNELS = {
    "um", "uh", "hmm", "ah", "oh", "yeah", "yep", "yup", "nah", "nope",
    "uh-huh", "uh huh", "mhm", "mm-hmm", "mm hmm", "mmm",
    "huh", "hm", "wow", "whoa", "ooh", "oops", "ha", "haha",
    "hahaha", "okay", "ok", "right", "sure", "alright", "well",
    "so", "like", "anyway", "whatever", "seriously", "really",
    "no", "yes", "yea", "ya", "hey", "hi", "bye",
    "ugh", "argh", "jeez", "geez", "damn", "dammit", "shit",
    "god", "oh god", "oh my god", "oh no", "oh yes", "oh wow",
    "what", "wait", "stop", "go",
}

# Two-word backchannel/exclamation combos
BACKCHANNEL_PAIRS = {
    "oh no", "oh yes", "oh yeah", "oh wow", "oh my", "oh god",
    "oh man", "oh boy", "oh well", "oh okay", "oh right",
    "my god", "my goodness", "good lord",
    "no way", "for real", "come on", "let's go",
    "thank you", "thank god", "sounds good",
    "of course", "all right", "you know",
    "ha ha", "he he", "ho ho",
}


class InputFilter:
    """
    Pre-filter for transcribed text before it reaches the agent.

    This filter catches obvious machine-level noise:
    - Whisper hallucinations from non-speech audio
    - Isolated backchannel tokens (phatic signals)
    - Singing patterns (repetitive syllables)
    - Very low confidence transcriptions

    It does NOT attempt to judge conversational intent — that's the agent's job.
    This layer only catches things that are clearly not directed speech at all.
    """

    def __init__(self):
        # Pre-compile regex patterns for performance
        self._hallucination_patterns = [
            re.compile(r'\b' + re.escape(phrase) + r'\b', re.IGNORECASE)
            for phrase in WHISPER_HALLUCINATIONS
            if len(phrase.split()) > 1  # Only multi-word phrases as regex
        ]

        # Single-word hallucinations checked via set lookup
        self._hallucination_words = {
            phrase.lower() for phrase in WHISPER_HALLUCINATIONS
            if len(phrase.split()) == 1
        }

        # Singing pattern: repetitive syllables (la-la-la, na-na-na, etc.)
        self._singing_pattern = re.compile(
            r'\b(la|na|da|do|ba|hey|oh|ooh|yeah|sha|ra|ta)\b'
            r'(?:\s+\1){2,}',
            re.IGNORECASE
        )

        # Word repetition pattern: same word 4+ times in a row
        self._repetition_pattern = re.compile(
            r'\b(\w+)\b(?:\s+\1){3,}',
            re.IGNORECASE
        )

        # Character repetition: same character 6+ times
        self._char_repetition = re.compile(r'(.)\1{5,}')

        # Phrase repetition: 2-4 word phrase repeated 3+ times (catches "You're welcome. You're welcome. You're welcome.")
        self._phrase_repetition = re.compile(
            r'((?:\b\w+\b[.,!?\s]*){2,4})\1{2,}',
            re.IGNORECASE
        )

    def check(self, text: str, confidence: Optional[float] = None,
              no_speech_prob: Optional[float] = None,
              compression_ratio: Optional[float] = None) -> FilterResult:
        """
        Evaluate whether transcribed text should be sent to the agent.

        Args:
            text: The transcribed text from Whisper
            confidence: avg_logprob from Whisper (closer to 0 = higher confidence)
            no_speech_prob: Whisper's probability that the segment is not speech
            compression_ratio: Whisper's compression ratio for the segment

        Returns:
            FilterResult with passed=True if text should reach the agent
        """
        # Normalize
        stripped = text.strip()
        lower = stripped.lower().strip('.,!?;:\'"')

        # === A. Whisper Quality Gate ===

        # Empty or near-empty
        if len(stripped) < 3:
            return FilterResult(False, f"too_short: '{stripped}' ({len(stripped)} chars)")

        # No-speech probability (Whisper's own non-speech detector).
        # Standalone gate: coughs, sneezes, and other non-speech bursts often
        # get transcribed with moderate confidence — don't require low
        # confidence as a secondary condition.
        if no_speech_prob is not None and no_speech_prob > 0.4:
            return FilterResult(False, f"no_speech: prob={no_speech_prob:.2f}")

        # Very low confidence (below Whisper's own recommended -1.0 cutoff)
        if confidence is not None and confidence < -1.0:
            return FilterResult(False, f"low_confidence: {confidence:.2f}")

        # High compression ratio (repetitive/hallucinated output)
        if compression_ratio is not None and compression_ratio > 2.4:
            return FilterResult(False, f"high_compression: {compression_ratio:.2f}")

        # Known hallucination phrases (multi-word)
        for pattern in self._hallucination_patterns:
            if pattern.search(lower):
                return FilterResult(False, f"hallucination: matched '{pattern.pattern}'")

        # Single-word hallucination check (only if text is a single word)
        words = lower.split()
        if len(words) == 1 and lower in self._hallucination_words:
            return FilterResult(False, f"hallucination_word: '{lower}'")

        # Hallucination anchor substrings (catches variants like "thank you SO MUCH for watching")
        for anchor in HALLUCINATION_ANCHORS:
            if anchor in lower:
                return FilterResult(False, f"hallucination_anchor: '{anchor}'")

        # Word repetition (same word 4+ times consecutively)
        if self._repetition_pattern.search(lower):
            return FilterResult(False, f"word_repetition: '{stripped}'")

        # Phrase repetition (same 2-4 word phrase 3+ times)
        if self._phrase_repetition.search(lower):
            return FilterResult(False, f"phrase_repetition: '{stripped}'")

        # Character repetition (same char 6+ times)
        if self._char_repetition.search(lower):
            return FilterResult(False, f"char_repetition: '{stripped}'")

        # === B. Backchannel Gate ===

        # Isolated single-word backchannel
        if len(words) == 1 and lower in BACKCHANNELS:
            return FilterResult(False, f"backchannel: '{lower}'")

        # Two-word backchannel/exclamation
        if len(words) == 2 and lower in BACKCHANNEL_PAIRS:
            return FilterResult(False, f"backchannel_pair: '{lower}'")

        # === C. Non-Speech Vocalization Gate ===

        # Singing patterns (la-la-la, na-na-na, etc.)
        if self._singing_pattern.search(lower):
            return FilterResult(False, f"singing_pattern: '{stripped}'")

        # === Passed all gates ===
        return FilterResult(True, "passed")
