from setuptools import setup, find_packages

setup(
    name='openclaw-ears',
    version='0.1.0',
    packages=find_packages(),
    install_requires=[
        'pyaudio',
        'numpy',
        'scipy',
        'openai-whisper',  # Legacy support
        'faster-whisper>=0.10.0',  # Optimized transcription (4x faster)
        'webrtcvad',
        'edge-tts>=6.1.0',  # Free TTS
        'sounddevice>=0.4.5',  # Audio I/O
    ],
    description='OpenClaw voice input extension for AI agents',
    author='OpenClaw Contributors',
    author_email='opensource@openclaw.ai',
    url='https://github.com/openclaw/openclaw-ears',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
    ],
)