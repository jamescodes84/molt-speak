"""Main TTS pipeline orchestrating all components."""

import asyncio
import importlib.util
import json
import logging
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from queue import Queue, Empty
from threading import Thread, Event
from typing import Optional

from ..config import settings
from ..control.control_server import ControlServer
from ..core.state_manager import StateManager
from ..core.terminal_visualizer import TerminalVisualizer
from ..services.audio_playback import AudioPlayer, StreamingAudioPlayer
from ..services.ears_status_monitor import EarsStatusMonitor
from ..services.text_monitor import TextMonitor
from ..services.tts_service import TTSService
from ..services.tts_factory import TTSFactory
from ..utils.openclaw_notifier import OpenClawNotifier
from ..utils.logging_utils import log_speaking, log_queued, log_error

# Load ConfigManager from project root (avoids src package conflict)
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
config_manager_path = PROJECT_ROOT / "src" / "config" / "config_manager.py"
spec = importlib.util.spec_from_file_location("config_manager", config_manager_path)
config_manager_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config_manager_module)
ConfigManager = config_manager_module.ConfigManager

# Load error registry from project root (avoids src package conflict)
_errors_path = PROJECT_ROOT / "src" / "errors.py"
_errors_spec = importlib.util.spec_from_file_location("molt_errors", str(_errors_path))
_errors_mod = importlib.util.module_from_spec(_errors_spec)
_errors_spec.loader.exec_module(_errors_mod)
lookup_error = _errors_mod.lookup_error

logger = logging.getLogger(__name__)

# --- Sentence splitter for TTS pipelining ---
_ABBREV_RE = re.compile(
    r'\b(Mr|Mrs|Ms|Dr|Prof|Sr|Jr|vs|etc|St|Ave|Blvd|U\.S|U\.K)\.',
    re.IGNORECASE
)
_SENTENCE_END_RE = re.compile(r'(?<=[.!?])\s+(?=[A-Z])')
_CLAUSE_RE = re.compile(
    r'(?<=;)\s+|,\s+(?=(?:and|but|or|nor|for|yet|so)\s)',
    re.IGNORECASE
)
_MIN_WORDS = 5
_MAX_CHARS = 300


def _split_into_sentences(text: str) -> list:
    """Split text into sentence-level chunks for TTS pipelining."""
    text = text.strip()
    if not text:
        return []

    # Protect abbreviations from being split
    protected = _ABBREV_RE.sub(lambda m: m.group(0).replace('.', '\x00'), text)
    parts = _SENTENCE_END_RE.split(protected)
    sentences = [p.replace('\x00', '.').strip() for p in parts if p.strip()]

    # Merge short fragments (< 5 words) with neighbors
    merged = []
    buf = ""
    for s in sentences:
        if buf:
            s = buf + " " + s
            buf = ""
        if len(s.split()) < _MIN_WORDS:
            buf = s
        else:
            merged.append(s)
    if buf:
        if merged:
            merged[-1] += " " + buf
        else:
            merged.append(buf)

    # Split long sentences at clause boundaries
    final = []
    for s in (merged or [text]):
        if len(s) > _MAX_CHARS:
            clauses = _CLAUSE_RE.split(s)
            chunk = ""
            for cl in clauses:
                if chunk and len(chunk) + len(cl) + 2 > _MAX_CHARS:
                    final.append(chunk.strip())
                    chunk = cl
                else:
                    chunk = (chunk + " " + cl).strip() if chunk else cl
            if chunk:
                final.append(chunk.strip())
        else:
            final.append(s)

    return final if final else [text]


class MouthPipeline:
    """Main TTS pipeline - the inverse of UltraFastJarvis from OpenClaw Ears."""

    def __init__(
        self,
        voice: Optional[str] = None,
        rate: Optional[float] = None,
        volume: Optional[float] = None,
        input_file: Optional[Path] = None,
        compact_display: bool = False,
        use_local_tts: bool = False,
        enable_control: bool = False,
        analytics=None
    ):
        """
        Initialize the Mouth pipeline.

        Args:
            voice: TTS voice identifier
            rate: Speech rate multiplier
            volume: Volume multiplier
            input_file: Path to input text file
            compact_display: Use compact display mode
            use_local_tts: Use local TTS (macOS 'say') for instant playback
            enable_control: Enable control server for runtime configuration
            analytics: Analytics manager instance
        """
        self.analytics = analytics
        # Load config for voice/provider settings
        config = ConfigManager()

        # Configuration — prefer config's preferred_voice over hardcoded default
        # Explicitly reject empty strings so falsy "" doesn't silently fall through
        _config_voice = config.preferred_voice if config.preferred_voice else None
        self.voice = voice or _config_voice or settings.DEFAULT_VOICE
        self.rate = rate or settings.DEFAULT_RATE
        self.volume = volume or settings.DEFAULT_VOLUME
        self.input_file = input_file or settings.INPUT_FILE
        self.compact_display = compact_display
        self.use_local_tts = use_local_tts
        self.enable_control = enable_control

        # Core components
        self.state_manager = StateManager(voice=self.voice)
        self.visualizer = TerminalVisualizer(enable_colors=settings.ENABLE_COLORS)

        # Initialize TTS service based on mode
        if use_local_tts:
            from ..services.local_tts_service import LocalTTSService
            self.tts_service = LocalTTSService(
                voice=voice or "Alex",
                rate=int(rate * 200) if rate else 200  # Convert to WPM
            )
            logger.info("Using LOCAL TTS for instant playback")
        else:
            # Determine TTS provider from config
            provider = config.tts_provider

            if provider == "elevenlabs":
                # Create ElevenLabs TTS service
                api_key = config.elevenlabs_api_key
                voice_id = config.elevenlabs_voice_id
                model = config.elevenlabs_model
                if not api_key:
                    logger.warning(lookup_error("ELEVENLABS_KEY_MISSING").log_message())
                    provider = "edge-tts"
                else:
                    try:
                        logger.info(f"Creating ElevenLabs TTS with voice_id={voice_id}, model={model}")
                        self.tts_service = TTSFactory.create_tts_service(
                            provider="elevenlabs",
                            voice=voice_id,
                            api_key=api_key,
                            model=model
                        )
                        logger.info(f"Using ELEVENLABS TTS (Voice ID: {voice_id}, Model: {model})")
                    except Exception as e:
                        logger.warning(lookup_error("ELEVENLABS_INIT_FAILED").log_message(e))
                        provider = "edge-tts"

            if provider == "edge-tts":
                # Create Edge-TTS service using config preferred voice
                self.tts_service = TTSFactory.create_tts_service(
                    provider="edge-tts",
                    voice=self.voice,
                    rate=self.rate,
                    volume=self.volume
                )
                logger.info("Using CLOUD TTS (Edge-TTS)")

        self.audio_player = AudioPlayer()
        self.notifier = OpenClawNotifier()

        # Sentence pipelining: split text into sentences, play each via afplay
        # with concurrent prefetch of the next sentence for reduced latency
        self._streaming_enabled = not use_local_tts

        # Ears status monitor - detect when user speaks to enable barge-in
        self.ears_monitor = EarsStatusMonitor()
        self.barge_in_triggered = False

        # Barge-in pause: after barge-in, pause synthesis until Ears truncates
        # speech_output.txt (the "all clear" signal that stale generation is dead)
        self._barge_in_paused = False
        self._barge_in_time = 0.0

        # Control server (if enabled)
        self.control_server = None
        self.voice_config = None
        if enable_control:
            self.control_server = ControlServer(command_handler=self._handle_control_command)
            # Load voice configuration
            from ..config.voice_config import VoiceConfig
            self.voice_config = VoiceConfig()
            logger.info("Voice configuration loaded")

        # Queues
        self.text_queue = Queue(maxsize=settings.MAX_QUEUE_SIZE)
        self.audio_queue = Queue(maxsize=settings.MAX_QUEUE_SIZE)

        # Track queued text items for display
        self.queued_text_items = []
        from threading import Lock as ThreadLock
        self.queued_items_lock = ThreadLock()

        # Text monitor - use watchdog for instant file change detection
        from ..services.text_monitor import TextMonitor
        self.text_monitor = TextMonitor(
            file_path=self.input_file,
            text_queue=self.text_queue,
            monitor_interval=0.02  # Backup poll every 20ms
        )

        # Thread control
        self.running = Event()
        self.threads = []

        logger.info("Mouth pipeline initialized")
        logger.info(f"Voice: {self.voice}")
        logger.info(f"Input file: {self.input_file}")

    def _handle_control_command(self, command: str, args: Optional[str]) -> str:
        """
        Handle control commands from the control server.

        Args:
            command: Command name
            args: Command arguments

        Returns:
            Response string
        """
        from ..control.command_protocol import CommandResponse

        try:
            if command == "GET_STATUS":
                status = self.state_manager.get_status()
                current_text = self.state_manager.get_current_text()
                mode = "local" if self.use_local_tts else "cloud"
                return CommandResponse.ok(f"{status}|{self.voice}|{mode}|{current_text[:50]}")

            elif command == "GET_VOICES":
                # TODO: Implement voice listing
                return CommandResponse.ok("[]")

            elif command == "CHANGE_VOICE":
                if not args:
                    return CommandResponse.error("Missing voice argument")

                parts = args.split(",")
                new_voice = parts[0]
                new_mode = parts[1] if len(parts) > 1 else None

                success = self.change_voice(new_voice, new_mode)
                if success:
                    return CommandResponse.ok(f"Voice changed to {new_voice}")
                else:
                    return CommandResponse.error("Voice change failed")

            elif command == "CHANGE_RATE":
                if not args:
                    return CommandResponse.error("Missing rate argument")

                try:
                    new_rate = float(args)
                    self.rate = new_rate
                    return CommandResponse.ok(f"Rate changed to {new_rate}")
                except ValueError:
                    return CommandResponse.error("Invalid rate value")

            elif command == "CHANGE_VOLUME":
                if not args:
                    return CommandResponse.error("Missing volume argument")

                try:
                    new_volume = float(args)
                    self.volume = new_volume
                    return CommandResponse.ok(f"Volume changed to {new_volume}")
                except ValueError:
                    return CommandResponse.error("Invalid volume value")

            else:
                return CommandResponse.error(f"Unknown command: {command}")

        except Exception as e:
            logger.error(f"Error handling command {command}: {e}")
            return CommandResponse.error(str(e))

    def _save_interrupted_speech(self, text: str, start_time: float,
                                audio_seconds: float = 0.0) -> None:
        """Save interrupted speech to file so the agent can resume later."""
        try:
            elapsed = audio_seconds if audio_seconds > 0 else (time.time() - start_time)
            words = text.split()
            # Edge-TTS speaks at ~180 WPM (3.0 words/sec) — faster than the
            # 150 WPM (2.5 w/s) we assumed before.  Use the higher rate so
            # the barge_point lands closer to where playback actually was.
            words_spoken = min(int(elapsed * 3.0), len(words))

            data = {
                "timestamp": time.time(),
                "full_text": text,
                "elapsed_seconds": round(elapsed, 2),
                "words_spoken_estimate": words_spoken,
                "total_words": len(words),
            }

            interrupted_file = settings.RUNTIME_DIR / "interrupted_speech.json"
            interrupted_file.write_text(json.dumps(data))
            logger.info(f"Saved interrupted speech ({words_spoken}/{len(words)} words spoken)")
        except Exception as e:
            logger.warning(f"Failed to save interrupted speech: {e}")

    def _peek_queue_texts(self, q: Queue) -> list:
        """Return all text items currently in the queue WITHOUT removing them."""
        texts = []
        with q.mutex:
            for item in list(q.queue):
                if isinstance(item, str):
                    texts.append(item)
        return texts

    def _drain_queue(self, q: Queue, cleanup_files: bool = False) -> None:
        """Drain a queue to prevent stale items from playing after barge-in."""
        while not q.empty():
            try:
                item = q.get_nowait()
                if cleanup_files and isinstance(item, tuple) and len(item) == 2:
                    _, path = item
                    try:
                        Path(path).unlink(missing_ok=True)
                    except Exception:
                        pass
                q.task_done()
            except Empty:
                break

    async def _synthesize_sentence(self, sentence: str) -> Path:
        """Synthesize a single sentence to a temp MP3 file for playback."""
        loop = asyncio.get_running_loop()

        def _make_temp():
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                return f.name

        tmp_path = Path(await loop.run_in_executor(None, _make_temp))
        try:
            await self.tts_service.synthesize_streaming(sentence, tmp_path)
        except Exception as e:
            # If ElevenLabs fails mid-session, fall back to Edge-TTS
            if not isinstance(self.tts_service, TTSService):
                logger.warning(lookup_error("ELEVENLABS_SYNTHESIS_FAILED").log_message(e))
                self.tts_service = TTSFactory.create_tts_service(
                    provider="edge-tts",
                    voice=self.voice,
                    rate=self.rate,
                    volume=self.volume
                )
                await self.tts_service.synthesize_streaming(sentence, tmp_path)
            else:
                raise
        return tmp_path

    def _decode_mp3_to_pcm(self, mp3_path: Path) -> bytes:
        """Decode an MP3 file to raw 24kHz mono int16 PCM via ffmpeg."""
        proc = subprocess.run(
            ["ffmpeg", "-y", "-i", str(mp3_path),
             "-f", "s16le", "-acodec", "pcm_s16le",
             "-ar", "24000", "-ac", "1", "pipe:1"],
            capture_output=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg decode failed: {proc.stderr[:200]}")
        return proc.stdout

    async def _stream_and_play(self, text: str) -> bool:
        """
        Play text with sentence-level pipelining and gapless audio.

        Uses a single continuous StreamingAudioPlayer (sounddevice) stream.
        Each sentence's MP3 is decoded to PCM and fed into the same stream,
        so there is zero gap between sentences — no subprocess startup overhead.
        Prefetches next sentence during current sentence's playback.
        """
        sentences = _split_into_sentences(text)
        if not sentences:
            return True

        prefetch_task = None
        playback_start = None
        interrupted = False
        loop = asyncio.get_running_loop()
        player = StreamingAudioPlayer(
            sample_rate=24000, channels=1,
            interrupt_check=self.ears_monitor.is_user_speaking,
        )

        try:
            log_speaking(logger, text)
            self.notifier.notify_speaking(text)

            player.start_stream()
            # Record playback start immediately — the stream is live and
            # the callback will begin outputting audio as soon as we feed.
            # Setting this early ensures _save_interrupted_speech always
            # has a valid start time, even if the callback fires a barge-in
            # before we finish decoding the first sentence.
            playback_start = time.time()

            def _barge_detected():
                """Check monitor OR callback-fired interrupt."""
                return self.ears_monitor.is_user_speaking() or player._interrupted_flag

            for i, sentence in enumerate(sentences):
                # Check barge-in between sentences
                if _barge_detected():
                    interrupted = True
                    break

                # Get MP3 for this sentence
                if i == 0:
                    tmp_path = await self._synthesize_sentence(sentence)
                elif prefetch_task:
                    tmp_path = await prefetch_task
                    prefetch_task = None
                else:
                    tmp_path = await self._synthesize_sentence(sentence)

                # Check barge-in after synthesis
                if _barge_detected():
                    tmp_path.unlink(missing_ok=True)
                    interrupted = True
                    break

                # Start prefetch of next sentence (runs during decode+playback)
                if i + 1 < len(sentences):
                    prefetch_task = asyncio.create_task(
                        self._synthesize_sentence(sentences[i + 1])
                    )

                # Decode MP3 → PCM and feed into the continuous stream
                try:
                    pcm_data = await loop.run_in_executor(
                        None, self._decode_mp3_to_pcm, tmp_path
                    )
                    # Don't feed a dead stream — break immediately
                    if player._interrupted_flag:
                        interrupted = True
                        break
                    player.feed(pcm_data)
                finally:
                    try:
                        tmp_path.unlink(missing_ok=True)
                    except Exception:
                        pass

            # Signal no more audio data
            player.mark_finished()

            # Wait for playback to complete, polling for barge-in
            while not player._done.is_set():
                if _barge_detected():
                    player.interrupt()
                    interrupted = True
                    break
                await asyncio.sleep(0.02)

            if not interrupted:
                # Wait for final drain
                await loop.run_in_executor(None, player.wait_until_done, 30.0)
                if player._interrupted_flag:
                    interrupted = True

            if interrupted:
                if playback_start:
                    # Collect queued text BEFORE draining so the full_text
                    # includes everything the user never heard (current chunk
                    # remainder + all subsequent queued chunks).
                    queued_texts = self._peek_queue_texts(self.text_queue)
                    full_text = text
                    if queued_texts:
                        full_text = text + "\n\n" + "\n\n".join(queued_texts)
                    self._save_interrupted_speech(
                        full_text, playback_start,
                        audio_seconds=player.seconds_played,
                    )
                self._drain_queue(self.text_queue)
                self._barge_in_paused = True
                self._barge_in_time = time.time()
                if self.analytics:
                    self.analytics.track_event("tts_barge_in", {
                        "tts_provider": "streaming"
                    })
                return False

            self.state_manager.increment_spoken()
            logger.info(f"Finished speaking ({len(sentences)} sentences): {text[:50]}...")

            if self.analytics:
                self.analytics.track_voice_interaction("synthesis_streaming",
                    text_length=len(text),
                    word_count=len(text.split()),
                    voice=self.voice,
                    tts_provider="streaming"
                )
            return True

        except Exception as e:
            logger.error(lookup_error("TTS_PIPELINE_ERROR").log_message(e))
            raise

        finally:
            player.stop()
            if prefetch_task:
                prefetch_task.cancel()
                try:
                    cancelled_path = await prefetch_task
                    cancelled_path.unlink(missing_ok=True)
                except Exception:
                    pass

    def _monitor_loop(self) -> None:
        """
        Monitor for new text (Thread 1).

        This thread watches the text queue filled by the file monitor.
        """
        logger.info("Monitor loop started")

        while self.running.is_set():
            try:
                # Update queue size in state
                queue_size = self.text_queue.qsize()
                self.state_manager.update_queue_size(queue_size)

                # Peek at queue items for display (using internal deque)
                # This allows us to show what's queued without removing items
                queued_items = []
                with self.text_queue.mutex:
                    queued_items = list(self.text_queue.queue)[:3]  # Get first 3 items
                self.state_manager.update_queued_items(queued_items)

                if queue_size > 0:
                    self.state_manager.set_queued(queue_size)
                    self.notifier.notify_queued(queue_size)
                elif self.state_manager.get_status() == "QUEUED":
                    self.state_manager.set_idle()
                    self.notifier.notify_idle()

                time.sleep(0.1)

            except Exception as e:
                log_error(logger, e, "monitor loop")

        logger.info("Monitor loop stopped")

    def _synthesis_loop(self) -> None:
        """
        Synthesize queued text (Thread 2).

        This thread takes text from the text queue, synthesizes it to audio,
        and puts the audio file path in the audio queue.
        """
        logger.info("Synthesis loop started")

        # Create event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        while self.running.is_set():
            try:
                # Get text from queue (blocking with timeout)
                try:
                    text = self.text_queue.get(timeout=0.5)
                except Empty:
                    continue

                # Barge-in pause gate: discard stale text until Ears signals all-clear
                if self._barge_in_paused:
                    # Safety timeout — auto-release after 8 seconds
                    if time.time() - self._barge_in_time > 8.0:
                        logger.info("Barge-in pause timeout (8s) — resuming synthesis")
                        self._barge_in_paused = False
                    else:
                        # Check if speech file was truncated (Ears "all clear" signal)
                        try:
                            speech_size = (settings.RUNTIME_DIR / "speech_output.txt").stat().st_size
                            if speech_size == 0:
                                logger.info("Speech file truncated — barge-in pause cleared")
                                self._barge_in_paused = False
                                self._drain_queue(self.text_queue)
                        except Exception:
                            pass

                    if self._barge_in_paused:
                        logger.info(f"Discarding stale text during barge-in pause: {text[:50]}...")
                        self.text_queue.task_done()
                        continue

                log_queued(logger, text)

                # Update state
                self.state_manager.set_speaking(text, progress=0.0)

                # Synthesize and speak
                if self.use_local_tts:
                    # Local TTS - DIRECT SPEECH for INSTANT playback
                    # No file generation, no audio queue - speak immediately
                    # Supports barge-in via ears_monitor
                    log_speaking(logger, text)
                    self.notifier.notify_speaking(text)

                    speech_start = time.time()
                    success = self.tts_service.synthesize_direct(
                        text,
                        interrupt_check=self.ears_monitor.is_user_speaking
                    )

                    if success:
                        self.state_manager.increment_spoken()
                        logger.info(f"Finished speaking: {text[:50]}...")

                        # Track successful TTS synthesis
                        if self.analytics:
                            self.analytics.track_voice_interaction("synthesis_local",
                                text_length=len(text),
                                word_count=len(text.split()),
                                voice=self.voice,
                                tts_provider="local"
                            )
                    elif self.tts_service._interrupted:
                        logger.info(f"Barge-in: stopped speaking: {text[:50]}...")
                        queued_texts = self._peek_queue_texts(self.text_queue)
                        full_text = text
                        if queued_texts:
                            full_text = text + "\n\n" + "\n\n".join(queued_texts)
                        self._save_interrupted_speech(full_text, speech_start)
                        self._drain_queue(self.text_queue)
                        self._barge_in_paused = True
                        self._barge_in_time = time.time()

                        # Track barge-in
                        if self.analytics:
                            self.analytics.track_event("tts_barge_in", {
                                "tts_provider": "local"
                            })
                    else:
                        logger.error(lookup_error("TTS_DIRECT_SPEECH_FAILED").log_message(RuntimeError(f"text: {text[:50]}...")))

                    # Immediately return to idle
                    self.state_manager.set_idle()
                    self.notifier.notify_idle()

                    self.text_queue.task_done()
                elif self._streaming_enabled:
                    # Sentence pipelining — split text, play each via afplay with barge-in
                    loop.run_until_complete(self._stream_and_play(text))

                    self.state_manager.set_idle()
                    self.notifier.notify_idle()
                    self.text_queue.task_done()
                else:
                    # Fallback: file-based synthesis + audio_queue + afplay
                    with tempfile.NamedTemporaryFile(
                        suffix=".mp3",
                        delete=False
                    ) as tmp_file:
                        tmp_path = Path(tmp_file.name)

                    try:
                        loop.run_until_complete(
                            self.tts_service.synthesize_streaming(text, tmp_path)
                        )
                    except Exception as synth_err:
                        if not isinstance(self.tts_service, TTSService):
                            logger.warning(f"ElevenLabs synthesis failed: {synth_err}. Falling back to Edge-TTS.")
                            self.tts_service = TTSFactory.create_tts_service(
                                provider="edge-tts",
                                voice=self.voice,
                                rate=self.rate,
                                volume=self.volume
                            )
                            loop.run_until_complete(
                                self.tts_service.synthesize_streaming(text, tmp_path)
                            )
                        else:
                            raise

                    self.state_manager.update_progress(0.5)
                    self.audio_queue.put((text, tmp_path))
                    self.text_queue.task_done()

            except Exception as e:
                log_error(logger, e, "synthesis loop")
                self.state_manager.set_error(str(e))
                self.notifier.notify_error(str(e))

        loop.close()
        logger.info("Synthesis loop stopped")

    def _playback_loop(self) -> None:
        """
        Play synthesized audio (Thread 3).

        This thread takes audio files from the audio queue and plays them.
        """
        logger.info("Playback loop started")

        while self.running.is_set():
            try:
                # Get audio from queue (blocking with timeout)
                try:
                    text, audio_path = self.audio_queue.get(timeout=0.5)
                except Empty:
                    continue

                # Barge-in pause gate: discard stale audio from synthesis pipeline
                if self._barge_in_paused:
                    logger.info(f"Discarding stale audio during barge-in pause: {text[:50]}...")
                    try:
                        audio_path.unlink(missing_ok=True)
                    except Exception:
                        pass
                    self.audio_queue.task_done()
                    continue

                log_speaking(logger, text)

                # Update state
                self.state_manager.set_speaking(text, progress=0.75)
                self.notifier.notify_speaking(text)

                # Play audio with barge-in support (stops if user speaks)
                playback_start = time.time()
                success = self.audio_player.play_file(
                    audio_path,
                    interrupt_check=self.ears_monitor.is_user_speaking
                )

                if success:
                    self.state_manager.increment_spoken()
                    logger.info(f"Finished speaking: {text[:50]}...")

                    # Track successful TTS synthesis (cloud)
                    if self.analytics:
                        self.analytics.track_voice_interaction("synthesis_cloud",
                            text_length=len(text),
                            word_count=len(text.split()),
                            voice=self.voice,
                            tts_provider="edge-tts"
                        )
                elif self.audio_player._interrupted:
                    logger.info(f"Barge-in: stopped speaking: {text[:50]}...")
                    queued_texts = self._peek_queue_texts(self.text_queue)
                    full_text = text
                    if queued_texts:
                        full_text = text + "\n\n" + "\n\n".join(queued_texts)
                    self._save_interrupted_speech(full_text, playback_start)
                    self._drain_queue(self.text_queue)
                    self._drain_queue(self.audio_queue, cleanup_files=True)
                    self._barge_in_paused = True
                    self._barge_in_time = time.time()

                    # Track barge-in
                    if self.analytics:
                        self.analytics.track_event("tts_barge_in", {
                            "tts_provider": "edge-tts"
                        })
                else:
                    logger.error(lookup_error("TTS_PLAYBACK_FAILED").log_message(RuntimeError(f"text: {text[:50]}...")))

                # Clean up temp file
                try:
                    audio_path.unlink()
                except Exception as e:
                    logger.warning(f"Failed to delete temp file: {e}")

                self.audio_queue.task_done()

                # Immediately update state to idle after playback completes
                # This ensures the visual indicator turns off right away
                # If there are more items in queue, the monitor loop will update to QUEUED
                self.state_manager.set_idle()
                self.notifier.notify_idle()

            except Exception as e:
                log_error(logger, e, "playback loop")
                self.state_manager.set_error(str(e))

        logger.info("Playback loop stopped")

    def _display_loop(self) -> None:
        """
        Update terminal display (Thread 4).

        This thread continuously updates the terminal visualization.
        """
        logger.info("Display loop started")

        while self.running.is_set():
            try:
                state = self.state_manager.get_state()
                self.visualizer.display(state, compact=self.compact_display)
                time.sleep(settings.DISPLAY_UPDATE_RATE)

            except Exception as e:
                log_error(logger, e, "display loop")

        logger.info("Display loop stopped")

    def start(self) -> None:
        """Start the speech system."""
        try:
            # Display startup banner
            self.visualizer.display_startup_banner()

            logger.info("Starting OpenClaw Mouth TTS system...")

            # Test TTS voice
            logger.info("Testing TTS voice...")
            if self.use_local_tts:
                # Local TTS test is synchronous
                voice_ok = self.tts_service.test_voice()
            else:
                # Cloud TTS test is async
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                voice_ok = loop.run_until_complete(self.tts_service.test_voice())
                loop.close()

            if not voice_ok:
                # If using ElevenLabs and voice test fails (e.g. expired API key),
                # fall back to Edge-TTS instead of crashing the entire pipeline
                if not self.use_local_tts and not isinstance(self.tts_service, TTSService):
                    logger.warning(lookup_error("TTS_VOICE_TEST_FAILED").log_message())
                    self.tts_service = TTSFactory.create_tts_service(
                        provider="edge-tts",
                        voice=self.voice,
                        rate=self.rate,
                        volume=self.volume
                    )
                    # Test the fallback
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    voice_ok = loop.run_until_complete(self.tts_service.test_voice())
                    loop.close()

                # If the configured Edge-TTS voice is broken (e.g. deprecated by Microsoft),
                # try known stable fallback voices before giving up entirely
                if not voice_ok and not self.use_local_tts:
                    fallback_voices = ["en-US-AriaNeural", "en-US-ChristopherNeural", "en-US-JennyNeural"]
                    for fallback_voice in fallback_voices:
                        if fallback_voice == self.voice:
                            continue
                        logger.warning(f"Voice '{self.voice}' unavailable. Trying fallback: {fallback_voice}")
                        self.tts_service = TTSFactory.create_tts_service(
                            provider="edge-tts",
                            voice=fallback_voice,
                            rate=self.rate,
                            volume=self.volume
                        )
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        voice_ok = loop.run_until_complete(self.tts_service.test_voice())
                        loop.close()
                        if voice_ok:
                            self.voice = fallback_voice
                            logger.info(f"Using fallback voice: {fallback_voice}")
                            break

                if not voice_ok:
                    logger.error(lookup_error("TTS_ALL_VOICES_FAILED").log_message())
                    return

            logger.info("Voice test passed ✓")

            # Clear stale speech from previous session
            try:
                speech_file = settings.RUNTIME_DIR / "speech_output.txt"
                speech_file.write_text("")
                logger.info("Cleared speech_output.txt (fresh session)")
            except Exception:
                pass

            # Start file monitor
            self.text_monitor.start()

            # Start ears monitor for barge-in support
            self.ears_monitor.start()
            logger.info("Barge-in support enabled (will stop when user speaks)")

            # Start control server if enabled
            if self.control_server:
                if self.control_server.start():
                    logger.info("Control server enabled")
                else:
                    logger.warning("Failed to start control server")

            # Set running flag
            self.running.set()

            # Start threads — skip Playback when streaming handles synthesis + playback
            threads_config = [
                ("Monitor", self._monitor_loop),
                ("Synthesis", self._synthesis_loop),
                ("Display", self._display_loop),
            ]
            if not self._streaming_enabled:
                threads_config.insert(2, ("Playback", self._playback_loop))

            for name, target in threads_config:
                thread = Thread(target=target, name=name, daemon=True)
                thread.start()
                self.threads.append(thread)
                logger.info(f"Started {name} thread")

            logger.info("✅ All systems running")
            logger.info(f"Monitoring: {self.input_file}")
            logger.info("Waiting for text to speak...")

            # Update state
            self.state_manager.set_idle()
            self.notifier.notify_idle()

            # Keep main thread alive
            try:
                while self.running.is_set():
                    time.sleep(1.0)
            except KeyboardInterrupt:
                logger.info("Received keyboard interrupt")
                self.stop()

        except Exception as e:
            log_error(logger, e, "startup")
            raise

    def stop(self) -> None:
        """Stop the speech system gracefully."""
        try:
            logger.info("Shutting down speech system...")

            # Clear running flag
            self.running.clear()

            # Stop text monitor
            self.text_monitor.stop()

            # Clear speech file to prevent stale content on next startup
            try:
                speech_file = settings.RUNTIME_DIR / "speech_output.txt"
                speech_file.write_text("")
            except Exception:
                pass

            # Stop ears monitor
            self.ears_monitor.stop()

            # Stop control server if enabled
            if self.control_server:
                self.control_server.stop()

            # Wait for threads to finish (with timeout)
            for thread in self.threads:
                thread.join(timeout=2.0)
                if thread.is_alive():
                    logger.warning(f"Thread {thread.name} did not stop cleanly")

            # Cleanup
            self.notifier.cleanup()

            # Display shutdown message
            self.visualizer.display_shutdown_message()

            logger.info("Shutdown complete")

        except Exception as e:
            log_error(logger, e, "shutdown")

    def speak_text(self, text: str) -> None:
        """
        Directly queue text for speech (programmatic API).

        Args:
            text: Text to speak
        """
        try:
            if not self.running.is_set():
                logger.warning("System not running, cannot speak")
                return

            self.text_queue.put(text)
            logger.debug(f"Queued text: {text[:50]}...")

        except Exception as e:
            log_error(logger, e, "speak_text")

    def change_voice(self, new_voice: str, new_mode: Optional[str] = None) -> bool:
        """
        Change TTS voice at runtime.

        Args:
            new_voice: New voice identifier
            new_mode: New TTS mode ("local" or "cloud"), None to keep current

        Returns:
            True if voice changed successfully, False otherwise
        """
        try:
            logger.info(f"Changing voice to: {new_voice} (mode: {new_mode})")

            # Determine if we need to change TTS backend
            if new_mode:
                use_local = (new_mode == "local")
            else:
                use_local = self.use_local_tts

            # Wait for queues to drain (with timeout)
            max_wait = 5.0  # seconds
            wait_interval = 0.1
            total_wait = 0.0

            while (self.text_queue.qsize() > 0 or self.audio_queue.qsize() > 0) and total_wait < max_wait:
                time.sleep(wait_interval)
                total_wait += wait_interval

            if total_wait >= max_wait:
                logger.warning("Timeout waiting for queues to drain, forcing voice change")

            # Create new TTS service
            if use_local:
                from ..services.local_tts_service import LocalTTSService
                new_tts_service = LocalTTSService(
                    voice=new_voice,
                    rate=int(self.rate * 200) if self.rate else 200
                )
                logger.info(f"Created local TTS service with voice: {new_voice}")
            else:
                new_tts_service = TTSService(
                    voice=new_voice,
                    rate=self.rate,
                    volume=self.volume
                )
                logger.info(f"Created cloud TTS service with voice: {new_voice}")

            # Test the new voice
            if use_local:
                voice_ok = new_tts_service.test_voice()
            else:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                voice_ok = loop.run_until_complete(new_tts_service.test_voice())
                loop.close()

            if not voice_ok:
                logger.error(lookup_error("TTS_VOICE_TEST_FAILED").log_message(RuntimeError(f"voice: {new_voice}")))
                return False

            # Atomically swap TTS service
            self.tts_service = new_tts_service
            self.voice = new_voice
            self.use_local_tts = use_local

            # Update state manager
            self.state_manager.set_voice(new_voice)

            # Save to config if enabled
            if self.voice_config:
                mode_str = "local" if use_local else "cloud"
                self.voice_config.set_last_voice(new_voice, mode_str)

            logger.info(f"Voice successfully changed to: {new_voice}")
            return True

        except Exception as e:
            logger.error(lookup_error("TTS_VOICE_CHANGE_FAILED").log_message(e))
            return False
