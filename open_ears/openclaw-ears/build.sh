#!/bin/bash

# Exit on any error
set -e

# Ensure we're in the correct directory
cd "$(dirname "$0")"

# Create a virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Upgrade pip and setuptools
pip install --upgrade pip setuptools wheel

# Install system dependencies
brew install portaudio  # Required for PyAudio

# Install Python dependencies
pip install \
    pyaudio \
    numpy \
    scipy \
    torch \
    git+https://github.com/openai/whisper.git \
    webrtcvad

# Install the local package in editable mode
pip install -e .

# Run basic tests
python3 -m unittest discover tests

echo "OpenClaw Ears extension built successfully!"