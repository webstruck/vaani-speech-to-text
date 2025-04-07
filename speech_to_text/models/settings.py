"""
Settings data model for the speech-to-text application.
"""
import typing as t

class Settings:
    """Stores application settings."""
    
    def __init__(self):
        """Initialize with default settings."""
        # Hotkeys
        self.hotkey = "ctrl+alt+z"
        self.exit_hotkey = "ctrl+alt+x"
        self.settings_hotkey = "ctrl+alt+q"
        self.test_hotkey = "ctrl+alt+t"
        self.debug_hotkey = "ctrl+alt+d"
        
        # Audio parameters
        self.sample_rate = 16000
        self.silence_threshold = 500
        self.pre_padding = 0.5
        self.silence_padding = 0.3
        self.min_phrase_duration = 0.5
        
        # Enhanced parameters
        self.use_noise_reduction = True
        self.input_device_index: t.Optional[int] = None
        self.visual_feedback = True
        
        # Speech detection parameters
        self.sentence_pause_threshold = 1.0
        self.sentence_energy_threshold = 0.3
        self.min_sentence_length = 0.8
        self.max_sentence_length = 10.0
        self.speech_energy_threshold = 3
        
        # Model parameters
        self.model_size = "small"
        self.device = "cuda"  # New setting for device selection
        self.cuda_path = "C:\\Program Files\\NVIDIA GPU Computing Toolkit\\CUDA\\v12.8\\bin"  # New setting for CUDA path
        
        # Debug mode
        self.debug_mode = False
        
        # UI settings
        self.indicator_position = {"x": 0, "y": 0}

        # Calibration data
        self.calibration_energy = None
        self.calibration_timestamp = 0
        self.last_calibrated_device = None
    
    def update(self, settings_dict):
        """Update settings from a dictionary."""
        if not settings_dict:
            return
            
        # Update hotkeys
        if "hotkeys" in settings_dict:
            self.hotkey = settings_dict["hotkeys"].get("toggle_listening", self.hotkey)
            self.exit_hotkey = settings_dict["hotkeys"].get("exit_app", self.exit_hotkey)
            self.settings_hotkey = settings_dict["hotkeys"].get("settings", self.settings_hotkey)
            self.test_hotkey = settings_dict["hotkeys"].get("test_mic", self.test_hotkey)
            self.debug_hotkey = settings_dict["hotkeys"].get("debug_mode", self.debug_hotkey)
        
        # Update audio settings
        if "audio" in settings_dict:
            self.sample_rate = settings_dict["audio"].get("sample_rate", self.sample_rate)
            self.silence_threshold = settings_dict["audio"].get("silence_threshold", self.silence_threshold)
            self.pre_padding = settings_dict["audio"].get("pre_padding", self.pre_padding)
            self.silence_padding = settings_dict["audio"].get("silence_padding", self.silence_padding)
            self.min_phrase_duration = settings_dict["audio"].get("min_phrase_duration", self.min_phrase_duration)
            self.sentence_pause_threshold = settings_dict["audio"].get("sentence_pause_threshold", self.sentence_pause_threshold)
            self.sentence_energy_threshold = settings_dict["audio"].get("sentence_energy_threshold", self.sentence_energy_threshold)
            self.min_sentence_length = settings_dict["audio"].get("min_sentence_length", self.min_sentence_length)
            self.max_sentence_length = settings_dict["audio"].get("max_sentence_length", self.max_sentence_length)
            self.speech_energy_threshold = settings_dict["audio"].get("speech_energy_threshold", self.speech_energy_threshold)
            self.use_noise_reduction = settings_dict["audio"].get("use_noise_reduction", self.use_noise_reduction)
            # Load the input device index, ensuring it's an int or None
            loaded_index = settings_dict["audio"].get("input_device_index", self.input_device_index)
            if isinstance(loaded_index, int) or loaded_index is None:
                self.input_device_index = loaded_index
            else:
                # Handle potential invalid type from file (e.g., string)
                try:
                    self.input_device_index = int(loaded_index)
                except (ValueError, TypeError):
                    self.input_device_index = None # Fallback to default
        # Update processing settings
        if "processing" in settings_dict:
            self.model_size = settings_dict["processing"].get("model_size", self.model_size)
            self.device = settings_dict["processing"].get("device", self.device)
            self.cuda_path = settings_dict["processing"].get("cuda_path", self.cuda_path)
        
        # Update UI settings
        if "ui" in settings_dict:
            self.visual_feedback = settings_dict["ui"].get("visual_feedback", self.visual_feedback)
            self.indicator_position = settings_dict["ui"].get("indicator_position", self.indicator_position)

        # Update calibration data
        if "calibration" in settings_dict:
            self.calibration_energy = settings_dict["calibration"].get("energy", self.calibration_energy)
            self.calibration_timestamp = settings_dict["calibration"].get("timestamp", self.calibration_timestamp)
            self.last_calibrated_device = settings_dict["calibration"].get("device_index", self.last_calibrated_device)
    
    def to_dict(self):
        """Convert settings to a dictionary."""
        return {
            "hotkeys": {
                "toggle_listening": self.hotkey,
                "exit_app": self.exit_hotkey,
                "settings": self.settings_hotkey,
                "test_mic": self.test_hotkey,
                "debug_mode": self.debug_hotkey
            },
            "audio": {
                "sample_rate": self.sample_rate,
                "silence_threshold": self.silence_threshold,
                "pre_padding": self.pre_padding,
                "silence_padding": self.silence_padding,
                "min_phrase_duration": self.min_phrase_duration,
                "sentence_pause_threshold": self.sentence_pause_threshold,
                "sentence_energy_threshold": self.sentence_energy_threshold,
                "min_sentence_length": self.min_sentence_length,
                "max_sentence_length": self.max_sentence_length,
                "speech_energy_threshold": self.speech_energy_threshold,
                "use_noise_reduction": self.use_noise_reduction,
                "input_device_index": self.input_device_index
            },
            "processing": {
                "model_size": self.model_size,
                "device": self.device,
                "cuda_path": self.cuda_path

            },
            "ui": {
                "visual_feedback": self.visual_feedback,
                "indicator_position": self.indicator_position
            },
            "calibration": {
                "energy": self.calibration_energy,
                "timestamp": self.calibration_timestamp,
                "device_index": self.last_calibrated_device
            }            
        }