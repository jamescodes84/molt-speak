#!/usr/bin/env python3
"""
OpenClaw Ears - Maximum Performance Voice Pipeline
Optimized for fastest possible STT → Agent → TTS at zero cost

Key optimizations:
- faster-whisper with CTranslate2 backend (4x faster than openai-whisper)
- Direct numpy array transcription (no temp file I/O)
- INT8 quantization (2x speedup on CPU)
- Greedy decoding (beam_size=1) for fast short utterances
- 0.8s silence detection (tuned for conversational speech)
- Pre-compiled AppleScript with non-blocking delivery
- Async file I/O (context writes off the hot path)
"""

import json
import re
import sys
import os
import time
import threading
import queue
import numpy as np
import sounddevice as sd
from pathlib import Path
from collections import deque
from datetime import datetime

from src.services.transcription_service import WhisperTranscriberOptimized
from src.services.mouth_status_monitor import MouthStatusMonitor
from src.services.ears_status_notifier import EarsStatusNotifier
from src.services.input_filter import InputFilter
from src.services.conversation_temperature import ConversationTemperature
from src.services.social_cues_meter import SocialCuesMeter
from src.services.pragmatic_analyzer import PragmaticAnalyzer
from src.services.environment_memory import EnvironmentMemory
from src.core.state_manager import AudioState
from src.utils.openclaw_notifier import OpenClawNotifier
from src.core.terminal_visualizer import TerminalVisualizer
from src.config import settings

import logging
import importlib.util
logger = logging.getLogger(__name__)

# Import error registry from project root (not open_ears/src/)
_errors_path = Path(__file__).parent.parent.parent.parent / "src" / "errors.py"
_spec = importlib.util.spec_from_file_location("molt_errors", str(_errors_path))
_errors_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_errors_mod)
lookup_error = _errors_mod.lookup_error


class UltraFastVoicePipeline:
    """
    Maximum performance voice transcription system
    Optimized for speed with zero extra cost
    """

    def __init__(self,
                 output_dir=None,  # Defaults to settings.VOICE_DIR
                 model_size='small',
                 silence_duration=1.1,  # Seconds of silence before submitting
                 speech_threshold=500,
                 sample_rate=16000,
                 enable_tts=False,
                 analytics=None,
                 debug_mode=False):
        """
        Initialize ultra-fast voice pipeline

        :param silence_duration: Seconds of silence before submitting (1.1s = fast response)
        :param enable_tts: Enable text-to-speech responses
        :param analytics: Analytics manager instance
        :param debug_mode: Include inline temp/barge-in tags in messages (default: clean text)
        """
        self.debug_mode = debug_mode
        self.analytics = analytics
        if output_dir is None:
            self.output_dir = settings.VOICE_DIR
        else:
            self.output_dir = Path(output_dir).expanduser()
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.sample_rate = sample_rate
        self.silence_duration = silence_duration
        self.speech_threshold = speech_threshold
        self.barge_multiplier = self._get_barge_multiplier()
        self.speaking_threshold = speech_threshold * self.barge_multiplier

        # Agent boldness — disposition perturbation for conversation temperature
        self._boldness_value = self._get_agent_boldness()
        v = self._boldness_value
        if v <= 15: self._boldness_label = "very_timid"
        elif v <= 35: self._boldness_label = "timid"
        elif v <= 50: self._boldness_label = "somewhat_timid"
        elif v <= 70: self._boldness_label = "balanced"
        else: self._boldness_label = "bold"
        self.enable_tts = enable_tts
        self.check_interval = 0.05  # Check audio every 50ms for responsiveness

        # Terminal Visualizer
        self.visualizer = TerminalVisualizer(width=60)
        self.visualizer.threshold = speech_threshold
        self.current_amplitude = 0
        self.is_speaking = False

        # Streaming state
        self.audio_buffer = []
        self.buffer_lock = threading.Lock()
        self.transcription_queue = queue.Queue()

        # Silence detection state
        self.last_speech_time = None
        self.accumulated_audio = []
        self.is_recording = False

        # Sustained speech detection: require consecutive frames above threshold
        # before signaling SPEECH_DETECTED — filters transient noise (cracks, pops)
        self._consecutive_speech_frames = 0
        self._barge_speech_frames_required = 2  # ~100ms at 50ms/frame (check_interval)
        self.min_segment_duration = 0.5  # Minimum audio duration (seconds) to transcribe

        # Silero VAD: neural speech detector for barge-in confirmation.
        # Loaded lazily — only activates if silero-vad is installed.
        # Runs only when amplitude threshold is sustained — adds <1ms overhead.
        self._silero_vad = None
        self._silero_available = False
        self._silero_torch = None  # lazy-loaded torch reference

        # Pre-roll buffer: keep last ~150ms of audio for capturing word onsets
        # Each capture loop iteration grabs ~50ms, so 5 entries = ~250ms lookback
        self.pre_roll_buffer = deque(maxlen=5)

        # Echo detection: cache agent's recent speech for comparison
        self._recent_agent_text = ""

        # Volley sync: track when we're waiting for the agent to respond
        # so we can cancel stale generation if the user speaks again
        self._awaiting_response = False
        self._last_sent_time = 0

        # --- Fast-path init: mic-critical state only (no heavy loading) ---

        # Lightweight services that don't block
        self.state = AudioState(state_dir=str(self.output_dir))
        self.openclaw = OpenClawNotifier(queue_dir=str(self.output_dir))
        self.mouth_monitor = MouthStatusMonitor()
        self.ears_notifier = EarsStatusNotifier()
        self.input_filter = InputFilter()
        self.conversation_temp = ConversationTemperature(boldness=self._boldness_value)
        self.social_cues = SocialCuesMeter()
        self.pragmatic = PragmaticAnalyzer()
        self.environment_memory = EnvironmentMemory()

        # Ensure lifespan data is saved on shutdown (atexit + SIGTERM)
        import atexit
        import signal as _signal
        atexit.register(self._shutdown_social_cues)
        _signal.signal(_signal.SIGTERM, self._sigterm_handler)

        # AppleScript and transcriber loaded in background (see _deferred_init)
        self._compiled_send_script = None
        self._compiled_cancel_script = None
        self._last_osascript_proc = None
        self.transcriber = None
        self._model_size = model_size
        self._ready = threading.Event()  # Set when Whisper model is loaded

        # Background I/O thread for non-critical file writes
        self._io_queue = queue.Queue()
        self._io_thread = threading.Thread(target=self._io_worker, daemon=True)
        self._io_thread.start()

        # TTS (if enabled)
        self.tts_queue = queue.Queue()
        if enable_tts:
            try:
                import edge_tts
                self.edge_tts = edge_tts
            except ImportError:
                logger.error(lookup_error("EDGE_TTS_NOT_INSTALLED").log_message())
                self.enable_tts = False

        # Display
        self.current_transcription = ""
        self.transcription_count = 0
        self.last_transcription_time = 0

        # Dedup guard: prevent the same barge-in utterance from being sent twice
        # (first without tag, then with) due to audio segment splitting
        self._last_sent_text = ""
        self._last_sent_time_dedup = 0.0

        # Performance metrics
        self.avg_transcription_time = 0
        self.transcription_times = deque(maxlen=10)

        # Speaking flag to prevent listening while TTS is active
        self.is_speaking_tts = False

        self.running = False
        self.segment_count = 0

        # Debug mode indicator
        if self.debug_mode:
            print("DEBUG MODE ENABLED")
        try:
            debug_state_file = Path(settings.PROJECT_DIR) / "runtime" / "debug_mode_state.txt"
            debug_state_file.write_text(f"debug_mode={self.debug_mode}\n")
        except Exception:
            pass

    def _deferred_init(self):
        """Load heavy resources in background so the mic can start immediately.

        Called from a daemon thread in start(). Sets self._ready when Whisper
        is loaded so the transcription worker can begin processing.
        """
        # Load Whisper model (the heavy part — 1-3 seconds)
        print(f"🚀 Loading Whisper {self._model_size} model...")
        self.transcriber = WhisperTranscriberOptimized(
            model_size=self._model_size,
            compute_type='int8'
        )
        print("✅ Whisper model loaded — transcription ready")
        self._ready.set()

        # Pre-compile AppleScript (two osacompile subprocess calls)
        self._compiled_send_script = self._compile_applescript_send()
        self._compiled_cancel_script = self._compile_applescript_cancel()

        # Status prints
        if self.openclaw.is_available():
            print("✅ OpenClaw integration enabled")
        if self.mouth_monitor.is_available():
            print("✅ Mouth integration enabled (echo prevention)")

    def _get_barge_multiplier(self) -> int:
        """Get barge-in threshold multiplier from ConfigManager."""
        try:
            import sys
            config_manager_path = settings.PROJECT_DIR / "src" / "config"
            if str(config_manager_path) not in sys.path:
                sys.path.insert(0, str(config_manager_path))
            from config_manager import ConfigManager
            config = ConfigManager()
            return config.get_barge_multiplier()
        except Exception:
            return 5  # Default fallback

    def _get_agent_boldness(self) -> int:
        """Get agent boldness from ConfigManager."""
        try:
            import sys
            config_manager_path = settings.PROJECT_DIR / "src" / "config"
            if str(config_manager_path) not in sys.path:
                sys.path.insert(0, str(config_manager_path))
            from config_manager import ConfigManager
            config = ConfigManager()
            return config.agent_boldness
        except Exception:
            return 40  # Default fallback

    def _shutdown_social_cues(self):
        """Save lifespan data on shutdown."""
        if hasattr(self, 'social_cues'):
            self.social_cues.end_session()

    def _sigterm_handler(self, signum, frame):
        """Handle SIGTERM from unified_audio.py process manager."""
        self._shutdown_social_cues()
        sys.exit(0)

    def _compute_elaboration_level(self, temp_score: float) -> int:
        """Derive elaboration level (1-5) from temperature score and boldness.

        Temperature drives elaboration; boldness scales the ceiling.
        Timid agents cap low even in hot conversations.
        Bold agents can reach extensive at high temperature.
        """
        max_elab = 2.0 + 3.0 * (self._boldness_value / 100.0)
        raw = 1.0 + (max_elab - 1.0) * temp_score
        return max(1, min(5, round(raw)))

    def _compute_elaboration_label(self, temp_score: float) -> str:
        """Human-readable label for the computed elaboration level."""
        labels = {1: "minimal", 2: "brief", 3: "standard", 4: "detailed", 5: "extensive"}
        return labels.get(self._compute_elaboration_level(temp_score), "standard")

    def _compile_applescript_send(self):
        """Pre-compile AppleScript for fast text delivery to Terminal."""
        import subprocess as _sp
        window_pattern = settings.TARGET_WINDOW_PATTERN

        script_source = f'''on run argv
    set inputText to item 1 of argv
    tell application "Terminal"
        set foundWindow to missing value
        set searchPattern to "{window_pattern}"
        if searchPattern is not "" then
            repeat with w in windows
                if name of w contains searchPattern then
                    set foundWindow to w
                    exit repeat
                end if
            end repeat
        end if
        if foundWindow is missing value and (count of windows) > 0 then
            set foundWindow to front window
        end if
        if foundWindow is not missing value then
            do script inputText in (selected tab of foundWindow)
        end if
    end tell
end run
'''
        try:
            source_path = '/tmp/molt_speak_send.applescript'
            compiled_path = '/tmp/molt_speak_send.scpt'
            with open(source_path, 'w') as f:
                f.write(script_source)
            _sp.run(['osacompile', '-o', compiled_path, source_path],
                    capture_output=True, timeout=5)
            print("✅ AppleScript pre-compiled for fast delivery")
            return compiled_path
        except Exception as e:
            logger.warning(lookup_error("APPLESCRIPT_COMPILE_FAILED").log_message(e))
            return None

    def _compile_applescript_cancel(self):
        """Pre-compile AppleScript for sending Escape to cancel agent generation."""
        import subprocess as _sp
        window_pattern = settings.TARGET_WINDOW_PATTERN

        script_source = f'''tell application "Terminal"
    set foundWindow to missing value
    set searchPattern to "{window_pattern}"
    if searchPattern is not "" then
        repeat with w in windows
            if name of w contains searchPattern then
                set foundWindow to w
                exit repeat
            end if
        end repeat
    end if
    if foundWindow is missing value and (count of windows) > 0 then
        set foundWindow to front window
    end if
    if foundWindow is not missing value then
        do script (ASCII character 27) in (selected tab of foundWindow)
    end if
end tell
'''
        try:
            source_path = '/tmp/molt_speak_cancel.applescript'
            compiled_path = '/tmp/molt_speak_cancel.scpt'
            with open(source_path, 'w') as f:
                f.write(script_source)
            _sp.run(['osacompile', '-o', compiled_path, source_path],
                    capture_output=True, timeout=5)
            return compiled_path
        except Exception:
            return None

    def _io_worker(self):
        """Process file I/O in background to avoid blocking transcription."""
        while self.running or not self._io_queue.empty():
            try:
                func, args = self._io_queue.get(timeout=0.5)
                func(*args)
            except queue.Empty:
                continue
            except Exception as e:
                logger.warning(lookup_error("BACKGROUND_IO_ERROR").log_message(e))

    def _audio_callback(self, indata, frames, time_info, status):
        """Capture and analyze audio"""
        if status:
            logger.debug(lookup_error("MIC_STREAM_WARNING").log_message(RuntimeError(str(status))))

        amplitude = np.sqrt(np.mean(indata**2)) * 10000
        self.current_amplitude = amplitude
        self.is_speaking = amplitude > self.speech_threshold

        # Update visualizer
        self.visualizer.update(amplitude, self.is_speaking)

        # Add to buffer
        with self.buffer_lock:
            self.audio_buffer.append(indata.copy())

    def _display_loop(self):
        """Update display using terminal visualizer"""
        while self.running:
            time.sleep(0.05)

            # Move cursor up and display the visualizer
            self.visualizer.clear_lines(4)
            print(self.visualizer.render_full())
            sys.stdout.flush()

    def _init_silero(self):
        """Lazy-load Silero VAD on first use. Safe to call multiple times."""
        if self._silero_available:
            return True
        if self._silero_vad is False:
            return False  # Already tried and failed
        try:
            import torch
            from silero_vad import load_silero_vad
            self._silero_vad = load_silero_vad(onnx=True)
            self._silero_torch = torch
            self._silero_available = True
            logger.info("Silero VAD loaded (neural barge-in confirmation)")
            return True
        except Exception as e:
            logger.info(lookup_error("VAD_LOAD_FAILED").log_message(e))
            self._silero_vad = False  # Sentinel: don't retry
            return False

    def _silero_confirm_speech(self, audio_data, threshold=0.5):
        """Run Silero VAD on audio chunk to confirm it's speech, not noise.

        Returns True if Silero detects speech above the given probability threshold.
        Falls back to True (permissive) if Silero is unavailable.
        """
        if not self._init_silero():
            return True

        try:
            # Silero expects exactly 512 samples at 16kHz (32ms)
            # Take the last 512 samples (most recent audio)
            if len(audio_data) >= 512:
                chunk = audio_data[-512:]
            else:
                chunk = np.pad(audio_data, (0, 512 - len(audio_data)))

            tensor = self._silero_torch.from_numpy(chunk.astype(np.float32))
            speech_prob = self._silero_vad(tensor, self.sample_rate).item()
            return speech_prob > threshold
        except Exception:
            return True  # Fail open — don't block speech on Silero errors

    def _capture_loop(self):
        """Capture audio with silence-based voice activity detection"""
        while self.running:
            time.sleep(self.check_interval)  # Check every 100ms for responsiveness

            # Use higher threshold when agent is speaking to prevent TTS bleed.
            # BUT: once we're already recording (speech confirmed by consecutive
            # frames + Silero), drop to normal threshold so the user's continued
            # speech isn't split by brief amplitude dips below the elevated bar.
            agent_speaking = self.is_speaking_tts or self.mouth_monitor.is_agent_speaking()
            if agent_speaking and not self.is_recording:
                current_threshold = self.speaking_threshold
            else:
                current_threshold = self.speech_threshold

            # Get buffered audio
            with self.buffer_lock:
                if len(self.audio_buffer) == 0:
                    if agent_speaking:
                        self.ears_notifier.notify_paused()
                    continue

                audio_data = np.concatenate(self.audio_buffer)
                self.audio_buffer = []

            # Check amplitude against current threshold
            max_amp = np.max(np.abs(audio_data)) * 10000
            frame_above_threshold = max_amp >= current_threshold

            # Sustained speech detection: require consecutive frames above
            # threshold to filter transient noise (cracks, pops, clicks).
            # Real speech sustains for hundreds of ms; a pop is one frame.
            if frame_above_threshold:
                self._consecutive_speech_frames += 1
            else:
                self._consecutive_speech_frames = 0

            # Gate barge-in through Silero VAD: amplitude says "something loud"
            # but Silero confirms "it's actually speech, not a fan or music."
            # Silero only runs when sustained threshold is met (not every frame).
            if self._consecutive_speech_frames >= self._barge_speech_frames_required:
                is_confirmed_speech = self._silero_confirm_speech(audio_data)
            else:
                is_confirmed_speech = False

            has_speech = (
                (self._consecutive_speech_frames >= self._barge_speech_frames_required and is_confirmed_speech)
                or (self.is_recording and frame_above_threshold)
            )

            if has_speech:
                # Speech detected - update last speech time and accumulate audio
                self.last_speech_time = time.time()
                # Notify mouth that user is speaking (triggers barge-in)
                self.ears_notifier.notify_speech_detected(max_amp)
                if not self.is_recording:
                    self.is_recording = True
                    # Fast-kill: if agent is speaking, immediately truncate
                    # speech file so the Mouth stops after the current sentence
                    # instead of continuing to the next queued chunk.
                    if agent_speaking:
                        try:
                            sf = Path(settings.PROJECT_DIR) / "runtime" / "speech_output.txt"
                            sf.write_text("")
                        except Exception:
                            pass
                    # Prepend pre-roll buffer to capture the soft onset of the first word
                    if self.pre_roll_buffer:
                        self.accumulated_audio.extend(self.pre_roll_buffer)
                        self.pre_roll_buffer.clear()
                self.accumulated_audio.append(audio_data)
            else:
                # Silence detected - notify we're just listening
                self.ears_notifier.notify_listening()
                if self.is_recording and self.last_speech_time is not None:
                    # Keep accumulating audio during brief pauses between words
                    # so Whisper receives continuous audio without gaps
                    self.accumulated_audio.append(audio_data)

                    # Check if we've had enough silence to end the segment
                    silence_time = time.time() - self.last_speech_time
                    if silence_time >= self.silence_duration:
                        # Submit accumulated audio for transcription
                        if len(self.accumulated_audio) > 0:
                            full_audio = np.concatenate(self.accumulated_audio)
                            audio_duration = len(full_audio) / self.sample_rate
                            if audio_duration >= self.min_segment_duration:
                                self.segment_count += 1
                                self.transcription_queue.put((self.segment_count, full_audio, time.time()))

                        # Reset state
                        self.accumulated_audio = []
                        self.is_recording = False
                        self.last_speech_time = None
                        # Reset Silero RNN state between utterances
                        if self._silero_available:
                            self._silero_vad.reset_states()
                else:
                    # Not recording — maintain pre-roll buffer for word onset capture
                    self.pre_roll_buffer.append(audio_data)

    def _transcription_worker(self):
        """
        Process transcription queue
        OPTIMIZED: No file I/O, transcribe directly from memory
        """
        # Wait for Whisper model to finish loading (deferred init)
        self._ready.wait()

        while self.running:
            try:
                segment_num, audio_data, capture_time = self.transcription_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            # OPTIMIZATION: Transcribe directly from memory (no file I/O!)
            start_time = time.time()

            try:
                # Pass raw float32 audio — transcription service handles normalization
                result = self.transcriber.transcribe(
                    audio_data,
                    language='en'  # Pre-specify language for speed
                )
                text = result['text'].strip()

                transcription_time = time.time() - start_time
                total_latency = time.time() - capture_time

                self.transcription_times.append(transcription_time)
                self.avg_transcription_time = sum(self.transcription_times) / len(self.transcription_times)

                if text:
                    # Pre-filter: catch machine-level noise before it reaches the agent
                    filter_result = self.input_filter.check(
                        text,
                        confidence=result.get('confidence'),
                        no_speech_prob=result.get('no_speech_prob'),
                        compression_ratio=result.get('compression_ratio'),
                    )
                    if not filter_result.passed:
                        print(f"\n🔇 Filtered: \"{text}\" — {filter_result.reason}")
                        continue

                    # Echo detection: suppress agent's own speech picked up by mic
                    if self._detect_echo(text):
                        print(f"\n🔄 Echo filtered: \"{text}\"")
                        continue

                    # Dedup guard: during barge-in the user's speech can be
                    # split into two audio segments by the threshold transition,
                    # producing two near-identical transcriptions.  Suppress the
                    # second one so the agent isn't hit with a duplicate.
                    if self._last_sent_text and (time.time() - self._last_sent_time_dedup) < 3.0:
                        overlap = self._text_overlap(self._last_sent_text, text)
                        if overlap > 0.6:
                            print(f"\n🔇 Dedup suppressed (overlap {overlap:.0%}): \"{text}\"")
                            continue

                    # Check for barge-in FIRST so temperature scorer knows
                    barge_data = self._check_interrupted_speech()

                    # Score conversation temperature (barge-in = strong engagement signal)
                    temp_reading = self.conversation_temp.score(
                        text,
                        confidence=result.get('confidence'),
                        no_speech_prob=result.get('no_speech_prob'),
                        compression_ratio=result.get('compression_ratio'),
                        is_barge_in=bool(barge_data),
                    )
                    temp_tag = f'[CONV_TEMP: {temp_reading.score} / {temp_reading.label}]'
                    print(f"\n🌡️  {temp_tag} — {temp_reading.components}")

                    # Score social cues (behavioral dynamics)
                    social_reading = self.social_cues.score_user_turn(
                        text=text,
                        confidence=result.get('confidence'),
                        is_correction=temp_reading.recent_correction,
                        is_barge_in=bool(barge_data),
                    )
                    print(f"    🧭 social: {social_reading.engagement_label} | "
                          f"rapport={social_reading.rapport_label} | "
                          f"frust={social_reading.frustration_label} | "
                          f"eff_bold={social_reading.effective_boldness} "
                          f"({social_reading.disposition_blend})")

                    # Pragmatic coherence analysis (contextual intelligence)
                    recent_texts = self.social_cues.get_recent_user_texts(5)
                    known_entities = self.environment_memory.get_known_entities()
                    entity_match = self.environment_memory.match_entity(text)

                    pragmatic_reading = self.pragmatic.analyze(
                        text=text,
                        recent_texts=recent_texts,
                        exchange_count=temp_reading.exchange_count,
                        known_entities=known_entities,
                        entity_match=entity_match,
                    )

                    if pragmatic_reading.not_for_me_evidence > 0.3:
                        print(f"    🎯 pragmatic: not_for_me={pragmatic_reading.not_for_me_evidence:.2f} "
                              f"reasons={pragmatic_reading.suspicion_reasons}")

                    # Learn from corrections: when correction fires, teach environment memory
                    if temp_reading.correction_just_fired:
                        prev_texts = self.social_cues.get_recent_user_texts(3)
                        prev_text = prev_texts[-2] if len(prev_texts) >= 2 else ""
                        self.environment_memory.learn_from_correction(text, prev_text)
                        # Log correction trace for offline false-positive analysis (async)
                        entity_match = self.environment_memory.match_entity(prev_text) if prev_text else ""
                        self._io_queue.put((
                            self._write_correction_trace,
                            (prev_text, text, temp_reading, pragmatic_reading, entity_match)
                        ))
                    else:
                        self.environment_memory.check_followup_learning(text)

                    # Write agent-facing snapshot files SYNCHRONOUSLY (sub-ms)
                    # so the agent reads current data when it processes the message.
                    self._write_agent_context(temp_reading, barge_data, social_reading,
                                              pragmatic_reading, known_entities)
                    # Session logs are append-only — agent never reads them — async is fine.
                    self._io_queue.put((self._write_session_logs, (temp_reading, barge_data, social_reading, pragmatic_reading)))

                    self.current_transcription = text
                    self.transcription_count += 1
                    self.last_transcription_time = time.time()

                    # Track voice interaction
                    if self.analytics:
                        self.analytics.track_voice_interaction("transcription",
                            transcription_time=round(transcription_time, 3),
                            total_latency=round(total_latency, 3),
                            text_length=len(text),
                            word_count=len(text.split()),
                            model_size=self.transcriber.model_size if hasattr(self.transcriber, 'model_size') else 'unknown'
                        )

                    # Update visualizer with transcription
                    self.visualizer.set_transcription(text)

                    # Save to state (async — off the hot path)
                    self._io_queue.put((self.state.log_transcription, (text,)))
                    self._io_queue.put((self.state.update_interaction, ()))

                    if barge_data:
                        # BARGE-IN: cancel stale generation + truncate speech file
                        if self._is_agent_processing():
                            self._cancel_agent_generation()
                        else:
                            try:
                                speech_file = Path(settings.PROJECT_DIR) / "runtime" / "speech_output.txt"
                                speech_file.write_text("")
                            except Exception:
                                pass

                        if self.debug_mode:
                            message = f'{temp_tag} [BARGE-IN POINT: {barge_data["barge_point"]}] {text}'
                        else:
                            message = text
                        print(f"\n📤 Sending to TUI (debug={self.debug_mode}): {message[:100]}")
                        self._send_to_openclaw_tui(message)
                        self._awaiting_response = True
                        self._last_sent_time = time.time()
                        self._last_sent_text = text
                        self._last_sent_time_dedup = time.time()

                    else:
                        # NORMAL: send to agent with volley sync
                        if self._is_agent_processing():
                            print(f"\n🔄 Agent still processing — cancelling to sync volley")
                            self._cancel_agent_generation()

                        if self.debug_mode:
                            outgoing = f'{temp_tag} {text}'
                        else:
                            outgoing = text
                        print(f"\n📤 Sending to TUI (debug={self.debug_mode}): {outgoing[:100]}")
                        self._send_to_openclaw_tui(outgoing)
                        self._awaiting_response = True
                        self._last_sent_time = time.time()
                        self._last_sent_text = text
                        self._last_sent_time_dedup = time.time()

                    # Optional: Queue for TTS response
                    if self.enable_tts:
                        response = self._generate_agent_response(text)
                        if response:
                            self.tts_queue.put(response)

                    # Log performance
                    print(f"\n⚡ Transcribed in {transcription_time:.2f}s (total latency: {total_latency:.2f}s)")

            except Exception as e:
                logger.warning(lookup_error("TRANSCRIPTION_FAILED").log_message(e))

    def _check_interrupted_speech(self):
        """Check if the agent was interrupted mid-speech. Returns dict with barge_point and remaining text."""
        try:
            interrupted_file = Path(settings.PROJECT_DIR) / "runtime" / "interrupted_speech.json"
            if not interrupted_file.exists():
                return None

            data = json.loads(interrupted_file.read_text())

            # Only use if recent (within 60 seconds)
            age = time.time() - data.get("timestamp", 0)
            if age > 60:
                interrupted_file.unlink(missing_ok=True)
                return None

            # Consume the file: delete after reading so subsequent messages
            # within the same window don't get falsely tagged as barge-in.
            # The "continue the joke" use case still works because the agent
            # already received the [BARGE-IN POINT: ...] tag in its context.
            interrupted_file.unlink(missing_ok=True)

            # Extract the approximate last words spoken before interruption
            full_text = data.get("full_text", "")
            words = full_text.split()
            total_words = data.get("total_words", len(words))
            words_spoken = min(data.get("words_spoken_estimate", 0), len(words))

            # If user heard nearly all of it, this isn't a real barge-in —
            # the user responded right at the tail end of the agent finishing.
            # The 50ms polling in play_file can catch user speech in the last
            # moments of playback even when the user waited for the agent.
            # 90% threshold with 3-word floor accounts for WPM estimation error.
            near_complete = max(total_words - 3, int(total_words * 0.90))
            if total_words > 0 and words_spoken >= near_complete:
                print(f"\n🔇 Near-complete playback ({words_spoken}/{total_words} words) — not a barge-in")
                return None

            if words_spoken <= 0 and words:
                barge_point = words[0]
            elif words_spoken <= 5:
                barge_point = " ".join(words[:words_spoken])
            else:
                # Last ~5 words at the cutoff point
                barge_point = " ".join(words[words_spoken - 5:words_spoken])

            # Everything the user didn't hear — preserve paragraph structure.
            # Reconstruct from full_text using character offset so newlines survive.
            if words_spoken < len(words):
                # Find where the Nth word starts in the original text
                offset = 0
                for _ in range(words_spoken):
                    offset = full_text.index(words[_], offset) + len(words[_])
                remaining = full_text[offset:].lstrip()
            else:
                remaining = ""

            return {"barge_point": barge_point, "remaining": remaining}
        except Exception:
            return None

    def _detect_echo(self, text):
        """Detect if transcription is the agent's own speech picked up by the mic.

        Compares transcribed text against the agent's recent TTS output.
        Only active within a short window after agent finishes speaking.
        """
        last_spoke = self.mouth_monitor.last_speaking_time()
        if last_spoke is None:
            return False

        time_since = time.time() - last_spoke
        if time_since > 5.0:
            self._recent_agent_text = ""
            return False

        # Read what the agent recently said (update cache if non-empty)
        try:
            speech_file = Path(settings.PROJECT_DIR) / "runtime" / "speech_output.txt"
            content = speech_file.read_text().strip()
            if content:
                self._recent_agent_text = content
        except Exception:
            pass

        if not self._recent_agent_text:
            return False

        # Normalize both texts: lowercase, strip punctuation
        norm_text = re.sub(r'[^\w\s]', '', text.lower()).strip()
        norm_agent = re.sub(r'[^\w\s]', '', self._recent_agent_text.lower()).strip()

        if not norm_text or not norm_agent:
            return False

        # Exact substring match
        if norm_text in norm_agent:
            return True

        # Word overlap for fuzzy matching (Whisper might misrecognize slightly)
        text_words = norm_text.split()
        if len(text_words) >= 2:
            agent_words = set(norm_agent.split())
            matching = sum(1 for w in text_words if w in agent_words)
            if matching / len(text_words) >= 0.8:
                return True

        return False

    @staticmethod
    def _text_overlap(a: str, b: str) -> float:
        """Word-level Jaccard overlap between two strings (0.0–1.0)."""
        wa = set(a.lower().split())
        wb = set(b.lower().split())
        if not wa or not wb:
            return 0.0
        return len(wa & wb) / len(wa | wb)

    def _write_agent_context(self, temp_reading, barge_data, social_reading=None,
                             pragmatic_reading=None, known_entities=None):
        """Write snapshot files SYNCHRONOUSLY so the agent reads current data.

        Called on the transcription worker thread BEFORE _send_to_openclaw_tui.
        Single write_text() calls are sub-millisecond — no mic timing impact.

        Writes:
          - runtime/conversation_temperature.json (always, now includes social cues)
          - runtime/barge_in_context.json (only when barge_data is active)

        Normal messages do NOT overwrite barge_in_context.json — the previous
        barge-in data persists so the agent can read it for "continue" requests.
        The timestamp field serves as natural expiry.
        """
        runtime_dir = Path(settings.PROJECT_DIR) / "runtime"

        # --- Temperature snapshot (always overwritten) ---
        temp_entry = {
            "timestamp": time.time(),
            "score": temp_reading.score,
            "label": temp_reading.label,
            "key_signal": temp_reading.key_signal,
            "components": temp_reading.components,
            "disposition": self._boldness_label,
            "boldness": self._boldness_value,
            "elaboration": self._compute_elaboration_label(temp_reading.score),
            "elaboration_level": self._compute_elaboration_level(temp_reading.score),
            "recent_correction": temp_reading.recent_correction,
        }

        # --- Response confidence: hybrid min(pragmatic, temperature) ---
        # Must match _make_directedness_decision() so the agent sees the same
        # confidence the pipeline used for its gate decision.
        pragmatic_conf = (1.0 - pragmatic_reading.not_for_me_evidence
                          if pragmatic_reading is not None else 1.0)
        temp_conf = min(1.0, temp_reading.score + 0.3)
        response_confidence = round(min(pragmatic_conf, temp_conf), 2)
        temp_entry["response_confidence"] = response_confidence

        # --- Merge social cues into the same JSON (one file, one read) ---
        if social_reading is not None:
            temp_entry["social"] = {
                "engagement_trend": social_reading.engagement_label,
                "engagement_score": round(social_reading.engagement, 2),
                "rapport_label": social_reading.rapport_label,
                "rapport_score": round(social_reading.rapport, 2),
                "frustration_label": social_reading.frustration_label,
                "frustration_level": round(social_reading.frustration, 2),
                "rhythm_label": social_reading.rhythm_label,
                "social_warmth": round(social_reading.warmth, 2),
                "signal_conflict": social_reading.signal_conflict,
            }
            temp_entry["effective_boldness"] = social_reading.effective_boldness
            temp_entry["effective_disposition"] = social_reading.effective_disposition
            temp_entry["disposition_blend"] = social_reading.disposition_blend
            temp_entry["lifespan"] = {
                "total_sessions": social_reading.lifespan_sessions,
                "competence_ratio": round(social_reading.competence_ratio, 2),
                "engagement_style": social_reading.engagement_style,
                "rapport_baseline": round(social_reading.rapport_baseline, 2),
            }

        # --- Merge pragmatic coherence analysis ---
        if pragmatic_reading is not None:
            temp_entry["context_analysis"] = {
                "not_for_me_evidence": round(pragmatic_reading.not_for_me_evidence, 2),
                "topic_continuity": round(pragmatic_reading.topic_continuity, 2),
                "register_shift": pragmatic_reading.register_shift,
                "greeting_mid_conversation": pragmatic_reading.greeting_mid_conversation,
                "suspicion_reasons": pragmatic_reading.suspicion_reasons,
                "known_entities": known_entities or [],
            }

        try:
            (runtime_dir / "conversation_temperature.json").write_text(json.dumps(temp_entry))
        except Exception as e:
            logger.debug(f"Failed to write temperature file: {e}")

        # --- Barge-in snapshot (only when active — don't stomp previous data) ---
        if barge_data:
            barge_entry = {
                "timestamp": time.time(),
                "active": True,
                "barge_point": barge_data["barge_point"],
                "remaining": barge_data.get("remaining", ""),
            }
            try:
                (runtime_dir / "barge_in_context.json").write_text(json.dumps(barge_entry))
            except Exception as e:
                logger.debug(f"Failed to write barge-in context file: {e}")

    def _write_session_logs(self, temp_reading, barge_data, social_reading=None,
                            pragmatic_reading=None):
        """Append to session archive files (async via _io_queue — agent never reads these)."""
        runtime_dir = Path(settings.PROJECT_DIR) / "runtime"

        # --- Temperature + social + pragmatic session archive ---
        temp_entry = {
            "timestamp": time.time(),
            "score": temp_reading.score,
            "label": temp_reading.label,
            "key_signal": temp_reading.key_signal,
            "components": temp_reading.components,
        }
        if social_reading is not None:
            temp_entry["social"] = {
                "engagement": round(social_reading.engagement, 2),
                "rapport": round(social_reading.rapport, 2),
                "frustration": round(social_reading.frustration, 2),
                "rhythm": round(social_reading.rhythm, 2),
                "warmth": round(social_reading.warmth, 2),
                "effective_boldness": social_reading.effective_boldness,
            }
        if pragmatic_reading is not None:
            temp_entry["pragmatic"] = {
                "not_for_me": round(pragmatic_reading.not_for_me_evidence, 2),
                "topic_continuity": round(pragmatic_reading.topic_continuity, 2),
                "reasons": pragmatic_reading.suspicion_reasons,
            }
        try:
            with open(runtime_dir / "session_temperature_log.jsonl", "a") as f:
                f.write(json.dumps(temp_entry) + "\n")
        except Exception as e:
            logger.debug(f"Failed to append temperature log: {e}")

        # --- Barge-in session archive (only when active) ---
        if barge_data:
            barge_entry = {
                "timestamp": time.time(),
                "active": True,
                "barge_point": barge_data["barge_point"],
                "remaining": barge_data.get("remaining", ""),
            }
            try:
                with open(runtime_dir / "session_barge_in_log.jsonl", "a") as f:
                    f.write(json.dumps(barge_entry) + "\n")
            except Exception as e:
                logger.debug(f"Failed to append barge-in log: {e}")

    def _write_correction_trace(self, corrected_utterance, correction_text,
                                temp_reading, pragmatic_reading, entity_match):
        """Append correction trace for offline false-positive analysis."""
        runtime_dir = Path(settings.PROJECT_DIR) / "runtime"
        trace = {
            "timestamp": time.time(),
            "corrected_utterance": corrected_utterance,
            "correction_text": correction_text,
            "temperature": {
                "score": temp_reading.score,
                "label": temp_reading.label,
                "components": temp_reading.components,
            },
            "outcome": "false_positive",
        }
        if pragmatic_reading is not None:
            trace["pragmatic_signals"] = {
                "not_for_me_evidence": round(pragmatic_reading.not_for_me_evidence, 2),
                "reasons": pragmatic_reading.suspicion_reasons,
                "topic_continuity": round(pragmatic_reading.topic_continuity, 2),
                "register_shift": pragmatic_reading.register_shift,
            }
        if entity_match:
            trace["entity_match"] = entity_match
        try:
            with open(runtime_dir / "correction_trace.jsonl", "a") as f:
                f.write(json.dumps(trace) + "\n")
        except Exception:
            pass  # Best-effort trace — don't disrupt pipeline

    def _is_agent_processing(self):
        """Check if the agent is still processing our last message (thinking, not yet speaking)."""
        if not self._awaiting_response:
            return False
        # Agent currently speaking (or in cooldown)
        if self.mouth_monitor.is_agent_speaking():
            self._awaiting_response = False
            self.conversation_temp.record_agent_response()
            return False
        # Agent finished speaking since we sent our message
        # (catches the case where mouth spoke and stopped before the next transcription)
        last_spoke = self.mouth_monitor.last_speaking_time()
        if last_spoke and last_spoke > self._last_sent_time:
            self._awaiting_response = False
            self.conversation_temp.record_agent_response()
            return False
        # Timeout — agent truly never responded
        if time.time() - self._last_sent_time > 15:
            self._awaiting_response = False
            self.conversation_temp.record_agent_silence()
            return False
        return True

    def _cancel_agent_generation(self):
        """Send Escape to TUI to cancel current agent generation (best-effort).

        When the user speaks a second message while the agent is still
        processing the first, we cancel the stale generation so the agent
        sees both messages in context and responds to both at once.
        """
        import subprocess as _sp

        if self._compiled_cancel_script:
            try:
                _sp.Popen(
                    ['osascript', self._compiled_cancel_script],
                    stdout=_sp.DEVNULL, stderr=_sp.DEVNULL,
                )
            except Exception as e:
                logger.warning(lookup_error("AGENT_CANCEL_FAILED").log_message(e))
        else:
            # Fallback: inline AppleScript (blocking)
            window_pattern = settings.TARGET_WINDOW_PATTERN
            applescript = f'''
tell application "Terminal"
    set foundWindow to missing value
    set searchPattern to "{window_pattern}"
    if searchPattern is not "" then
        repeat with w in windows
            if name of w contains searchPattern then
                set foundWindow to w
                exit repeat
            end if
        end repeat
    end if
    if foundWindow is missing value and (count of windows) > 0 then
        set foundWindow to front window
    end if
    if foundWindow is not missing value then
        do script (ASCII character 27) in (selected tab of foundWindow)
    end if
end tell
'''
            try:
                _sp.run(['osascript', '-e', applescript],
                        capture_output=True, text=True, timeout=2)
            except Exception as e:
                logger.warning(lookup_error("AGENT_CANCEL_FAILED").log_message(e))

        # Truncate speech output to prevent stale responses from bleeding through.
        # This also serves as the "all clear" signal for Mouth to resume synthesis.
        try:
            speech_file = Path(settings.PROJECT_DIR) / "runtime" / "speech_output.txt"
            speech_file.write_text("")
        except Exception:
            pass

        # Let Terminal settle after cancellation before sending new text.
        # Without this delay, the new text can arrive before the Escape is
        # processed, causing a "(no output)" artifact in the session log.
        time.sleep(0.3)

    def _send_to_openclaw_tui(self, text):
        """
        Send transcribed text directly to OpenClaw TUI.

        Uses pre-compiled AppleScript with non-blocking Popen for minimal latency.
        Falls back to inline AppleScript or pyautogui if needed.
        """
        import subprocess as _sp

        # Check if the last osascript delivery failed (error detection for fire-and-forget)
        if self._last_osascript_proc is not None:
            retcode = self._last_osascript_proc.poll()
            if retcode is not None and retcode != 0:
                logger.warning(lookup_error("TUI_DELIVERY_FAILED").log_message(RuntimeError(f"exit code {retcode}")))

        # Fast path: pre-compiled script, non-blocking
        if self._compiled_send_script:
            try:
                self._last_osascript_proc = _sp.Popen(
                    ['osascript', self._compiled_send_script, text],
                    stdout=_sp.DEVNULL, stderr=_sp.DEVNULL,
                )
                logger.debug(f"Sent to TUI: {text}")
                return
            except Exception as e:
                logger.warning(lookup_error("TUI_DELIVERY_FAILED").log_message(e))

        # Slow path: inline AppleScript (blocking fallback)
        escaped_text = (text
            .replace('\\', '\\\\')
            .replace('"', '\\"')
            .replace('|', '\\|')
            .replace('$', '\\$')
            .replace('`', '\\`')
            .replace('!', '\\!')
        )
        window_pattern = settings.TARGET_WINDOW_PATTERN
        applescript = f'''
tell application "Terminal"
    set foundWindow to missing value
    set searchPattern to "{window_pattern}"
    if searchPattern is not "" then
        repeat with w in windows
            if name of w contains searchPattern then
                set foundWindow to w
                exit repeat
            end if
        end repeat
    end if
    if foundWindow is missing value and (count of windows) > 0 then
        set foundWindow to front window
    end if
    if foundWindow is not missing value then
        do script "{escaped_text}" in (selected tab of foundWindow)
    end if
end tell
'''
        try:
            result = _sp.run(['osascript', '-e', applescript],
                             capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                logger.debug(f"Sent to TUI (inline): {text}")
                return
            else:
                logger.warning(lookup_error("TUI_DELIVERY_FAILED").log_message(RuntimeError(result.stderr.strip())))
        except _sp.TimeoutExpired:
            logger.warning(lookup_error("TUI_DELIVERY_TIMEOUT").log_message())
        except Exception as e:
            logger.warning(lookup_error("TUI_DELIVERY_FAILED").log_message(e))

        # Last resort: pyautogui (types into focused window)
        try:
            import pyautogui
            time.sleep(0.05)
            pyautogui.write(text, interval=0)
            time.sleep(0.05)
            pyautogui.press('enter')
            logger.debug(f"Typed into focused window (fallback): {text}")
        except ImportError:
            logger.error(lookup_error("TUI_ALL_METHODS_FAILED").log_message())
        except Exception as e:
            logger.warning(lookup_error("TUI_TYPING_FAILED").log_message(e))

    def _generate_agent_response(self, transcription):
        """
        Generate agent response to transcription
        Placeholder - integrate with your OpenClaw agent here
        """
        # TODO: Integrate with OpenClaw agent
        # For now, just echo back with confirmation
        return f"Received: {transcription}"

    def _tts_worker(self):
        """Process TTS queue (if enabled)"""
        if not self.enable_tts:
            return

        import asyncio

        async def speak(text):
            """Speak text using edge-tts"""
            try:
                # Set speaking flag to prevent echo
                self.is_speaking_tts = True

                output_file = self.output_dir / f"tts_{int(time.time())}.mp3"
                communicate = self.edge_tts.Communicate(text, "en-US-ChristopherNeural")
                await communicate.save(str(output_file))

                # Play audio (requires pygame or similar)
                # For now, just save the file
                print(f"\n🔊 TTS saved to: {output_file}")

                # TODO: Add actual playback here
                # When playback completes, clear the flag
                # For now, wait estimated duration
                await asyncio.sleep(len(text) * 0.1)  # Rough estimate

            except Exception as e:
                logger.warning(lookup_error("TTS_SYNTHESIS_FAILED").log_message(e))
            finally:
                # Always clear speaking flag when done
                self.is_speaking_tts = False

        while self.running:
            try:
                text = self.tts_queue.get(timeout=0.5)
                asyncio.run(speak(text))
            except queue.Empty:
                continue

    def start(self):
        """Start ultra-fast voice pipeline.

        Opens the microphone FIRST, then loads heavy resources (Whisper model,
        AppleScript) in a background thread. The mic is capturing audio within
        milliseconds of calling start(), so the user can speak immediately.
        """
        self.running = True

        # ---- MIC FIRST: open audio stream before anything else ----
        self._stream = sd.InputStream(
            channels=1,
            samplerate=self.sample_rate,
            blocksize=int(self.sample_rate * 0.03),
            callback=self._audio_callback
        )
        self._stream.start()
        print("🎙️  Microphone live — listening")

        # Start capture + display threads (only need mic + amplitude, no Whisper)
        if self.mouth_monitor.is_available():
            self.mouth_monitor.start()
        threading.Thread(target=self._display_loop, daemon=True).start()
        threading.Thread(target=self._capture_loop, daemon=True).start()

        # Load heavy stuff in background (Whisper model, AppleScript compilation)
        threading.Thread(target=self._deferred_init, daemon=True).start()

        # Transcription worker waits for _ready event before processing
        threading.Thread(target=self._transcription_worker, daemon=True).start()

        # TTS worker (if enabled)
        if self.enable_tts:
            threading.Thread(target=self._tts_worker, daemon=True).start()

        print(f"📡 {self.sample_rate}Hz | threshold {self.speech_threshold} | silence {self.silence_duration}s")
        print("Press Ctrl+C to stop")

        try:
            while self.running:
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n\n⏹️  Shutting down OpenClaw Ears...")
            self.running = False
            self._stream.stop()
            self._stream.close()
            if self.mouth_monitor:
                self.mouth_monitor.stop()
            time.sleep(0.5)
            print("✅ Shutdown complete")


def main():
    """Run ultra-fast voice pipeline"""
    import argparse

    parser = argparse.ArgumentParser(description='OpenClaw Ears Ultra Fast Voice Pipeline')
    parser.add_argument('--model', default='tiny', help='Whisper model size (tiny recommended)')
    parser.add_argument('--threshold', type=int, default=500, help='Speech threshold')
    parser.add_argument('--silence', type=float, default=1.1, help='Silence duration before submitting (1.1s = fast response)')
    parser.add_argument('--tts', action='store_true', help='Enable TTS responses')

    args = parser.parse_args()

    pipeline = UltraFastVoicePipeline(
        model_size=args.model,
        speech_threshold=args.threshold,
        silence_duration=args.silence,
        enable_tts=args.tts
    )

    pipeline.start()


if __name__ == '__main__':
    main()