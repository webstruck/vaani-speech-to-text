"""
Audio processing functionality for the speech-to-text application.
Handles audio capture, preprocessing, and analysis.
"""

import numpy as np
import pyaudio
from scipy import signal
import logging
import wave
import os
import speech_to_text.utils.audio_utils as audio_utils

class AudioProcessor:
    """Handles audio capture and processing."""
    # Audio format constants
    AUDIO_FORMAT = pyaudio.paInt16
    AUDIO_CHANNELS = 1
    BUFFER_SIZE = 1024
    BIT_DEPTH_DIVISOR = 32768.0  # Used for normalizing 16-bit audio
    
    # Filter parameters
    DEFAULT_HIGHPASS_CUTOFF = 100  # Hz

    def __init__(self, settings, config_manager=None):
        """Initialize the audio processor with the given settings."""
        self.logger = logging.getLogger(__name__)
        self.settings = settings
        self.config_manager = config_manager
        self.audio = pyaudio.PyAudio()
        self.stream = None
    
    def update_settings(self, settings):
        """Update the settings used by the audio processor."""
        self.settings = settings
    
    def start_stream(self):
        """Start the audio input stream."""
        if self.stream is not None:
            self.stop_stream()
        
        device_index = self.settings.input_device_index
        device_info = "System Default"
        if device_index is not None:
            try:
                # Get device name for logging
                p = pyaudio.PyAudio()
                device_info = p.get_device_info_by_index(device_index).get('name')
                p.terminate()
            except Exception:
                device_info = f"Index {device_index} (Error getting name)"

        self.logger.info(f"Attempting to start audio stream on device: {device_info} (Index: {device_index})")

        try:
            self.stream = self.audio.open(
                format=self.AUDIO_FORMAT,
                channels=self.AUDIO_CHANNELS,
                rate=self.settings.sample_rate,
                input=True,
                frames_per_buffer=self.BUFFER_SIZE,
                input_device_index=device_index
            )
            self.logger.info(f"Audio stream started successfully on device index {device_index}")
            return self.stream
        except IOError as e:
            # Specific handling if the selected device index is invalid
            if "Invalid input device" in str(e) or "Invalid device index" in str(e):
                self.logger.error(f"Error starting audio stream on device index {device_index}: {e}. Falling back to default device.")
                # Try again with default device
                try:
                    # Update setting to reflect fallback - THIS IS THE KEY CHANGE
                    self.settings.input_device_index = None
                    # Force recalibration for the default device
                    if hasattr(self.settings, 'last_calibrated_device'):
                        self.settings.last_calibrated_device = -1  # Set to invalid value to force recalibration
                    # Save this change if we have access to config_manager
                    if hasattr(self, 'config_manager') and self.config_manager:
                        self.config_manager.save_settings(self.settings)
                    
                    self.stream = self.audio.open(
                        format=self.AUDIO_FORMAT, channels=self.AUDIO_CHANNELS,
                        rate=self.settings.sample_rate, input=True,
                        frames_per_buffer=self.BUFFER_SIZE,
                        input_device_index=None # Explicitly use default
                    )
                    self.logger.info("Audio stream started successfully on SYSTEM DEFAULT device.")
                    return self.stream
                except Exception as e_fallback:
                    self.logger.error(f"Failed to start audio stream even on default device: {e_fallback}", exc_info=True)
                    return None
            else:
                self.logger.error(f"Error starting audio stream: {e}", exc_info=True)
                return None
        except Exception as e:
            self.logger.error(f"Unexpected error starting audio stream: {e}", exc_info=True)
            return None
    
    def stop_stream(self):
        """Stop the audio input stream."""
        if self.stream is not None:
            try:
                # Check if stream is active before stopping
                if self.stream.is_active():
                    self.stream.stop_stream()
                self.stream.close()
            except Exception as e:
                self.logger.error(f"Error stopping stream: {e}")
            finally:
                self.stream = None
    
    def cleanup(self):
        """Clean up resources."""
        self.logger.info("Cleaning up AudioProcessor resources")
        
        # First stop the stream if it exists
        self.stop_stream()
        
        # Then terminate PyAudio
        if hasattr(self, 'audio') and self.audio:
            try:
                self.audio.terminate()
            except Exception as e:
                self.logger.error(f"Error terminating PyAudio: {e}")
            finally:
                self.audio = None
    
    def preprocess_audio(self, audio):
        """Enhanced audio preprocessing for better speech recognition."""
        # Ensure input is float32
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32) / self.BIT_DEPTH_DIVISOR
        
        # Apply processing pipeline using utility functions
        audio = audio_utils.normalize_audio(audio)
        audio = audio_utils.apply_highpass_filter(audio, self.settings.sample_rate, self.DEFAULT_HIGHPASS_CUTOFF)
        
        if self.settings.use_noise_reduction:
            audio = audio_utils.apply_noise_reduction(audio, self.settings.sample_rate)
        
        return audio.astype(np.float32)
    
    def save_debug_audio(self, audio_data, sample_rate, index):
        """Save audio data to WAV file for debugging."""
        if not self.settings.debug_mode:
            return
            
        debug_dir = "debug_audio"
        os.makedirs(debug_dir, exist_ok=True)
        
        filename = os.path.join(debug_dir, f"speech_{index}.wav")
        wf = wave.open(filename, 'wb')
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 2 bytes for int16
        wf.setframerate(sample_rate)
        wf.writeframes(audio_data)
        wf.close()
        self.logger.info(f"Saved debug audio to {filename}")