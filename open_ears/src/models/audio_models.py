"""
Data models for audio processing.

Pydantic models for request/response validation and data contracts.
"""

# Standard library
from typing import Any, Dict, List, Optional

# Third-party
from pydantic import BaseModel, ConfigDict, Field


class TranscriptionResult(BaseModel):
    """Result from audio transcription."""

    model_config = ConfigDict(frozen=False)

    text: str = Field(..., description="Transcribed text")
    language: str = Field(..., description="Detected or specified language")
    duration: Optional[float] = Field(None, description="Audio duration in seconds")
    confidence: Optional[float] = Field(None, description="Average confidence score")
    segments: List[Dict[str, Any]] = Field(default_factory=list, description="Individual segments with timing")


class TTSRequest(BaseModel):
    """Request for text-to-speech generation."""

    model_config = ConfigDict(frozen=False)

    text: str = Field(..., min_length=1, description="Text to convert to speech")
    voice: str = Field(default="us_male", description="Voice to use")
    rate: str = Field(default="+0%", description="Speech rate adjustment")
    volume: str = Field(default="+0%", description="Volume adjustment")


class TTSResponse(BaseModel):
    """Response from text-to-speech generation."""

    model_config = ConfigDict(frozen=False)

    audio_file: str = Field(..., description="Path to generated audio file")
    duration: Optional[float] = Field(None, description="Audio duration in seconds")
    text: str = Field(..., description="Text that was converted")


class AudioSegment(BaseModel):
    """Captured audio segment."""

    model_config = ConfigDict(frozen=False)

    segment_number: int = Field(..., description="Sequential segment number")
    timestamp: float = Field(..., description="Capture timestamp")
    max_amplitude: float = Field(..., description="Maximum amplitude in segment")
    duration: float = Field(..., description="Segment duration in seconds")
    has_speech: bool = Field(..., description="Whether speech was detected")
