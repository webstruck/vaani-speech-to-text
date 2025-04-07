"""
Speech detection functionality for the speech-to-text application.
Handles detecting speech segments in audio input.
"""

import numpy as np
import pyaudio
import time
import logging
import threading
from speech_to_text.utils.error_handling import log_exceptions
from speech_to_text.models.speech_segment import SpeechSegment

class SpeechDetector:
    """Detects speech segments in audio input."""
    # Speech detection constants
    CALIBRATION_DURATION_CHUNKS = 20  # About 1 second at 1024 chunk size
    ENERGY_HISTORY_MAX_SIZE = 50
    ENERGY_SMOOTHING_WINDOW = 10
    
    # Chunk size for audio processing
    CHUNK_SIZE = 1024

    def __init__(self, settings, speech_queue, energy_queue, segment_counter, config_manager=None):
        """Initialize the speech detector with the given settings."""
        self.logger = logging.getLogger(__name__)
        self.settings = settings
        self.speech_queue = speech_queue
        self.energy_queue = energy_queue  # Add the energy queue
        self.segment_counter = segment_counter
        self.energy_history = []
        self.energy_history_max_size = self.ENERGY_HISTORY_MAX_SIZE
        self.config_manager = config_manager  # Store the config manager        
    
    def update_settings(self, settings):
        """Update the settings used by the speech detector."""
        self.settings = settings
    
    @log_exceptions
    def start_detection(self, active_flag, segment_counter, termination_event):
        """
        Start detecting speech in audio input.
        
        Args:
            active_flag: Reference to the active flag in the main app
            segment_counter: Reference to the segment counter in the main app
            termination_event: Event to signal thread termination
        """
        FORMAT = pyaudio.paInt16
        CHANNELS = 1
        RATE = self.settings.sample_rate
        CHUNK = self.CHUNK_SIZE
        
        # Calculate parameters in chunks
        pre_padding_chunks = int(self.settings.pre_padding * RATE / CHUNK)
        silence_padding_chunks = int(self.settings.silence_padding * RATE / CHUNK)
        min_phrase_chunks = int(self.settings.min_phrase_duration * RATE / CHUNK)
        device_index = self.settings.input_device_index
        audio = pyaudio.PyAudio()
        stream = None
        
        try:
            # Start recording
            self.logger.info(f"SpeechDetector attempting to open stream on device index: {device_index}")
            stream = audio.open(format=FORMAT, channels=CHANNELS,
                            rate=RATE, input=True,
                            frames_per_buffer=CHUNK,
                            input_device_index=device_index) # <-- Use index here
            self.logger.info(f"SpeechDetector stream opened successfully on index: {device_index}")
            
            # Circular buffer for keeping recent audio
            circular_buffer = []
            circular_buffer_size = pre_padding_chunks
            
            # State tracking
            is_speaking = False
            silent_chunks = 0
            recorded_chunks = 0
            current_energy_levels = []
            sentence_start_time = None
            last_speech_time = None
            
            # Calibration code
            self.logger.info("Calibrating microphone (establishing noise baseline)...")

            baseline_energy = None
            calibration_timestamp = 0
            
            # Try to load calibration from settings
            if hasattr(self.settings, 'calibration_energy') and hasattr(self.settings, 'calibration_timestamp'):
                baseline_energy = self.settings.calibration_energy
                calibration_timestamp = self.settings.calibration_timestamp
                
                if hasattr(self.settings, 'last_calibrated_device') and self.settings.last_calibrated_device != device_index:
                    self.logger.info(f"Input device changed from {self.settings.last_calibrated_device} to {device_index}, forcing recalibration")
                    baseline_energy = None
                # Only use cached value if less than 24 hours old
                elif time.time() - calibration_timestamp > 86400:  # 24 hours in seconds
                    baseline_energy = None
                else:
                    self.logger.info(f"Using cached calibration: {baseline_energy:.1f}")
            
            # Run calibration if no cached value or force recalibration flag is set
            if baseline_energy is None:
                self.logger.info("Calibrating microphone (establishing noise baseline)...")
                baseline_frames = []
                for _ in range(self.CALIBRATION_DURATION_CHUNKS):  # About 1 second
                    # Check termination event during calibration
                    if termination_event.is_set():
                        self.logger.info("Termination requested during calibration")
                        return
                        
                    data = stream.read(CHUNK, exception_on_overflow=False)
                    baseline_frames.append(np.frombuffer(data, dtype=np.int16))
                    time.sleep(0.01)
                
                # Calculate baseline energy
                if baseline_frames:
                    baseline_energy = np.mean([np.abs(frame).mean() for frame in baseline_frames])
                    self.logger.info(f"New baseline energy: {baseline_energy:.1f}")
                    
                    # Store calibration in settings
                    self.settings.calibration_energy = baseline_energy
                    self.settings.calibration_timestamp = time.time()
                    self.settings.last_calibrated_device = device_index
                    # Save settings using the config_manager
                    # We need to access the config_manager from the app
                    # This requires passing a reference to the config_manager when initializing SpeechDetector
                    if hasattr(self, 'config_manager') and self.config_manager:
                        self.config_manager.save_settings(self.settings)
                    else:
                        self.logger.warning("Config manager not available, calibration not saved to settings")
            
            # Use the baseline energy to set adaptive threshold
            if baseline_energy:
                adaptive_threshold = baseline_energy * self.settings.speech_energy_threshold
                self.settings.silence_threshold = max(300, min(adaptive_threshold, 1000))
                self.logger.info(f"Adaptive threshold set to: {self.settings.silence_threshold}")
            
            # Main audio processing loop
            frames = []
            while active_flag and not termination_event.is_set():
                try:
                    # Check termination event more frequently
                    if termination_event.is_set():
                        self.logger.info("Termination event detected, stopping audio capture")
                        break
                        
                    data = stream.read(CHUNK, exception_on_overflow=False)
                except IOError as e:
                    # Handle stream read errors
                    self.logger.error(f"Stream read error: {e}")
                    break
                    
                audio_data = np.frombuffer(data, dtype=np.int16)
                
                # Keep circular buffer updated
                if len(circular_buffer) >= circular_buffer_size:
                    circular_buffer.pop(0)
                circular_buffer.append(data)
                
                # Energy calculation with smoothing
                current_energy = np.abs(audio_data).mean()
                current_energy_levels.append(current_energy)
                if len(current_energy_levels) > self.ENERGY_SMOOTHING_WINDOW:
                    current_energy_levels.pop(0)
                smoothed_energy = np.mean(current_energy_levels)
                
                # Emit energy level for visualization - FIXED: Now using the speech_queue
                self._emit_energy_level(smoothed_energy)
                
                # Speech detection with enhanced sentence boundary detection
                is_speech = smoothed_energy > self.settings.silence_threshold
                current_time = time.time()
                
                if not is_speaking:
                    if is_speech:
                        is_speaking = True
                        sentence_start_time = current_time
                        last_speech_time = current_time
                        silent_chunks = 0
                        recorded_chunks = 0
                        frames = list(circular_buffer)
                        self.logger.info(f"Speech detected (energy: {smoothed_energy:.1f})")
                
                if is_speaking:
                    frames.append(data)
                    recorded_chunks += 1
                    
                    if is_speech:
                        last_speech_time = current_time
                        silent_chunks = 0
                    else:
                        silent_chunks += 1
                    
                    # Check for sentence boundaries
                    duration = current_time - sentence_start_time
                    silence_duration = current_time - last_speech_time
                    
                    should_split = False
                    split_reason = ""
                    
                    # Check various conditions for sentence splitting
                    if silence_duration >= self.settings.sentence_pause_threshold:
                        should_split = True
                        split_reason = "long pause"
                    elif duration >= self.settings.max_sentence_length:
                        should_split = True
                        split_reason = "max length"
                    elif (silence_duration >= self.settings.sentence_pause_threshold * 0.5 and 
                        smoothed_energy < self.settings.silence_threshold * self.settings.sentence_energy_threshold):
                        should_split = True
                        split_reason = "energy drop"
                    
                    if should_split and duration >= self.settings.min_sentence_length:
                        self.logger.info(f"Sentence boundary detected ({split_reason})")
                        
                        # Process the current sentence with better memory management
                        audio_data = b''.join(frames)
                        audio_np = np.frombuffer(audio_data, dtype=np.int16)
                        
                        # Use our new method for better memory management
                        self._process_speech_segment(audio_np, RATE, sentence_start_time, self.segment_counter)
                        self.segment_counter += 1
                        
                        # Reset for next sentence
                        frames = []
                        is_speaking = False
                        sentence_start_time = None
                        
                    # Check for end of speech
                    elif silent_chunks >= silence_padding_chunks and recorded_chunks >= min_phrase_chunks:
                        if len(frames) > min_phrase_chunks:
                            audio_data = b''.join(frames)
                            audio_np = np.frombuffer(audio_data, dtype=np.int16)
                            
                            # Use our new method for better memory management
                            self._process_speech_segment(audio_np, RATE, sentence_start_time, self.segment_counter)
                            self.segment_counter += 1
                        
                        # Reset state
                        is_speaking = False
                        frames = []
                        sentence_start_time = None
                
                # Check termination event periodically
                if termination_event.is_set():
                    self.logger.info("Termination event detected, stopping audio capture")
                    break
        except IOError as e:
             # Try fallback to default if specific device fails
             if device_index is not None and ("Invalid input device" in str(e) or "Invalid device index" in str(e)):
                 self.logger.warning(f"SpeechDetector failed to open stream on index {device_index}: {e}. Falling back to default.")
                 try:
                     # Try again with default
                     stream = audio.open(format=FORMAT, channels=CHANNELS,
                                     rate=RATE, input=True,
                                     frames_per_buffer=CHUNK,
                                     input_device_index=None)
                     self.logger.info("SpeechDetector stream opened successfully on SYSTEM DEFAULT device.")
                     # Continue with the loop using the fallback stream
                     # ... (Duplicate or refactor the main loop logic here for the fallback case) ...
                     # OR: A simpler approach is to just log the error and exit the function
                     self.logger.error("Fallback successful, but loop logic needs refactoring. Exiting detection.")
                     # --- Start of detection loop logic (potentially refactor into a helper method) ---
                     # circular_buffer = []
                     # ... rest of the loop from the original try block ...
                     # --- End of detection loop logic ---

                 except Exception as e_fallback:
                     self.logger.error(f"SpeechDetector failed to open stream even on default device: {e_fallback}", exc_info=True)
                     # Cannot continue without a stream
                     return
             else:
                 self.logger.error(f"SpeechDetector stream open error: {e}", exc_info=True)
                 return # Cannot continue

        except Exception as e:
             self.logger.error(f"Error in audio capture/detection loop: {str(e)}", exc_info=True)
        finally:
            # Cleanup code - make sure to properly close the stream
            self.logger.info("Cleaning up audio resources")
            if stream is not None:
                try:
                    stream.stop_stream()
                    stream.close()
                except Exception as e:
                    self.logger.error(f"Error closing stream: {e}")
                    
            if audio is not None:
                try:
                    audio.terminate()
                except Exception as e:
                    self.logger.error(f"Error terminating PyAudio: {e}")
                    
            self.logger.info("Microphone deactivated")

    def _emit_energy_level(self, energy):
        """Emit energy level for visualization."""
        # Use the dedicated energy queue
        self.energy_queue.put(energy)

    def stop_detection(self):
        """Stop any ongoing speech detection."""
        self.logger.info("Explicitly stopping speech detection")
        # This method can be expanded if needed

    def _process_speech_segment(self, audio_data, sample_rate, timestamp, segment_id):
        """Process speech segment with better memory management."""
        try:
            # Create a speech segment
            segment = SpeechSegment(
                audio_data=audio_data,
                sample_rate=sample_rate,
                timestamp=timestamp,
                segment_id=segment_id
            )
            
            # Add to processing queue
            self.speech_queue.put(segment)
            self.logger.info(f"Added speech segment #{segment_id} to queue")
            
            # Explicitly delete the original audio data to help garbage collection
            del audio_data
            
            return True
        except Exception as e:
            self.logger.error(f"Error processing speech segment: {str(e)}")
            return False