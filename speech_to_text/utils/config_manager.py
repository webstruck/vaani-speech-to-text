"""
Configuration management for the speech-to-text application.
"""

import os
import json
import logging
from speech_to_text.models.settings import Settings
import typing as t

class ConfigManager:
    """Manages application configuration and settings."""
    
    def __init__(self):
        """Initialize the configuration manager."""
        self.logger = logging.getLogger(__name__)
        self.config_dir = os.path.join(os.path.expanduser("~"), ".speech_to_text_app")
        os.makedirs(self.config_dir, exist_ok=True)
        self.settings_file = os.path.join(self.config_dir, "settings.json")
    
    def create_default_settings(self):
        """Create default settings."""
        return Settings()
    
    def load_settings(self):
        """Load settings from file."""
        settings = self.create_default_settings()
        
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    settings_dict = json.load(f)
                    settings.update(settings_dict)
                    self.logger.info("Settings loaded from file")
            else:
                self.logger.info("No settings file found, using defaults")
        except Exception as e:
            self.logger.error(f"Error loading settings: {str(e)}")
        
        # Validate settings after loading
        settings = self.validate_settings(settings)
        
        return settings

    def validate_settings(self, settings):
        """Validate settings and ensure they're within acceptable ranges."""
        # Audio settings validation
        settings.sample_rate = self.validate_option(settings.sample_rate, 
                                            [8000, 16000, 22050, 44100, 48000], 
                                            16000)
        settings.silence_threshold = self.validate_range(settings.silence_threshold, 100, 2000, 500)
        settings.pre_padding = self.validate_range(settings.pre_padding, 0.1, 1.0, 0.5)
        settings.silence_padding = self.validate_range(settings.silence_padding, 0.1, 1.0, 0.3)
        settings.min_phrase_duration = self.validate_range(settings.min_phrase_duration, 0.1, 2.0, 0.5)
        settings.sentence_pause_threshold = self.validate_range(settings.sentence_pause_threshold, 0.2, 2.0, 1.0)
        settings.sentence_energy_threshold = self.validate_range(settings.sentence_energy_threshold, 0.1, 1.0, 0.3)
        settings.min_sentence_length = self.validate_range(settings.min_sentence_length, 0.2, 2.0, 0.8)
        settings.max_sentence_length = self.validate_range(settings.max_sentence_length, 5.0, 20.0, 10.0)
        settings.speech_energy_threshold = self.validate_range(settings.speech_energy_threshold, 1.0, 10.0, 3.0)
        if not (isinstance(settings.input_device_index, int) or settings.input_device_index is None):
             self.logger.warning(f"Invalid input_device_index '{settings.input_device_index}' found in settings, resetting to default (None).")
             settings.input_device_index = None # Reset to default if invalid type
             
        # Model settings validation
        settings.model_size = self.validate_option(settings.model_size, 
                                            ["tiny", "base", "small", "medium", "large"], 
                                            "small")
        settings.device = self.validate_option(settings.device, ["cpu", "cuda"], "cpu")
        
        return settings

    # Helper validation functions to add at module level
    def validate_range(self, value, min_val, max_val, default):
        """Ensure a value is within a specified range."""
        if value is None or not isinstance(value, (int, float)) or value < min_val or value > max_val:
            return default
        return value

    def validate_option(self, value, options, default):
        """Ensure a value is one of the allowed options."""
        if value not in options:
            return default
        return value
    
    def save_settings(self, settings):
        """Save settings to file."""
        try:
            settings_dict = settings.to_dict()
            
            with open(self.settings_file, 'w') as f:
                json.dump(settings_dict, f, indent=2)
            
            self.logger.info("Settings saved to file")
            return True
        except Exception as e:
            self.logger.error(f"Error saving settings: {str(e)}")
            return False
    
    def check_settings_path(self):
        """Check if settings path is writable."""
        try:
            # Create directory if it doesn't exist
            os.makedirs(self.config_dir, exist_ok=True)
            
            # Check if directory is writable
            test_file = os.path.join(self.config_dir, "test_write.tmp")
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
            
            self.logger.info(f"Settings directory is writable: {self.config_dir}")
            return True
        except Exception as e:
            self.logger.error(f"Settings directory is NOT writable: {self.config_dir}")
            self.logger.error(f"Error: {str(e)}")
            return False