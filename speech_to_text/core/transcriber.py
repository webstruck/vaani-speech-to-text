"""
Transcription functionality for the speech-to-text application.
Handles loading and using the speech recognition model.
"""

import logging
import os
import numpy as np

class Transcriber:
    """Handles speech transcription using the Whisper model."""
    
    def __init__(self, settings):
        """Initialize the transcriber with the given settings."""
        self.logger = logging.getLogger(__name__)
        self.settings = settings
        self.stt_model = None
    
    def load_model(self) -> bool:
        """Load the STT model using faster_whisper."""
        self.logger.info(f"Loading STT model...{self.settings.model_size} on {self.settings.device}")
        try:
            from faster_whisper import WhisperModel
            # Use the device from settings
            device = self.settings.device
            compute_type = "int8"
            
            # Adjust compute type based on device
            if device == "cpu":
                compute_type = "int8"
            elif device == "cuda":
                compute_type = "float16"  # Better precision for GPU
            
            self.stt_model = WhisperModel(
                model_size_or_path=self.settings.model_size,
                device=device,
                compute_type=compute_type,
                download_root=None,
                local_files_only=False,
                num_workers=4
            )
            self.logger.info(f"Model loaded successfully on {device}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to load model: {str(e)}")
            return False
    
    def transcribe(self, audio_data: np.ndarray) -> str:
        """
        Transcribe the given audio data.
        
        Args:
            audio_data: Preprocessed audio data as float32 numpy array
            
        Returns:
            Transcribed text as string
        """
        if self.stt_model is None:
            self.logger.error("Transcription model not loaded")
            return ""
        
        try:
            # Perform transcription
            segments, info = self.stt_model.transcribe(
                audio_data,
                beam_size=5,
                word_timestamps=True,
                language="en",
                vad_filter=True,
                vad_parameters=dict(
                    min_silence_duration_ms=500,
                    speech_pad_ms=400
                )
            )
            
            # Combine segments into text
            text = " ".join(segment.text for segment in segments)
            return text
            
        except Exception as e:
            self.logger.error(f"Error during transcription: {str(e)}")
            return ""