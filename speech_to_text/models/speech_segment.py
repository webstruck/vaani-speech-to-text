"""
Speech segment data model for the speech-to-text application.
"""

from dataclasses import dataclass
import numpy as np
import time

@dataclass
class SpeechSegment:
    """Class to store speech segment data."""
    audio_data: np.ndarray
    sample_rate: int
    timestamp: float  # Capture time
    segment_id: int   # For ordering
    is_processed: bool = False
    transcription: str = ""