"""
Text-to-Speech using edge-tts (Microsoft's free TTS)
Zero cost, high quality, multiple voices
"""

import asyncio
from pathlib import Path
import tempfile


class EdgeTTSSpeaker:
    """
    Text-to-Speech using Microsoft Edge TTS
    - Free, no API key required
    - High quality voices
    - Multiple languages and accents
    """

    # Popular voices
    VOICES = {
        # US English
        'us_male': 'en-US-ChristopherNeural',
        'us_female': 'en-US-JennyNeural',
        'us_male_casual': 'en-US-GuyNeural',
        'us_female_friendly': 'en-US-AriaNeural',

        # UK English
        'uk_male': 'en-GB-RyanNeural',
        'uk_female': 'en-GB-SoniaNeural',

        # Australian English
        'au_male': 'en-AU-WilliamNeural',
        'au_female': 'en-AU-NatashaNeural',

        # Other languages
        'es_male': 'es-ES-AlvaroNeural',
        'fr_male': 'fr-FR-HenriNeural',
        'de_male': 'de-DE-ConradNeural',
        'ja_male': 'ja-JP-KeitaNeural',
    }

    def __init__(self, voice='us_male', rate='+0%', volume='+0%', output_dir=None):
        """
        Initialize TTS speaker

        :param voice: Voice name (see VOICES dict) or full voice ID
        :param rate: Speech rate (-50% to +50%, default +0%)
        :param volume: Volume (-50% to +50%, default +0%)
        :param output_dir: Directory to save audio files (default: temp)
        """
        try:
            import edge_tts
            self.edge_tts = edge_tts
        except ImportError:
            raise ImportError(
                "edge-tts not installed. Install with: pip install edge-tts"
            )

        # Resolve voice name
        if voice in self.VOICES:
            self.voice = self.VOICES[voice]
        else:
            self.voice = voice

        self.rate = rate
        self.volume = volume

        if output_dir:
            self.output_dir = Path(output_dir).expanduser()
            self.output_dir.mkdir(parents=True, exist_ok=True)
        else:
            self.output_dir = None

    async def speak_async(self, text, output_file=None):
        """
        Speak text asynchronously

        :param text: Text to speak
        :param output_file: Optional output file path
        :return: Path to audio file
        """
        # Determine output path
        if output_file is None:
            if self.output_dir:
                output_file = self.output_dir / f"tts_{hash(text)}.mp3"
            else:
                # Use temp file (in executor to avoid blocking event loop)
                loop = asyncio.get_running_loop()
                def _make_temp():
                    with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
                        return tmp.name
                output_file = await loop.run_in_executor(None, _make_temp)

        output_file = str(output_file)

        # Generate speech
        communicate = self.edge_tts.Communicate(
            text,
            self.voice,
            rate=self.rate,
            volume=self.volume
        )

        await communicate.save(output_file)
        return output_file

    def speak(self, text, output_file=None):
        """
        Speak text (synchronous wrapper)

        :param text: Text to speak
        :param output_file: Optional output file path
        :return: Path to audio file
        """
        return asyncio.run(self.speak_async(text, output_file))

    async def speak_and_play_async(self, text, output_file=None):
        """
        Speak text and play it immediately

        :param text: Text to speak
        :param output_file: Optional output file path
        """
        audio_file = await self.speak_async(text, output_file)

        # Try to play using available players
        try:
            # Try pygame
            import pygame
            pygame.mixer.init()
            pygame.mixer.music.load(audio_file)
            pygame.mixer.music.play()

            # Wait for playback to finish
            while pygame.mixer.music.get_busy():
                await asyncio.sleep(0.1)

        except ImportError:
            try:
                # Try playsound
                from playsound import playsound
                playsound(audio_file)

            except ImportError:
                # Try system player
                import platform
                system = platform.system()

                if system == 'Darwin':  # macOS
                    try:
                        proc = await asyncio.create_subprocess_exec('afplay', audio_file)
                        await proc.wait()
                    except FileNotFoundError:
                        raise RuntimeError(f"'afplay' not found; cannot play {audio_file}")
                elif system == 'Linux':
                    try:
                        proc = await asyncio.create_subprocess_exec('mpg123', audio_file)
                        await proc.wait()
                    except FileNotFoundError:
                        raise RuntimeError(f"'mpg123' not found; install it to play {audio_file}")
                elif system == 'Windows':
                    import os as _os
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(None, _os.startfile, audio_file)

        return audio_file

    def speak_and_play(self, text, output_file=None):
        """
        Speak text and play it (synchronous wrapper)

        :param text: Text to speak
        :param output_file: Optional output file path
        :return: Path to audio file
        """
        return asyncio.run(self.speak_and_play_async(text, output_file))

    @staticmethod
    async def list_voices_async():
        """List all available voices"""
        import edge_tts  # pylint: disable=import-error
        voices = await edge_tts.VoicesManager.create()
        return voices.voices

    @staticmethod
    def list_voices():
        """List all available voices (synchronous)"""
        return asyncio.run(EdgeTTSSpeaker.list_voices_async())


# Alias for compatibility
TTSSpeaker = EdgeTTSSpeaker


def main():
    """Test the TTS speaker"""
    import time

    print("🔊 Testing Edge TTS Speaker")
    print("=" * 60)

    # Initialize speaker
    speaker = EdgeTTSSpeaker(voice='us_male', output_dir='/tmp/tts_test')
    print(f"✅ Initialized with voice: {speaker.voice}")
    print()

    # Test text
    test_texts = [
        "Hello! I am your AI assistant.",
        "I can now speak as well as listen.",
        "This is powered by Microsoft Edge TTS, completely free."
    ]

    for i, text in enumerate(test_texts, 1):
        print(f"📢 Speaking: \"{text}\"")
        start = time.time()
        audio_file = speaker.speak(text)
        duration = time.time() - start

        print(f"   ✅ Generated in {duration:.2f}s")
        print(f"   💾 Saved to: {audio_file}")
        print()

    print("🎉 TTS test complete!")
    print()
    print("💡 To hear the audio, run:")
    print(f"   afplay {audio_file}")


if __name__ == '__main__':
    main()