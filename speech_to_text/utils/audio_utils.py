"""
Audio utility functions for the speech-to-text application.
"""

import numpy as np
from scipy import signal
import logging
import pyaudio
import typing as t


logger = logging.getLogger(__name__)

def normalize_audio(audio: np.ndarray) -> np.ndarray:
    """
    Normalize audio to have a maximum amplitude of 1.0.
    
    Args:
        audio: numpy array of audio data
        
    Returns:
        Normalized audio as float32 numpy array
    """
    if np.abs(audio).max() > 0:
        return audio / np.abs(audio).max() * 0.9
    return audio

def apply_highpass_filter(audio: np.ndarray, sample_rate: int, cutoff: int = 100) -> np.ndarray:
    """
    Apply a high-pass filter to remove low-frequency noise.
    
    Args:
        audio: numpy array of audio data
        sample_rate: audio sample rate in Hz
        cutoff: cutoff frequency in Hz
        
    Returns:
        Filtered audio as float32 numpy array
    """
    sos = signal.butter(2, cutoff, 'hp', fs=sample_rate, output='sos')
    return signal.sosfilt(sos, audio)

def apply_noise_reduction(audio: np.ndarray, sample_rate: int) -> np.ndarray:   
    """
    Apply noise reduction using spectral gating.
    
    Args:
        audio: numpy array of audio data
        sample_rate: audio sample rate in Hz
        
    Returns:
        Noise-reduced audio as float32 numpy array
    """
    try:
        import noisereduce as nr
        # Use the first 0.3 seconds as noise profile if available
        noise_sample = audio[:int(sample_rate * 0.3)] if len(audio) > sample_rate * 0.3 else None
        return nr.reduce_noise(y=audio, sr=sample_rate, 
                            y_noise=noise_sample,
                            prop_decrease=0.75,
                            stationary=False)
    except ImportError:
        logger.warning("noisereduce library not found. Install with: pip install noisereduce")
        return audio

def get_audio_input_devices() -> t.Dict[str, t.Optional[int]]:
    """
    Retrieves a dictionary of available audio input devices.

    Returns:
        A dictionary mapping device names (with host API) to their indices.
        Includes a "System Default" option mapping to None.
        Returns an empty dict + default if PyAudio fails.
    """
    devices = {"System Default": None} # Start with the default option
    try:
        p = pyaudio.PyAudio()
        info = p.get_host_api_info_by_index(0)
        numdevices = info.get('deviceCount')

        logger.info(f"Found {numdevices} audio devices.")

        for i in range(0, numdevices):
            device_info = p.get_device_info_by_index(i)
            if device_info.get('maxInputChannels') > 0:
                device_name = device_info.get('name')
                host_api = p.get_host_api_info_by_index(device_info.get('hostApi')).get('name')
                # Make name more unique and informative
                full_name = f"{device_name} ({host_api})"
                devices[full_name] = i
                logger.debug(f"Found input device: index={i}, name='{full_name}'")

        p.terminate()
    except Exception as e:
        logger.error(f"Could not enumerate audio devices: {e}", exc_info=True)
        # Return just the default option if enumeration fails
        return {"System Default": None}
    return devices