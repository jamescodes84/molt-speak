"""Main TTS pipeline orchestrating all components."""

import asyncio
import logging
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
from ..services.audio_playback import AudioPlayer
from ..services.ears_status_monitor import EarsStatusMonitor
from ..services.text_monitor import TextMonitor
from ..services.tts_service import TTSService
from ..services.tts_factory import TTSFactory
from ..utils.openclaw_notifier import OpenClawNotifier
from ..utils.logging_utils import log_speaking, log_queued, log_error
from ...src.config.config_manager import ConfigManager

logger = logging.getLogger(__name__)


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
        enable_control: bool = False
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
        """
        # Configuration
        self.voice = voice or settings.DEFAULT_VOICE
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
            # Load config to determine TTS provider
            config = ConfigManager()
            provider = config.tts_provider

            if provider == "elevenlabs":
                # Create ElevenLabs TTS service
                api_key = config.elevenlabs_api_key
                if not api_key:
                    logger.warning("ElevenLabs API key not configured. Falling back to Edge-TTS. Run 'molt-speak elo' to configure.")
                    provider = "edge-tts"
                else:
                    self.tts_service = TTSFactory.create_tts_service(
                        provider="elevenlabs",
                        voice=config.elevenlabs_voice_id,
                        api_key=api_key,
                        model=config.elevenlabs_model
                    )
                    logger.info(f"Using ELEVENLABS TTS (Voice ID: {config.elevenlabs_voice_id})")

            if provider == "edge-tts":
                # Create Edge-TTS service
                self.tts_service = TTSFactory.create_tts_service(
                    provider="edge-tts",
                    voice=self.voice,
                    rate=self.rate,
                    volume=self.volume
                )
                logger.info("Using CLOUD TTS (Edge-TTS)")

        self.audio_player = AudioPlayer()
        self.notifier = OpenClawNotifier()

        # Ears status monitor - detect when user speaks to enable barge-in
        self.ears_monitor = EarsStatusMonitor()
        self.barge_in_triggered = False

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

                    success = self.tts_service.synthesize_direct(
                        text,
                        interrupt_check=self.ears_monitor.is_user_speaking
                    )

                    if success:
                        self.state_manager.increment_spoken()
                        logger.info(f"Finished speaking: {text[:50]}...")
                    elif self.tts_service._interrupted:
                        logger.info(f"Barge-in: stopped speaking: {text[:50]}...")
                    else:
                        logger.error(f"Direct speech failed for: {text[:50]}...")

                    # Immediately return to idle
                    self.state_manager.set_idle()
                    self.notifier.notify_idle()

                    self.text_queue.task_done()
                else:
                    # Cloud TTS - use streaming synthesis with file queue
                    suffix = ".mp3"
                    with tempfile.NamedTemporaryFile(
                        suffix=suffix,
                        delete=False
                    ) as tmp_file:
                        tmp_path = Path(tmp_file.name)

                    loop.run_until_complete(
                        self.tts_service.synthesize_streaming(text, tmp_path)
                    )

                    # Update progress
                    self.state_manager.update_progress(0.5)

                    # Queue for playback
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

                log_speaking(logger, text)

                # Update state
                self.state_manager.set_speaking(text, progress=0.75)
                self.notifier.notify_speaking(text)

                # Play audio with barge-in support (stops if user speaks)
                success = self.audio_player.play_file(
                    audio_path,
                    interrupt_check=self.ears_monitor.is_user_speaking
                )

                if success:
                    self.state_manager.increment_spoken()
                    logger.info(f"Finished speaking: {text[:50]}...")
                elif self.audio_player._interrupted:
                    logger.info(f"Barge-in: stopped speaking: {text[:50]}...")
                else:
                    logger.error(f"Failed to play audio for: {text[:50]}...")

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
                logger.error("TTS voice test failed!")
                return

            logger.info("Voice test passed ✓")

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

            # Start threads
            threads_config = [
                ("Monitor", self._monitor_loop),
                ("Synthesis", self._synthesis_loop),
                ("Playback", self._playback_loop),
                ("Display", self._display_loop),
            ]

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
                logger.error(f"Voice test failed for: {new_voice}")
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
            logger.error(f"Failed to change voice: {e}")
            return False
