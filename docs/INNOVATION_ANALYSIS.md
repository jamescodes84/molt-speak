# Molt-Speak: Innovation Analysis

## What This System Is

Molt-Speak is a full-duplex, always-on voice agent for macOS. It listens to ambient room audio, determines whether speech is directed at it using a multi-signal scoring system, and responds conversationally via TTS — all without a wake word. Three coordinated subprocesses (Ears, Mouth, Coordinator) communicate through file-based IPC, with an LLM agent as the intelligence layer.

No other voice AI system — commercial, open-source, or academic — occupies this design space.

```
                    Session-Based              Always-On Ambient
                    (all speech = mine)        (must detect directedness)
                    ─────────────────          ──────────────────────────
Binary Gate         Retell, VAPI, Bland        Alexa, Siri, Google
(wake word / ON-OFF)                           (wake word → open mic)

Continuous Scoring  OpenAI semantic VAD        ██ MOLT-SPEAK ██
(graduated response (3 eagerness levels,       (4-signal temperature,
 threshold)         no DDSD)                    BIS/BAS disposition,
                                                3-tier closing,
                                                momentum floors)
```

---

## The 10 Innovations

### 1. Conversation Temperature — Continuous Engagement Scoring as a Response Gate

A real-time 0.0–1.0 score computed from four weighted signals — temporal proximity, lexical directedness, ASR confidence, and dialog state — that calibrates when the agent should respond. Not a binary yes/no. A gradient. The score is disposition-adjusted: boldness shifts the curve, scales momentum, and stretches temporal decay.

**What everyone else does:** Amazon Alexa, Google Assistant, and Siri use binary wake-word gates — OFF until triggered, then ALL speech is assumed directed. OpenAI's Realtime API is session-based with no device-directed speech detection. Apple's 2024 DDSD research is the closest parallel — multi-signal LLM classifier — but outputs binary (directed vs. not-directed), not a continuous score.

**Why this is novel:** No published system uses a continuous engagement score to dynamically calibrate a voice agent's response threshold. The closest academic precedent is Reichl & Hammer (Interspeech 2004) who coined "conversational temperature" for post-hoc conversation characterization, not real-time agent decision-making. OpenAI's semantic VAD eagerness parameter has 3 levels. Molt-Speak has a continuous 0.0–1.0 scale with momentum, decay, and overrides.

---

### 2. Psychologically-Grounded Disposition System — BIS/BAS + Kagan

A 1–100 "boldness" parameter that mechanically adjusts the agent's response threshold, conversation momentum, temporal decay, and warm-up behavior. Implemented across three layers:

**Signal-level** (`conversation_temperature.py`): Three mathematical perturbation factors — `_score_bias = (boldness - 40) / 250` shifts the curve, `_momentum_mult = 0.6 + boldness / 100` scales conversation inertia, `_halflife_mult = 1.0 + (boldness - 40) / 100` scales temporal persistence. Bold agents keep conversations alive longer and decay slower.

**Behavioral** (`AGENT_INSTRUCTIONS.txt`): Three full disposition profiles. Bold (60-100): BAS-dominant, respond to any directedness signal, one criterion enough, volunteer context, interpret ambiguity charitably, instant error recovery, false silence is catastrophic via the still-face paradigm. Somewhat Timid (30-59): default balanced profile, standard thresholds, neutral ambiguity interpretation. Timid (1-29): BIS-dominant, require 2/3 Listening Principle criteria, concise responses, Kagan warm-up curve (reserved at exchanges 1-2, loosening at 3-5, normal after 5+), mild negative interpretation bias, explicit rejection prophecy prevention.

**UI** (`unified_menu_bar.py`): Menu bar submenu with five presets plus custom value dialog showing real-time perturbation stats. Changing boldness auto-restarts the voice loop.

**What everyone else does:** OpenAI uses prompt-level personality descriptors. Hume AI OCTAVE has voice quality sliders controlling how the agent sounds, not when it speaks. ElevenLabs uses text-based voice design prompts. Character.ai uses character descriptions.

**Why this is novel:** Every commercial system tunes personality through voice quality or prompt engineering. Molt-Speak tunes the fundamental decision of when to speak vs. stay silent based on personality psychology, implemented as mathematical parameters in the scoring pipeline. No published AI system applies Gray's BIS/BAS or Kagan's temperament research as quantitative parameters controlling an agent's behavioral activation pattern. The three-layer implementation (signal math + behavioral rules + UI controls) makes this a complete system. Zero precedent found.

---

### 3. Three-Tier Asymmetric Closing Detection

A conversation ending detection system with three tiers of decreasing severity. Tier 1 (Terminal): "bye", "goodbye", "see ya" — hard override to cold, full momentum reset. Tier 2 (Departure): context-scored using nine weighted signals including completion vocabulary, brevity, no question mark, first-person departure, and closure idioms — override to near-cold. Tier 3 (Gratitude): "thanks", "thank you" in active conversation — reduces but doesn't kill momentum.

The design is asymmetric: cool-down is instant (closings immediately override momentum), warm-up is gradual. Motivated by Mastroianni et al. (Harvard 2021): only 2% of conversations end when both parties want them to.

**What everyone else does:** Alexa and Google use binary exit intent matching — one tier, no context scoring. Dialog systems use a single "end_conversation" intent class. Robot HRI research (Uchida et al. 2024) designs multi-step closing sequences, but for initiating closings, not detecting them.

**Why this is novel:** No published voice agent implements multi-tier closing detection with context-scored departure intent. The nine-signal departure scorer — where brevity is the strongest differentiator — is original. The asymmetric momentum override follows directly from Schegloff & Sacks' conversational analysis framework applied as a runtime mechanism.

---

### 4. Momentum Floors with Temporal Gating

Once a conversation reaches a certain depth, the temperature score cannot fall below a floor — but the floor itself decays with temporal distance. Five or more exchanges with temporal proximity above 0.3 sets a floor of 0.55 scaled by momentum and temporal factors. Three or more exchanges sets 0.45. One or more sets 0.35.

An active conversation stays "warm" even during pauses, but eventually goes cold if the user truly stops engaging. The floor respects disposition — boldness scales the momentum multiplier.

**What everyone else does:** Session-based systems keep the session ON until explicitly ended, with no concept of graduated engagement. Wake-word systems like Alexa's Follow-Up Mode keep the mic hot for a fixed 5-8 second window, then revert. No graduated floor.

**Why this is novel:** The concept of a conversation floor that prevents active sessions from reading cold but which itself decays with time is not found in any published system. It solves "we're in a conversation but there was a natural pause" without requiring the user to re-invoke.

---

### 5. Rejection Prophecy Prevention with Mechanical Correction Tracking

A fully implemented safeguard against the hostile-submissive death spiral — the failure mode where a correction causes the agent to withdraw, the withdrawal causes the user to disengage, the disengagement "confirms" the agent should be more cautious, and the interaction dies.

**Pipeline layer** (`conversation_temperature.py`): A regex detects correction phrases ("not you", "wasn't talking to you", "shut up", "stop talking", "go away", "leave me alone"). Timestamps and exchange counts track correction state mechanically. The `recent_correction` flag is True if a correction happened within five minutes AND fewer than three successful exchanges since. Auto-clears on whichever comes first. Written to the temperature JSON so the agent sees it.

**Behavioral layer** (`AGENT_INSTRUCTIONS.txt`): Per-disposition correction response rules. Bold agents acknowledge internally and do not change threshold — instant recovery. Somewhat Timid agents increase caution slightly for 2-3 utterances, then return to baseline. Timid agents have active BIS post-event processing but with an explicit REJECTION PROPHECY warning preventing spiral. All dispositions: clear directives always get answered regardless of correction state. Warmth is non-negotiable — "A timid agent who is cold when they speak is broken."

**What everyone else does:** No published voice AI system addresses this failure mode. Commercial systems either always respond (session-based) or require explicit invocation (wake-word), so the problem doesn't arise.

**Why this is novel:** This is a psychologically-informed safeguard with mechanical enforcement. The pipeline detects corrections automatically, tracks recovery, and auto-clears the flag. The agent doesn't have to self-regulate (which LLMs are bad at); the system does it for them. The concept draws from clinical psychology (hostile-submissive interpersonal dynamics) applied to AI behavior. No precedent found.

---

### 6. Barge-In as Engagement Signal

When a user interrupts the agent mid-speech, the barge-in event feeds back into the temperature system as a +0.15 engagement bonus. If the user cared enough to interrupt, they're actively engaged. The system preserves exactly what was said vs. what was interrupted via structured JSON (barge-point tracking). A near-complete playback filter (90% plus a 3-word floor) prevents tail-end interruptions from being falsely counted. The agent receives structured context so it can handle continuation naturally.

**What everyone else does:** Standard barge-in stops playback and starts a new turn with no feedback into engagement scoring. Amazon Nova Sonic (2025) preserves conversation context across barge-in events — the closest parallel for context preservation. Nuance IVR uses mark elements for telephony barge-point tracking.

**Why this is novel:** The bidirectional feedback loop — barge-in feeding into temperature feeding into response threshold — is not found in any published system. The near-complete playback filter is a practical innovation not documented elsewhere.

---

### 7. Hybrid LLM + Signal Scoring Architecture

The temperature system produces a continuous score, but the LLM agent makes the final call on whether to respond. The agent receives the temperature score with its component breakdown, disposition label, speech act classification guidance (Searle's taxonomy), a listening principle with three criteria, and threshold rules that vary by temperature band.

This is a two-stage architecture: lightweight signal scoring running in microseconds in the voice pipeline, followed by heavyweight LLM reasoning where the agent reads the score and decides.

**What everyone else does:** Apple's 2024 DDSD has the LLM do classification directly — heavy, single-stage. Amazon and Google use dedicated ML classifiers — lightweight, single-stage, binary. OpenAI and Hume have no device-directed speech detection at all.

**Why this is novel:** The scoring system handles the 90% case (clearly cold or clearly hot) at near-zero cost, while the LLM handles the ambiguous middle where language understanding matters most. More efficient than Apple's approach (LLM for everything) and more sophisticated than Amazon's (classifier for everything).

---

### 8. 2D Personality Space — Boldness x Elaboration

Disposition (when to speak) and elaboration (how much to say) are independent, orthogonal axes creating a 2D personality space with distinct behavioral profiles. Timid + Minimal is maximum reservation — speaks rarely, says little, risk of hostile-submissive zone. Timid + Extensive is the "warm introvert" — rarely speaks but gives rich responses, explicitly identified as the antidote to the death spiral. Bold + Minimal is the "efficient extrovert" — responds to everything but keeps it terse. Bold + Extensive is maximum engagement, with the risk of overwhelming.

Elaboration level (1-5) is stored independently of boldness (1-100). Both are written to the temperature JSON. The agent instructions define five elaboration levels with specific behavioral descriptions. The menu bar has a separate Response Detail submenu.

**What everyone else does:** OpenAI, Hume, and ElevenLabs treat personality as one-dimensional — a style prompt or independent voice quality sliders with no interaction model between them. No system models the interaction between response frequency and response depth as a personality construct.

**Why this is novel:** The explicit modeling of personality as a 2D space with named interaction profiles — and the identification that certain combinations are dangerous while others are protective — has no parallel in voice AI. This is closer to clinical personality assessment than to anything in the voice agent literature.

---

### 9. Asymmetric Error Architecture with Inverted Gray Zone Default

The entire agent instruction framework is structured around the principle that false silence is catastrophically worse than false speech. This is not a guideline — it's architecturally enforced.

The Stakes section frames failure asymmetrically: responding to ambient speech is a recoverable two-second annoyance; ignoring a direct address is catastrophic trust destruction. The Gray Zone default has been inverted: stay silent ONLY when all six conditions are met simultaneously — no address, no AI content, no question structure, no active thread, temperature cold, AND clearly directed elsewhere. The Asymmetric Error Rule is a named section with an explicit 5x cost ratio. "Rule One: Use Your Brain" emphasizes that the LLM's language understanding is its primary tool, not keyword matching or temperature scores. Bold disposition amplifies the asymmetry further via the still-face paradigm warning.

**What everyone else does:** Alexa, Siri, and Google implicitly assume false positives are worse — the entire wake-word paradigm minimizes unwanted activations. OpenAI's voice agent documentation recommends erring on the side of caution. PwC/CHI 2023 research found false rejection is 2-3x worse than false acceptance, but no commercial system has implemented this finding.

**Why this is novel:** The entire voice AI industry was built on the assumption that unwanted activations are the primary failure mode. Molt-Speak architecturally inverts this — treating missed responses as the catastrophic failure and unwanted responses as recoverable. The implementation spans signal scoring (temperature bias), behavioral rules (gray zone inversion), and psychological framing (still-face paradigm). This is a fundamental philosophical break from every existing voice assistant.

---

### 10. Software-Only Multimodal Echo Prevention

Three-layer echo prevention without hardware AEC. Signal-file mic gating raises the amplitude threshold during TTS playback. Text-level echo detection compares transcribed audio against the agent's recent output using substring matching and 80% fuzzy word overlap. Coordination signals — `ears_pause.signal` created and deleted by the Coordinator based on mouth status — provide the third layer.

**What everyone else does:** Commercial smart speakers use hardware AEC with 6-7 microphone arrays and beamforming. Google's TEC (2021) uses a neural model with source text to enhance the audio signal pre-transcription. Software AEC libraries use adaptive filters on raw audio.

**Why this is novel:** The text-level echo detection operates at a completely different layer than Google's TEC. The three-layer defense-in-depth approach avoids real-time audio-domain AEC complexity entirely. Not novel as individual techniques, but the combination is practical and well-suited to the single-user desktop architecture.

---

## Novelty Summary

| # | Innovation | Closest Parallel | Gap | Level |
|---|---|---|---|---|
| 1 | Continuous temperature scoring as response gate | Apple DDSD (binary), Reichl 2004 (post-hoc) | Large | HIGH |
| 2 | BIS/BAS disposition tuning (3-layer) | OpenAI eagerness (3 levels), Hume OCTAVE (voice quality) | Very large | VERY HIGH |
| 3 | Three-tier closing detection | Alexa/Google binary exit intents | Large | HIGH |
| 4 | Momentum floors with temporal gating | Alexa Follow-Up Mode (fixed window) | Large | HIGH |
| 5 | Rejection prophecy prevention + mechanical correction tracking | (nothing) | Very large | VERY HIGH |
| 6 | Barge-in as engagement signal | Nova Sonic context preservation | Moderate | MOD-HIGH |
| 7 | Hybrid LLM + signal scoring | Apple LLM DDSD, Amazon classifiers | Moderate | MOD-HIGH |
| 8 | 2D personality space (boldness x elaboration) | OpenAI/Hume 1D style controls | Large | HIGH |
| 9 | Asymmetric error architecture + inverted gray zone | PwC/CHI 2023 (research only, not implemented) | Very large | VERY HIGH |
| 10 | Software multimodal echo prevention | Google TEC, hardware AEC | Small | MODERATE |

**Zero precedent (VERY HIGH):** Disposition system, Rejection prophecy prevention, Asymmetric error architecture

**No close parallel (HIGH):** Temperature scoring, Closing detection, Momentum floors, 2D personality space

**Moderate gap (MOD-HIGH):** Barge-in feedback, Hybrid architecture

**Small gap (MODERATE):** Echo prevention

---

## Research Foundations

| Source | Applied As |
|---|---|
| Gray's BIS/BAS theory | Boldness parameter, score bias, momentum multiplier, disposition profiles |
| Kagan's temperament research | Warm-up curve for timid agents, habituation model |
| Schegloff & Sacks (1973) | Three-tier closing detection structure |
| Mastroianni et al. (Harvard 2021) | Asymmetric cool-down — conversations end late, not early |
| Tronick's still-face paradigm | Bold carry-forward warning, warmth non-negotiable rule |
| Coan's social baseline theory | Human dysregulation when expected social resource goes silent |
| Grice's Quantity maxim | Bold agents over-inform, timid agents under-inform |
| Searle's speech act taxonomy | Agent instruction classification — directives, representatives, expressives |
| Rejection sensitivity research | Hostile-submissive death spiral prevention, correction auto-clearing |
| Apple DDSD (2024) | ASR confidence as directedness proxy |
| Amazon ASR decoder research | ASR decoder features as strongest single signal |
| Frontiers 23-study review | Composite signals outperform single features |
| PwC/CHI 2023 | Asymmetric error cost — false rejection 2-3x worse than false acceptance |

---

## Architecture

### Components

**OpenClaw Ears** (`open_ears/`) — Voice input. Microphone capture at 16kHz, amplitude thresholding, optional Silero VAD confirmation, faster-whisper transcription (INT8 quantized, greedy decoding), input filtering (hallucination detection, backchannel suppression, singing patterns), echo detection, conversation temperature scoring, agent message delivery via pre-compiled AppleScript.

**OpenClaw Mouth** (`open_mouth/`) — Voice output. File monitoring (watchdog-based with 20ms backup polling), silence pattern detection, sentence-level pipelining with prefetch, multi-provider TTS (Edge-TTS, ElevenLabs, macOS `say`), streaming audio playback via sounddevice, barge-in handling with interrupted speech context preservation.

**Coordinator** (`src/core/coordinator.py`) — Echo prevention. Monitors mouth status, creates/deletes `ears_pause.signal` to mute microphone during TTS, sends agent instructions on startup and shutdown signals on exit.

**Unified Audio** (`src/unified_audio.py`) — Subprocess management. Starts Mouth first, then Ears. Monitors both for crashes. Graceful shutdown in reverse order.

**Menu Bar** (`unified_menu_bar.py`) — macOS control UI. Real-time status display, configuration (voice, sensitivity, boldness, elaboration, TTS provider, debug mode), process management, analytics integration.

### Inter-Process Communication

All communication is file-based — the agent runs in Terminal and can only interact with the filesystem.

```
runtime/
  speech_output.txt              Agent responses (Mouth monitors)
  conversation_temperature.json  Engagement score (Agent reads before every response)
  barge_in_context.json          Interruption context (Agent reads before every response)
  ears_status.txt                User speaking? (Mouth reads for barge-in)
  mouth_status.txt               Agent speaking? (Coordinator reads for echo prevention)
  ears_pause.signal              Mic muted (Coordinator creates/deletes)
  molt_speak_config.json         User preferences (persistent)
  interrupted_speech.json        What was said vs. interrupted (Ears reads)
```

### Boot Sequence

1. Create `runtime/` and `logs/` directories
2. Clear `speech_output.txt` and session logs
3. Spawn Mouth subprocess — creates `mouth_status.txt` with IDLE
4. Wait 500ms
5. Spawn Ears subprocess — loads Whisper model (1-3s), compiles AppleScript, starts audio capture
6. Wait 300ms
7. Spawn Coordinator — monitors mouth status, sends agent instructions
8. Menu bar initializes — auto-starts all systems after 1s delay

### Performance

- Mic-to-send latency: under 2 seconds (silence-triggered)
- Transcription turnaround: 0.2-0.5 seconds (faster-whisper)
- AppleScript delivery: ~50ms (non-blocking, pre-compiled)
- Audio capture: 50ms chunks at 16kHz (20Hz polling)
- Status updates: 100ms (10Hz)
- Display refresh: 50ms (20Hz)

---

## Verdict

Molt-Speak's deepest innovations are in the integration philosophy: applying behavioral psychology (Gray, Kagan, Tronick, Coan, Grice) and conversation analysis (Schegloff & Sacks) as quantitative, mechanically-enforced parameters in a real-time voice pipeline. No other voice AI system bridges personality psychology and signal processing this way.

Three innovations have zero precedent. Four have no close parallel. The conversation temperature system produces a continuous score modulated by momentum, closing detection, disposition, and correction state — all features without published parallel. The asymmetric error inversion — treating false silence as catastrophic and false speech as recoverable — is a fundamental philosophical break from every existing voice assistant, implemented across every layer of the system.
