"""
Settings dialog for the speech-to-text application (PySide6 version).
"""

import logging
import typing as t
import requests
from PySide6.QtWidgets import (QDialog, QWidget, QTabWidget, QVBoxLayout,
                               QHBoxLayout, QGridLayout, QLabel, QLineEdit,
                               QComboBox, QSlider, QCheckBox, QPushButton,
                               QFileDialog, QMessageBox, QDialogButtonBox,
                               QSizePolicy, QScrollArea)
from PySide6.QtCore import Qt, Slot, Signal
import os
# Assuming audio_utils.get_audio_input_devices remains the same
from speech_to_text.utils.audio_utils import get_audio_input_devices
from speech_to_text.models.settings import Settings, _LANGUAGE_CODES # Import the Settings class
from speech_to_text.ui.speech_indicator import SpeechIndicator # To call reset_position

class SettingsDialog(QDialog):
    """Dialog for configuring application settings using PySide6."""

    # Signal emitted when settings that require restart are changed
    restart_needed = Signal()

    def __init__(self, current_settings: Settings, config_manager,
                 speech_indicator: t.Optional[SpeechIndicator], parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.current_settings = current_settings
        # Create a deep copy for editing to allow cancellation
        self.editable_settings = Settings()
        self.editable_settings.update(current_settings.to_dict()) # Populate from current

        self.config_manager = config_manager
        self.speech_indicator = speech_indicator
        self.input_devices: t.Dict[str, t.Optional[int]] = {} # name -> index
        self.restart_required = False # Flag if restart-needed settings change

        self._initial_model_size = self.editable_settings.model_size
        self._initial_device = self.editable_settings.device
        self._initial_sample_rate = self.editable_settings.sample_rate
        self._initial_device_index = self.editable_settings.input_device_index

        self._setup_ui()
        self._populate_fields()


    def _setup_ui(self):
        """Create the dialog's UI elements."""
        self.setWindowTitle("Speech-to-Text Settings")
        self.setMinimumSize(600, 500)  # Set a reasonable minimum size

        # Main layout
        main_layout = QVBoxLayout(self)

        # Notebook (Tabs)
        self.notebook = QTabWidget(self)
        main_layout.addWidget(self.notebook)

        # Create tabs
        self._create_hotkeys_tab()
        self._create_audio_tab()
        self._create_processing_tab()
        self._create_llm_tab()  # New tab for LLM processing
        self._create_ui_tab()

        # Dialog buttons (OK, Cancel, Apply, Reset)
        self.button_box = QDialogButtonBox(self)
        reset_button = self.button_box.addButton("Reset to Defaults", QDialogButtonBox.ButtonRole.ActionRole)
        ok_button = self.button_box.addButton(QDialogButtonBox.StandardButton.Ok)
        cancel_button = self.button_box.addButton(QDialogButtonBox.StandardButton.Cancel)

        main_layout.addWidget(self.button_box)

        # --- Connect Signals ---
        ok_button.clicked.connect(self._save_settings_and_accept)
        cancel_button.clicked.connect(self.reject)
        reset_button.clicked.connect(self._reset_to_defaults)

        # Connect signals for restart check
        self.model_size_combo.currentTextChanged.connect(self._check_restart_needed)
        self.device_combo.currentTextChanged.connect(self._check_restart_needed)

        self.setLayout(main_layout)


    def _create_labeled_widget(self, label_text, widget):
        """Helper to create a label and widget pair in a horizontal layout."""
        layout = QHBoxLayout()
        label = QLabel(label_text)
        label.setMinimumWidth(150) # Align widgets
        layout.addWidget(label)
        layout.addWidget(widget, stretch=1)
        return layout

    @staticmethod
    def _create_slider_widget(label_text, min_val, max_val, initial_val, resolution=1.0, tick_interval=None):
        """Helper to create a slider with a label showing its value."""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        label = QLabel(label_text)
        label.setMinimumWidth(150)
        layout.addWidget(label)

        slider = QSlider(Qt.Orientation.Horizontal)
        # Scale float values to integers for the slider
        scale_factor = 1 / resolution
        slider.setRange(int(min_val * scale_factor), int(max_val * scale_factor))
        slider.setValue(int(initial_val * scale_factor))
        slider.setSingleStep(1)  # Step by scaled resolution
        if tick_interval:
            slider.setTickInterval(int(tick_interval * scale_factor))
            slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        layout.addWidget(slider, stretch=1)

        value_label = QLabel(f"{initial_val:.{len(str(resolution).split('.')[-1]) if '.' in str(resolution) else 0}f}")
        value_label.setMinimumWidth(40)  # Space for value
        layout.addWidget(value_label)

        # Connect slider's valueChanged signal to update the label
        slider.valueChanged.connect(lambda value, lbl=value_label, sf=scale_factor:
                                    lbl.setText(f"{value / sf:.{len(str(resolution).split('.')[-1]) if '.' in str(resolution) else 0}f}"))

        return container, slider  # Return container and slider


    # --- Tab Creation Methods ---

    def _create_hotkeys_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        grid_layout = QGridLayout()

        self.toggle_entry = QLineEdit()
        self.exit_entry = QLineEdit()
        self.settings_entry = QLineEdit()
        self.test_entry = QLineEdit()
        self.debug_entry = QLineEdit()

        grid_layout.addWidget(QLabel("Toggle Listening:"), 0, 0)
        grid_layout.addWidget(self.toggle_entry, 0, 1)
        grid_layout.addWidget(QLabel("Exit Application:"), 1, 0)
        grid_layout.addWidget(self.exit_entry, 1, 1)
        grid_layout.addWidget(QLabel("Open Settings:"), 2, 0)
        grid_layout.addWidget(self.settings_entry, 2, 1)
        grid_layout.addWidget(QLabel("Test Microphone:"), 3, 0)
        grid_layout.addWidget(self.test_entry, 3, 1)
        grid_layout.addWidget(QLabel("Toggle Debug Mode:"), 4, 0)
        grid_layout.addWidget(self.debug_entry, 4, 1)

        layout.addLayout(grid_layout)
        layout.addWidget(QLabel("Format: ctrl+alt+key (e.g., ctrl+alt+z)\nRequires exact naming as per 'keyboard' library."))
        layout.addStretch(1) # Push widgets to top
        self.notebook.addTab(tab, "Hotkeys")

    def _create_audio_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # --- Input Device ---
        device_layout = QHBoxLayout()
        device_label = QLabel("Input Device:")
        self.input_device_combo = QComboBox()
        self.input_device_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.input_devices = get_audio_input_devices()
        for name in self.input_devices.keys():
            self.input_device_combo.addItem(name, self.input_devices[name]) # Store index in UserData role
        self.input_device_combo.currentIndexChanged.connect(self._check_restart_needed)

        restart_label = QLabel("(Restart Required)")
        restart_label.setStyleSheet("font-style: italic; color: gray;")
        device_layout.addWidget(device_label)
        device_layout.addWidget(self.input_device_combo, stretch=1)
        device_layout.addWidget(restart_label)
        layout.addLayout(device_layout)

        layout.addSpacing(15)

        # --- Basic Settings ---
        basic_group = QWidget() # Use QGroupBox later if desired
        basic_layout = QVBoxLayout(basic_group)
        basic_layout.setContentsMargins(0,0,0,0)

        self.threshold_widget, self.threshold_slider = self._create_slider_widget(
            "Silence Threshold:", 100, 2000, self.editable_settings.silence_threshold, 10, 500)
        basic_layout.addWidget(self.threshold_widget)

        self.min_duration_widget, self.min_duration_slider = self._create_slider_widget(
            "Min Phrase Duration (s):", 0.1, 2.0, self.editable_settings.min_phrase_duration, 0.1)
        basic_layout.addWidget(self.min_duration_widget)

        self.speech_energy_widget, self.speech_energy_slider = self._create_slider_widget(
            "Speech Energy Factor:", 1.0, 10.0, self.editable_settings.speech_energy_threshold, 0.1)
        basic_layout.addWidget(self.speech_energy_widget)

        self.noise_reduction_check = QCheckBox("Use noise reduction (requires 'noisereduce')")
        basic_layout.addWidget(self.noise_reduction_check)

        layout.addWidget(QLabel("<b>Basic Audio Settings</b>"))
        layout.addWidget(basic_group)
        layout.addSpacing(15)

        # --- Advanced Button ---
        advanced_button = QPushButton("Advanced Audio Settings...")
        advanced_button.clicked.connect(self._show_advanced_audio_settings)
        layout.addWidget(advanced_button, alignment=Qt.AlignmentFlag.AlignLeft)

        layout.addStretch(1)
        self.notebook.addTab(tab, "Audio")


    def _create_processing_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # --- Language ---
        lang_layout = QHBoxLayout()
        lang_label = QLabel("Language:")
        self.language_combo = QComboBox()
        self.language_combo.addItems(_LANGUAGE_CODES) # Populate from imported list
        self.language_combo.setToolTip("Select the language to be transcribed.")
        lang_layout.addWidget(lang_label)
        lang_layout.addWidget(self.language_combo, stretch=1)
        layout.addLayout(lang_layout)

        # --- Model Size ---
        model_layout = QHBoxLayout()
        model_label = QLabel("Model Size:")
        self.model_size_combo = QComboBox()
        self.model_size_combo.addItems(["tiny", "base", "small", "medium", "large"])
        model_restart = QLabel("(Restart Required)")
        model_restart.setStyleSheet("font-style: italic; color: gray;")
        model_layout.addWidget(model_label)
        model_layout.addWidget(self.model_size_combo, stretch=1)
        model_layout.addWidget(model_restart)
        layout.addLayout(model_layout)

        # --- Device ---
        device_layout = QHBoxLayout()
        device_label = QLabel("Device:")
        self.device_combo = QComboBox()
        self.device_combo.addItems(["cpu", "cuda"]) # Add more if faster-whisper supports (e.g., rocm)
        device_restart = QLabel("(Restart Required)")
        device_restart.setStyleSheet("font-style: italic; color: gray;")
        device_layout.addWidget(device_label)
        device_layout.addWidget(self.device_combo, stretch=1)
        device_layout.addWidget(device_restart)
        layout.addLayout(device_layout)
        self.device_combo.currentTextChanged.connect(self._update_cuda_path_state) # Enable/disable path

        # --- CUDA Path ---
        cuda_layout = QHBoxLayout()
        self.cuda_path_label = QLabel("CUDA Path:")
        self.cuda_path_entry = QLineEdit()
        self.cuda_path_button = QPushButton("Browse...")
        self.cuda_path_button.clicked.connect(self._browse_cuda_path)
        cuda_layout.addWidget(self.cuda_path_label)
        cuda_layout.addWidget(self.cuda_path_entry, stretch=1)
        cuda_layout.addWidget(self.cuda_path_button)
        layout.addLayout(cuda_layout)

        layout.addSpacing(20)

        # --- Explanation ---
        explanation_text = (
            "<b>Language</b> determines the language expected in the audio.<br><br>"
            "<b>Model size</b> affects accuracy and speed:<br>"
            "• tiny: Fastest, lowest accuracy<br>"
            "• base: Fast, basic accuracy<br>"
            "• small: Good balance (recommended)<br>"
            "• medium: Better accuracy, slower<br>"
            "• large: Best accuracy, slowest<br><br><br>"
            "<b>Device selection</b> determines processing hardware:<br>"
            "• cpu: Works on all computers but is slower.<br>"
            "• cuda: Much faster but requires a compatible NVIDIA GPU and CUDA toolkit installed. Set the path to the CUDA 'bin' directory."
        )
        explanation_label = QLabel(explanation_text)
        explanation_label.setWordWrap(True)
        layout.addWidget(explanation_label)

        layout.addStretch(1)
        self.notebook.addTab(tab, "Transcribe")
        self._update_cuda_path_state(self.device_combo.currentText()) # Initial state

    def _create_llm_tab(self):
        """Create the LLM text processing settings tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # --- Enable LLM Processing ---
        self.use_llm_processing_check = QCheckBox("Enable LLM text processing")
        self.use_llm_processing_check.setToolTip("Use LLM to improve transcription quality with context-aware processing")
        layout.addWidget(self.use_llm_processing_check)
        
        # Connect to enable/disable the other controls
        self.use_llm_processing_check.toggled.connect(self._update_llm_controls_state)
        
        layout.addSpacing(10)
        
        # --- LLM Settings Group ---
        llm_group = QWidget()
        llm_layout = QVBoxLayout(llm_group)
        llm_layout.setContentsMargins(0, 0, 0, 0)

        # --- Ollama Endpoint ---
        endpoint_layout = QHBoxLayout()
        endpoint_label = QLabel("Ollama Endpoint:")
        self.llm_endpoint_entry = QLineEdit()
        self.llm_endpoint_entry.setPlaceholderText("http://localhost:11434")
        endpoint_layout.addWidget(endpoint_label)
        endpoint_layout.addWidget(self.llm_endpoint_entry, stretch=1)
        llm_layout.addLayout(endpoint_layout)
        
        # --- Model Dropdown with fetch button ---
        model_layout = QHBoxLayout()
        model_label = QLabel("LLM Model:")
        self.llm_model_combo = QComboBox()
        self.llm_model_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.llm_model_combo.setEditable(True)
        self.refresh_models_button = QPushButton("Refresh Models")
        self.refresh_models_button.clicked.connect(self._fetch_ollama_models)
        model_layout.addWidget(model_label)
        model_layout.addWidget(self.llm_model_combo, stretch=1)
        model_layout.addWidget(self.refresh_models_button)
        llm_layout.addLayout(model_layout)
        
        # --- Timeout slider ---
        self.timeout_widget, self.timeout_slider = self._create_slider_widget(
            "Timeout (seconds):", 1.0, 10.0, self.editable_settings.llm_timeout, 0.5)
        llm_layout.addWidget(self.timeout_widget)
        
        layout.addWidget(llm_group)
        
        # --- Explanation ---
        layout.addSpacing(15)
        explanation_text = (
            "<b>LLM Text Processing</b> uses large language models to improve transcript quality.<br><br>"
            "• <b>Ollama Endpoint</b>: URL where Ollama server is running<br>"
            "• <b>LLM Model</b>: Model to use for text processing (fetched from Ollama)<br>"
            "• <b>Timeout</b>: Maximum time to wait for LLM responses (lower for real-time use)<br><br>"
            "Requires <a href='https://ollama.ai'>Ollama</a> to be installed and running locally. "
            "Processing happens locally using your computer's hardware."
        )
        explanation_label = QLabel(explanation_text)
        explanation_label.setWordWrap(True)
        explanation_label.setOpenExternalLinks(True)
        layout.addWidget(explanation_label)

        layout.addStretch(1)
        self.notebook.addTab(tab, "Post Processing")
        
        # Initial fetch of Ollama models if endpoint is set
        if self.editable_settings.llm_endpoint:
            self._fetch_ollama_models()

    def _create_ui_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self.visual_feedback_check = QCheckBox("Show visual indicator while recording")
        layout.addWidget(self.visual_feedback_check)

        reset_pos_button = QPushButton("Reset Indicator Position")
        reset_pos_button.clicked.connect(self._reset_indicator_position)
        layout.addWidget(reset_pos_button, alignment=Qt.AlignmentFlag.AlignLeft)

        layout.addStretch(1)
        self.notebook.addTab(tab, "Interface")

    # --- Populate and Save Logic ---

    def _populate_fields(self):
        """Fill UI fields with values from editable_settings."""
        s = self.editable_settings

        # Hotkeys
        self.toggle_entry.setText(s.hotkey)
        self.exit_entry.setText(s.exit_hotkey)
        self.settings_entry.setText(s.settings_hotkey)
        self.test_entry.setText(s.test_hotkey)
        self.debug_entry.setText(s.debug_hotkey)

        # Audio
        # Find index in combo box matching the setting's device index
        idx = self.input_device_combo.findData(s.input_device_index)
        if idx != -1:
            self.input_device_combo.setCurrentIndex(idx)
        else:
            self.input_device_combo.setCurrentIndex(0) # Default to "System Default" if not found

        self.threshold_slider.setValue(int(s.silence_threshold / 10)) # Scaled value
        self.min_duration_slider.setValue(int(s.min_phrase_duration / 0.1))
        self.speech_energy_slider.setValue(int(s.speech_energy_threshold / 0.1))
        self.noise_reduction_check.setChecked(s.use_noise_reduction)

        # Processing
        self.model_size_combo.setCurrentText(s.model_size)
        self.language_combo.setCurrentText(s.language)
        self.device_combo.setCurrentText(s.device)
        self.cuda_path_entry.setText(s.cuda_path if s.cuda_path else "")
        self._update_cuda_path_state(s.device) # Set initial enable/disable

        # LLM Processing
        self.use_llm_processing_check.setChecked(s.use_llm_processing)
        self.llm_endpoint_entry.setText(s.llm_endpoint)
        self.llm_model_combo.setCurrentText(s.llm_model_name)
        self.timeout_slider.setValue(int(s.llm_timeout / 0.5))
        self._update_llm_controls_state(s.use_llm_processing)

        # UI
        self.visual_feedback_check.setChecked(s.visual_feedback)


    def _apply_to_settings(self):
        """Update self.editable_settings from UI fields."""
        s = self.editable_settings

        # Hotkeys
        s.hotkey = self.toggle_entry.text().strip()
        s.exit_hotkey = self.exit_entry.text().strip()
        s.settings_hotkey = self.settings_entry.text().strip()
        s.test_hotkey = self.test_entry.text().strip()
        s.debug_hotkey = self.debug_entry.text().strip()

        # Audio
        s.input_device_index = self.input_device_combo.currentData() # Get data (index)
        s.silence_threshold = self.threshold_slider.value() * 10
        s.min_phrase_duration = self.min_duration_slider.value() * 0.1
        s.speech_energy_threshold = self.speech_energy_slider.value() * 0.1
        s.use_noise_reduction = self.noise_reduction_check.isChecked()
        # Advanced settings are applied directly in the advanced dialog

        # Processing
        s.model_size = self.model_size_combo.currentText()
        s.language = self.language_combo.currentText()
        s.device = self.device_combo.currentText()
        s.cuda_path = self.cuda_path_entry.text().strip()
        
        # LLM Processing
        s.use_llm_processing = self.use_llm_processing_check.isChecked()
        s.llm_model_name = self.llm_model_combo.currentText()
        s.llm_endpoint = self.llm_endpoint_entry.text().strip()
        s.llm_timeout = self.timeout_slider.value() * 0.5

        # UI
        s.visual_feedback = self.visual_feedback_check.isChecked()

        # Check if restart is needed AFTER applying changes
        self._check_restart_needed()


    @Slot()
    def _save_settings_and_accept(self):
        """Apply changes to settings object, save, and accept dialog."""
        self._apply_to_settings() # Update editable_settings from UI
        try:
            # Save the updated editable_settings
            if self.config_manager.save_settings(self.editable_settings):
                self.logger.info("Settings saved successfully.")
                # Copy editable settings back to the original reference *only on success*
                self.current_settings.update(self.editable_settings.to_dict())
                self.accept() # Close dialog with Accepted status
            else:
                self.logger.error("Failed to save settings to file.")
                QMessageBox.warning(self, "Save Error", "Could not save settings. Please check file permissions.")
        except Exception as e:
             self.logger.error(f"Error during settings save: {e}", exc_info=True)
             QMessageBox.critical(self, "Save Error", f"An unexpected error occurred while saving settings:\n{e}")


    def get_updated_settings(self) -> t.Optional[Settings]:
         """Return the updated settings object if dialog was accepted."""
         # Since we update current_settings on accept, we can return that
         # Or return the editable_settings copy
         return self.editable_settings # This holds the accepted values

    # --- Button Actions ---

    @Slot()
    def _reset_to_defaults(self):
        """Reset settings to default values and update UI."""
        reply = QMessageBox.question(self, "Reset Settings",
                                       "Are you sure you want to reset all settings to their default values?",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                       QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            self.logger.info("Resetting settings to defaults.")
            # Re-create default settings
            default_settings_obj = Settings()
            # Update our editable copy
            self.editable_settings.update(default_settings_obj.to_dict())
            # Repopulate UI fields
            self._populate_fields()
            # Reset restart flag check
            self._check_restart_needed()
            # No need to save here, user must click OK to save defaults


    @Slot()
    def _reset_indicator_position(self):
        """Reset indicator position via the SpeechIndicator instance."""
        if self.speech_indicator:
            self.speech_indicator.reset_position()
            # Optionally update the position in editable_settings here if needed immediately
            # self.editable_settings.indicator_position = {'x': default_x, 'y': default_y} # Get defaults
            QMessageBox.information(self, "Position Reset", "Indicator position has been reset.")
        else:
            QMessageBox.warning(self, "Error", "Speech indicator reference not available.")

    # --- Helper Slots ---
    @Slot(str)
    def _update_cuda_path_state(self, device_text: str):
        """Enable/disable CUDA path entry based on device selection."""
        enable = (device_text == "cuda")
        self.cuda_path_label.setEnabled(enable)
        self.cuda_path_entry.setEnabled(enable)
        self.cuda_path_button.setEnabled(enable)

    @Slot()
    def _browse_cuda_path(self):
        """Open directory dialog to select CUDA path."""
        current_path = self.cuda_path_entry.text()
        cuda_dir = QFileDialog.getExistingDirectory(
            self,
            "Select CUDA bin Directory",
            current_path if os.path.exists(current_path) else "C:/Program Files/" # Sensible default start
        )
        if cuda_dir:
            # faster-whisper might need the *bin* directory
            if not cuda_dir.lower().endswith("bin"):
                 potential_bin = os.path.join(cuda_dir, "bin")
                 if os.path.exists(potential_bin):
                      cuda_dir = potential_bin
                 else:
                      QMessageBox.warning(self, "Path Warning", f"Selected path '{cuda_dir}' doesn't seem to be the CUDA 'bin' directory. Please ensure it's correct.")

            self.cuda_path_entry.setText(cuda_dir)

    @Slot()
    def _check_restart_needed(self):
         """Check if settings requiring restart have changed."""
         changed = False
         # Compare current UI values to initial values loaded when dialog opened
         if self.model_size_combo.currentText() != self._initial_model_size: changed = True
         if self.device_combo.currentText() != self._initial_device: changed = True
         if self.input_device_combo.currentData() != self._initial_device_index: changed = True
         # Sample rate check is handled in advanced dialog if modified there

         self.restart_required = changed
         # Optional: Show a visual indicator if restart is needed
         # self.setWindowTitle("Settings (*Restart Required*)") if changed else self.setWindowTitle("Settings")


    def _show_advanced_audio_settings(self):
        """Show the advanced audio settings dialog."""
        advanced_dialog = AdvancedAudioSettingsDialog(self.editable_settings, self)
        if advanced_dialog.exec() == QDialog.Accepted:
             # Settings were applied directly to self.editable_settings by the dialog
             self.logger.info("Advanced audio settings accepted.")
             # Check if sample rate changed
             if advanced_dialog.sample_rate_changed:
                 self.restart_required = True
                 self._check_restart_needed() # Update main dialog's flag/title if needed
        else:
             self.logger.info("Advanced audio settings cancelled.")

    @Slot(bool)
    def _update_llm_controls_state(self, enabled: bool):
        """Enable/disable LLM settings controls based on checkbox state."""
        # Find the LLM settings group widget
        llm_group = self.use_llm_processing_check.parent().findChildren(QWidget)[1]
        llm_group.setEnabled(enabled)

    @Slot()
    def _fetch_ollama_models(self):
        """Fetch available models from Ollama API."""
        endpoint = self.llm_endpoint_entry.text().strip()
        if not endpoint:
            endpoint = "http://localhost:11434"  # Default endpoint
            self.llm_endpoint_entry.setText(endpoint)
            
        try:
            # Store current selection to restore it later
            current_model = self.llm_model_combo.currentText()
            
            # Clear current items
            self.llm_model_combo.clear()
            
            # Request models from Ollama API
            url = f"{endpoint}/api/tags"
            self.logger.info(f"Fetching models from Ollama API at {url}")
            
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                models = [model["name"] for model in data.get("models", [])]
                
                # Add models to combo box
                if models:
                    self.llm_model_combo.addItems(models)
                    # Restore previous selection if it exists in the new list
                    index = self.llm_model_combo.findText(current_model)
                    if index >= 0:
                        self.llm_model_combo.setCurrentIndex(index)
                    # QMessageBox.information(self, "Models Found", f"Found {len(models)} models from Ollama.")
                else:
                    # Don't add default models, just inform the user to install them
                    QMessageBox.warning(self, "No Models Found", 
                                     "No models found on Ollama server.\n\n"
                                     "Please install models in Ollama first. The recommended model\n"
                                     "is 'gemma3:1b-it-qat' which offers a good balance of speed and quality.\n\n"
                                     "To install: 'ollama pull gemma3:1b-it-qat'")
            else:
                # Don't add default models on connection error
                QMessageBox.warning(self, "Connection Error",
                                 f"Failed to connect to Ollama API at {endpoint}.\n"
                                 f"Error code: {response.status_code}\n\n"
                                 "Please ensure Ollama is running and the endpoint is correct.\n"
                                 "The recommended model is 'gemma3:1b-it-qat' once Ollama is running.")
                
        except requests.RequestException as e:
            # Don't add default models on exception
            self.logger.error(f"Failed to fetch models from Ollama: {e}")
            QMessageBox.warning(self, "Connection Error", 
                             f"Failed to connect to Ollama API at {endpoint}.\n"
                             f"Error: {str(e)}\n\n"
                             "Please ensure Ollama is running and the endpoint is correct.\n"
                             "The recommended model is 'gemma3:1b-it-qat' once Ollama is running.")


class AdvancedAudioSettingsDialog(QDialog):
    """Modal dialog for advanced audio settings."""
    def __init__(self, settings_ref: Settings, parent=None):
        super().__init__(parent)
        self.settings = settings_ref  # Edit the settings object directly
        self._initial_sample_rate = self.settings.sample_rate
        self.sample_rate_changed = False

        self.setWindowTitle("Advanced Audio Settings")
        self.setMinimumWidth(450)

        # Main layout
        layout = QVBoxLayout(self)

        # Scroll Area for settings
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)

        # --- Add sliders using helper ---
        s = self.settings
        res_1f = 0.1  # Resolution for 1 decimal place floats
        res_int = 1  # Resolution for integers

        self.pre_padding_w, self.pre_padding_s = SettingsDialog._create_slider_widget(
            "Pre-padding (s):", 0.1, 1.0, s.pre_padding, resolution=res_1f)

        self.silence_padding_w, self.silence_padding_s = SettingsDialog._create_slider_widget(
            "Silence Padding (s):", 0.1, 1.0, s.silence_padding, resolution=res_1f)

        self.sentence_pause_w, self.sentence_pause_s = SettingsDialog._create_slider_widget(
            "Sentence Pause (s):", 0.2, 2.0, s.sentence_pause_threshold, resolution=res_1f)

        self.sentence_energy_w, self.sentence_energy_s = SettingsDialog._create_slider_widget(
            "Sentence Energy Factor:", 0.1, 1.0, s.sentence_energy_threshold, resolution=res_1f)

        self.min_sentence_w, self.min_sentence_s = SettingsDialog._create_slider_widget(
            "Min Sentence Length (s):", 0.2, 2.0, s.min_sentence_length, resolution=res_1f)

        self.max_sentence_w, self.max_sentence_s = SettingsDialog._create_slider_widget(
            "Max Sentence Length (s):", 5.0, 20.0, s.max_sentence_length, resolution=0.5)

        scroll_layout.addWidget(self.pre_padding_w)
        scroll_layout.addWidget(self.silence_padding_w)
        scroll_layout.addWidget(self.sentence_pause_w)
        scroll_layout.addWidget(self.sentence_energy_w)
        scroll_layout.addWidget(self.min_sentence_w)
        scroll_layout.addWidget(self.max_sentence_w)

        # --- Sample Rate ---
        sr_layout = QHBoxLayout()
        sr_label = QLabel("Sample Rate (Hz):")
        sr_label.setMinimumWidth(150)
        self.sample_rate_combo = QComboBox()
        common_rates = [8000, 16000, 22050, 44100, 48000]
        self.sample_rate_combo.addItems([str(r) for r in common_rates])
        self.sample_rate_combo.setCurrentText(str(s.sample_rate))
        sr_restart = QLabel("(Restart Required)")
        sr_restart.setStyleSheet("font-style: italic; color: gray;")
        sr_layout.addWidget(sr_label)
        sr_layout.addWidget(self.sample_rate_combo)
        sr_layout.addWidget(sr_restart)
        scroll_layout.addLayout(sr_layout)

        scroll_layout.addStretch(1)
        scroll_widget.setLayout(scroll_layout)
        scroll_area.setWidget(scroll_widget)
        layout.addWidget(scroll_area)

        # Dialog buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(self.button_box)

        # Connect signals
        self.button_box.accepted.connect(self._apply_and_accept)
        self.button_box.rejected.connect(self.reject)

    @Slot()
    def _apply_and_accept(self):
        """Apply UI values directly to the referenced settings object."""
        s = self.settings
        s.pre_padding = self.pre_padding_s.value() * 0.1
        s.silence_padding = self.silence_padding_s.value() * 0.1
        s.sentence_pause_threshold = self.sentence_pause_s.value() * 0.1
        s.sentence_energy_threshold = self.sentence_energy_s.value() * 0.1
        s.min_sentence_length = self.min_sentence_s.value() * 0.1
        s.max_sentence_length = self.max_sentence_s.value() * 0.5

        new_rate = int(self.sample_rate_combo.currentText())
        if new_rate != self._initial_sample_rate:
            self.sample_rate_changed = True
        s.sample_rate = new_rate

        self.accept()