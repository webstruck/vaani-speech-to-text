"""
Main application class for the Speech-to-Text app (PySide6 version).
Coordinates all components and manages the application lifecycle.
Uses Qt Signals and Slots for thread-safe communication.
"""

import threading
import queue
import keyboard
import logging
import time
import os
import sys

# --- Qt Imports ---
from PySide6.QtCore import QObject, Signal, Slot, QTimer, QCoreApplication, QThread
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt, QMetaObject
from PySide6.QtCore import Q_ARG
# --- End Qt Imports ---

from speech_to_text.core.audio_processor import AudioProcessor
from speech_to_text.core.speech_detector import SpeechDetector
from speech_to_text.core.transcriber import Transcriber
from speech_to_text.models.settings import Settings
# --- UI Imports (Now PySide6) ---
from speech_to_text.ui.system_tray import SystemTrayIcon # Keep concept, implementation changes
from speech_to_text.ui.speech_indicator import SpeechIndicator
from speech_to_text.ui.settings_dialog import SettingsDialog
from speech_to_text.ui.test_mic_dialog import TestMicDialog
# --- End UI Imports ---
from speech_to_text.utils.config_manager import ConfigManager
from speech_to_text.utils.logging_setup import setup_logging
from speech_to_text.utils.text_processing import TextProcessor
from speech_to_text.utils.error_handling import log_exceptions, safe_execution
from speech_to_text.utils.text_inserter import TextInserter

# Inherit from QObject to use Signals/Slots
class SpeechToTextApp(QObject):
    """Main application class that coordinates all components (PySide6)."""

    # --- Define Signals for thread-safe UI updates ---
    signal_show_indicator = Signal(bool)
    signal_update_energy = Signal(float)
    signal_show_notification = Signal(str, str) # title, message
    signal_request_exit = Signal() # Signal to cleanly exit the Qt app

    def __init__(self):
        """Initialize the application and its components."""
        super().__init__() # Initialize QObject base class
        self.logger = setup_logging()
        self.logger.info("Initializing SpeechToTextApp (PySide6 version)")

        self.config_manager = ConfigManager()
        self.settings = self.config_manager.load_settings()
        self.text_inserter = TextInserter()

        # Queues for non-UI thread communication remain the same
        self.speech_queue = queue.Queue()
        self.energy_queue = queue.Queue()
        # gui_update_queue is replaced by Qt Signals

        # State variables
        self.active = False
        self.should_process_queue = True
        self.segment_counter = 0
        self.is_processing_queue = False
        self.pending_text = []

        # Initialize core components
        self.text_processor = TextProcessor()
        self.transcriber = Transcriber(self.settings)
        self.audio_processor = AudioProcessor(self.settings, self.config_manager)
        self.speech_detector = SpeechDetector(
            self.settings,
            self.speech_queue,
            self.energy_queue,
            self.segment_counter,
            self.config_manager
        )

        # UI components (PySide6) - initialized in _init_ui
        self.system_tray = None
        self.speech_indicator = None
        # No hidden root needed for PySide6

        # Threading remains similar, but UI updates use signals
        self.detection_thread = None
        self.queue_processor_thread = None
        self.detection_event = threading.Event()

        # Connect the exit signal to Qt's quit slot
        self.signal_request_exit.connect(QCoreApplication.instance().quit)
        # self.diag_timer = QTimer(self)
        # self.diag_timer.timeout.connect(lambda: self.logger.info("--- Diagnostic Timer Tick ---"))
        # self.diag_timer.start(2000) # Log every 2 seconds
        # self.logger.info("Diagnostic timer started.")

    @log_exceptions
    def run(self):
        """Initialize components and return status for Qt app execution."""
        self.logger.info("Setting up core application components...")

        # Load the transcription model
        if not self.transcriber.load_model():
            self.logger.error("Failed to load transcription model.")
            QMessageBox.critical(None, "Error", "Failed to load transcription model. See logs for details.")
            return False

        # self.logger.info("Waiting briefly before registering hotkeys...")
        # time.sleep(1) # Wait for 1 second
        # Register hotkeys (using 'keyboard' library as before)
        if not self.setup_hotkeys():
            self.logger.error("Failed to register hotkeys.")
            QMessageBox.critical(None, "Error", "Failed to register global hotkeys. Check permissions or conflicts.")
            # Don't necessarily exit, user might use tray menu
            # return False # Decide if hotkeys are critical

        # Initialize UI components (Requires QApplication instance)
        if not QApplication.instance():
             self.logger.error("QApplication instance not found before UI initialization.")
             return False
        self._init_ui() # Creates indicator and tray

        # Start the queue processor thread
        self.start_queue_processor()

        # System tray is managed by QApplication event loop, no separate thread needed for pystray
        self.logger.info("Core application setup complete. Qt event loop will handle UI.")
        return True # Setup successful, ready for Qt event loop

    def _init_ui(self):
        """Initialize PySide6 UI components."""
        self.logger.info("Initializing UI components...")
        # Create Speech Indicator (QWidget)
        self.speech_indicator = SpeechIndicator(self.settings, self.config_manager)

        # Create System Tray Icon (QSystemTrayIcon)
        self.system_tray = SystemTrayIcon(
            "Speech to Text",
            self._on_toggle_listening_triggered, # Use internal slots/methods
            self._on_test_microphone_triggered,
            self._on_show_settings_triggered,
            self._on_toggle_debug_mode_triggered,
            self._on_exit_app_triggered
        )
        self.system_tray.show() # Make the tray icon visible

        # --- Connect Signals to Slots ---
        # App signals driving UI updates
        self.signal_show_indicator.connect(self.speech_indicator.show_indicator_slot)
        self.signal_update_energy.connect(self.speech_indicator.update_energy_slot)
        self.signal_show_notification.connect(self.system_tray.show_message_slot)

        # Connect tray actions to app logic handlers (internal methods for clarity)
        # Already passed callbacks during SystemTrayIcon init

        self.logger.info("UI components initialized and signals connected.")

    # --- Internal Slots for Tray Actions ---
    @Slot()
    def _on_toggle_listening_triggered(self):
        self.toggle_listening()

    @Slot()
    def _on_test_microphone_triggered(self):
        self.test_microphone()

    @Slot()
    def _on_show_settings_triggered(self):
        self.show_settings()

    @Slot()
    def _on_toggle_debug_mode_triggered(self):
        self.toggle_debug_mode()

    @Slot()
    def _on_exit_app_triggered(self):
        self.exit_app()

    def _trigger_toggle_listening(self):
        # self.logger.debug("Hotkey toggle triggered from keyboard thread") # Optional logging
        QMetaObject.invokeMethod(self, "toggle_listening", Qt.ConnectionType.QueuedConnection)

    def _trigger_show_settings(self):
        # self.logger.debug("Hotkey settings triggered from keyboard thread") # Optional logging
        QMetaObject.invokeMethod(self, "show_settings", Qt.ConnectionType.QueuedConnection)

    def _trigger_test_microphone(self):
        # self.logger.debug("Hotkey test mic triggered from keyboard thread") # Optional logging
        QMetaObject.invokeMethod(self, "test_microphone", Qt.ConnectionType.QueuedConnection)

    def _trigger_toggle_debug_mode(self):
        # self.logger.debug("Hotkey debug triggered from keyboard thread") # Optional logging
        QMetaObject.invokeMethod(self, "toggle_debug_mode", Qt.ConnectionType.QueuedConnection)

    def _trigger_exit_app(self):
        # Exit app likely already handles threading correctly via signals/event loop,
        # but consistency doesn't hurt.
        QMetaObject.invokeMethod(self, "exit_app", Qt.ConnectionType.QueuedConnection)
    # --- End Internal Slots ---

    @safe_execution(default_value=False)
    def setup_hotkeys(self):
        """Register all global hotkeys (using 'keyboard' library)."""
        try:
            # *** CHANGE CALLBACKS TO INTERNAL TRIGGER METHODS ***
            keyboard.add_hotkey(self.settings.hotkey, self._trigger_toggle_listening)
            self.logger.info(f"Listening hotkey registered: {self.settings.hotkey}")

            keyboard.add_hotkey(self.settings.exit_hotkey, self._trigger_exit_app) # Use trigger for consistency
            self.logger.info(f"Exit hotkey registered: {self.settings.exit_hotkey}")

            keyboard.add_hotkey(self.settings.settings_hotkey, self._trigger_show_settings)
            self.logger.info(f"Settings hotkey registered: {self.settings.settings_hotkey}")

            keyboard.add_hotkey(self.settings.debug_hotkey, self._trigger_toggle_debug_mode)
            self.logger.info(f"Debug hotkey registered: {self.settings.debug_hotkey}")

            keyboard.add_hotkey(self.settings.test_hotkey, self._trigger_test_microphone)
            self.logger.info(f"Test hotkey registered: {self.settings.test_hotkey}")

            return True
        # except AttributeError as e: # Catch the specific error you saw
        #      self.logger.error(f"Error registering hotkeys (likely keyboard lib issue): {e}", exc_info=True)
        #      self.signal_show_notification.emit("Hotkey Error", f"Failed to init keyboard library: {e}")
        #      return False
        except Exception as e:
            self.logger.error(f"Error registering hotkeys: {str(e)}", exc_info=True) # Log full traceback
            # Use signal for thread safety if run() is called before event loop starts fully
            self.signal_show_notification.emit("Warning", f"Could not register hotkey(s): {e}")
            return False # Return False but don't make it fatal

    @Slot() # Mark as a Slot
    def toggle_listening(self):
        self.logger.info(f"Toggle listening: active={self.active}, speech_indicator exists={self.speech_indicator is not None}")
        if not self.active:
            # Start listening
            self.active = True
            self.logger.info("Listening started")
            self.detection_event.clear()

            # Emit signal to show indicator
            self.signal_show_indicator.emit(True)
            self.signal_show_notification.emit("Listening Started", "Speak now...")

            with threading.Lock(): # Ensure thread-safe access if needed elsewhere
                self.pending_text = []

            # Start detection thread
            if self.detection_thread is None or not self.detection_thread.is_alive():
                self.detection_thread = threading.Thread(target=self._listen_and_transcribe)
                self.detection_thread.daemon = True
                self.detection_thread.start()
            else:
                 self.logger.warning("Detection thread already running? Signalling start anyway.")
                 # This case shouldn't ideally happen if state is managed correctly

        else:
            # Stop listening
            self.active = False
            self.logger.info("Listening stopped")
            self.detection_event.set() # Signal thread to terminate

            # Emit signal to hide indicator
            self.signal_show_indicator.emit(False)
            self.signal_show_notification.emit("Listening Stopped", "Voice input disabled")

            # Wait briefly for thread to stop processing current chunk
            if self.detection_thread and self.detection_thread.is_alive():
                 self.logger.info("Waiting briefly for detection thread...")
                 self.detection_thread.join(timeout=0.5) # Short wait, don't block UI long

            # Force stop audio processing if needed (detector should handle this via event)
            self._force_stop_audio_capture() # Call the existing method

            remaining = self.speech_queue.qsize()
            if remaining > 0:
                self.logger.info(f"Processing {remaining} remaining speech segments...")
            # Queue processor thread will continue until empty if active=False

    def _force_stop_audio_capture(self):
        """Ensure audio processor stream is stopped."""
        try:
            if hasattr(self, 'audio_processor'):
                self.audio_processor.stop_stream()
            # The detection_event should handle the SpeechDetector loop termination
            # Joining is handled in toggle_listening and exit_app
        except Exception as e:
            self.logger.error(f"Error stopping audio stream: {str(e)}")

    def _listen_and_transcribe(self):
        """Target method for the detection thread."""
        try:
            self.segment_counter = 0 # Reset counter each time listening starts
            # Pass the active flag reference and termination event
            # The 'active' flag is checked within start_detection now
            self.speech_detector.start_detection(lambda: self.active, self.segment_counter, self.detection_event)
        except Exception as e:
            self.logger.error(f"Error in speech detection thread: {str(e)}")
            import traceback
            self.logger.error(traceback.format_exc())
        finally:
            self.logger.info("Detection thread finished.")
             # Ensure state consistency if thread exits unexpectedly
            if self.active:
                self.logger.warning("Detection thread exited while app was still active. Forcing stop.")
                # Use QTimer to schedule the state change back on the main thread
                # to avoid potential race conditions with UI signals
                QTimer.singleShot(0, self.force_stop_listening_from_thread)


    @Slot() # Make it a slot if called via QTimer
    def force_stop_listening_from_thread(self):
        """Safely stops listening if the detection thread crashes."""
        if self.active:
            self.logger.warning("Forcing listening stop due to unexpected detection thread exit.")
            self.active = False
            self.signal_show_indicator.emit(False)
            self.signal_show_notification.emit("Error", "Audio detection stopped unexpectedly.")
            self._force_stop_audio_capture()


    def start_queue_processor(self):
        """Start the speech processing queue worker thread."""
        if self.queue_processor_thread is None or not self.queue_processor_thread.is_alive():
            self.is_processing_queue = True
            self.queue_processor_thread = threading.Thread(target=self.process_speech_queue)
            self.queue_processor_thread.daemon = True
            self.queue_processor_thread.start()
            self.logger.info("Speech queue processor thread started")
        else:
             self.logger.warning("Queue processor thread already running.")


    def stop_queue_processor(self):
        """Stop the queue processor thread."""
        self.logger.info("Stopping speech queue processor thread...")
        self.is_processing_queue = False
        # No need to join here usually, let it finish processing naturally
        # unless explicitly needed during shutdown.

    def process_speech_queue(self):
        """Process speech segments from the queue (runs in its own thread)."""
        last_transcription_time = None
        sentence_buffer = []

        while self.is_processing_queue:
            segment = None
            try:
                # Get speech segment with timeout
                segment = self.speech_queue.get(timeout=0.2) # Smaller timeout for responsiveness

                current_time = time.time()
                processed_audio = None
                text = None

                try:
                    processed_audio = self.audio_processor.preprocess_audio(segment.audio_data)
                    text = self.transcriber.transcribe(processed_audio)
                finally:
                    # Explicitly release large buffers earlier
                    if hasattr(segment, 'audio_data'): segment.audio_data = None
                    if processed_audio is not None: del processed_audio
                    # Ensure task_done is called even on error inside try
                    self.speech_queue.task_done()


                if text and len(text.strip()) > 0:
                    cleaned_text = self.text_processor.post_process_text(text)

                    is_continuous = (last_transcription_time is not None and
                                     current_time - last_transcription_time < self.settings.sentence_pause_threshold)

                    if is_continuous:
                        sentence_buffer.append(cleaned_text)
                        combined_text = " ".join(sentence_buffer)
                        # Check if potential end of sentence detected by transcription or punctuation
                        if any(cleaned_text.rstrip().endswith(end) for end in '.!?'):
                            self.insert_text(combined_text + " ")
                            sentence_buffer = []
                    else:
                        # Process previous buffer if exists
                        if sentence_buffer:
                             self.insert_text(" ".join(sentence_buffer) + " ")
                        # Start new buffer
                        sentence_buffer = [cleaned_text]

                    last_transcription_time = current_time

            except queue.Empty:
                # No speech segments, check energy queue and buffer timeout
                pass
            except Exception as e:
                self.logger.error(f"Error processing speech segment in queue: {str(e)}")
                import traceback
                self.logger.error(traceback.format_exc())
                # Ensure task_done is called if exception happened before finally block
                if segment:
                     try: self.speech_queue.task_done()
                     except ValueError: pass # May already be done


            # Process energy updates (non-blocking) outside speech segment processing
            try:
                while not self.energy_queue.empty():
                    energy = self.energy_queue.get_nowait()
                    # Emit signal to update UI (thread-safe)
                    self.signal_update_energy.emit(energy)
                    self.energy_queue.task_done()
            except queue.Empty:
                pass
            except Exception as e:
                self.logger.error(f"Error processing energy queue: {e}")

            # Handle sentence buffer timeout
            if sentence_buffer and (last_transcription_time is None or
                time.time() - last_transcription_time > self.settings.sentence_pause_threshold):
                self.insert_text(" ".join(sentence_buffer) + " ")
                sentence_buffer = []
                last_transcription_time = None # Reset timestamp

            # Small sleep if both queues were empty to prevent busy-waiting
            if segment is None and self.energy_queue.empty():
                 time.sleep(0.05) # Reduce CPU usage when idle

        self.logger.info("Speech queue processor thread finished.")


    def insert_text(self, text):
        self.logger.info(f"Qt event loop running: {QCoreApplication.instance().thread() == QThread.currentThread()}")
        self.logger.info(f"insert_text called from thread: {QThread.currentThread()}")
        """Insert transcribed text into the active application."""
        if not text: 
            return
        self.logger.info(f"Queueing text insertion: {text[:30]}...")
        # Text insertion might involve focus changes or delays, run in main thread
        # using QTimer.singleShot to avoid blocking the queue processor thread.
        # QTimer.singleShot(0, lambda t=text: self._execute_insert_text(t))
        # def schedule_insertion():
        #     self.logger.debug(f"Timer lambda executing for text: '{text[:30]}...'") # Add log here
        #     self._execute_insert_text(text)

        # self.logger.info(f"insert_text scheduling QTimer for: '{text[:30]}...'")
        # QTimer.singleShot(0, schedule_insertion) # Use a named function
        # schedule_insertion() # Directly call for simplicity in this context
        

        QMetaObject.invokeMethod(
            self,                       # target object (self)
            "_execute_insert_text",     # method name (slot)
            Qt.QueuedConnection,        # queued connection type
            Q_ARG(str, text)            # wrap the argument with Q_ARG
        )

    @Slot(str)
    def _execute_insert_text(self, text):
        """Executes text insertion in the main GUI thread."""
        try:
            # ***** LOGGING POINT 7: Check if this method is reached *****
            self.logger.info(f"!!! _execute_insert_text INVOKED with: '{text[:30]}...'") # Keep this as the first line inside try
            success = self.text_inserter.insert_text(text)
            if not success:
                self.logger.error(f"Failed to insert text: {text[:30]}{'...' if len(text) > 30 else ''}")
        except Exception as e:
            # ***** LOGGING POINT 8: Catch early exceptions *****
            self.logger.critical(f"*** CRITICAL ERROR inside _execute_insert_text BEFORE core logic: {e}", exc_info=True)

    @Slot() # Mark as a Slot
    @safe_execution()
    def test_microphone(self):
        """Show the microphone test dialog (modal)."""
        self.logger.info("Showing Microphone Test dialog.")
        # Pass None as parent if you want it to be a standalone window,
        # or pass a main window reference if you have one.
        dialog = TestMicDialog(self.settings, self.audio_processor, self.transcriber, parent=None)
        dialog.exec() # Show modally
        self.logger.info("Microphone Test dialog closed.")

    @Slot() # Mark as a Slot
    @safe_execution()
    def show_settings(self):
        """Show the settings dialog (modal)."""
        self.logger.info("Showing Settings dialog.")
        dialog = SettingsDialog(self.settings, self.config_manager, self.speech_indicator, parent=None)
        # Use exec() for modal dialog behavior, which returns QDialog.Accepted or QDialog.Rejected
        if dialog.exec() == SettingsDialog.Accepted:
            new_settings = dialog.get_updated_settings()
            if new_settings:
                self.logger.info("Settings accepted.")
                self.settings = new_settings
                # No need to save here, dialog saves on accept
                # self.config_manager.save_settings(self.settings) # Dialog handles saving

                # Update components with new settings
                self.speech_detector.update_settings(self.settings)
                self.audio_processor.update_settings(self.settings)
                if self.speech_indicator:
                    self.speech_indicator.update_settings(self.settings) # Update indicator settings if needed

                # Update hotkeys
                keyboard.clear_all_hotkeys()
                self.setup_hotkeys() # Re-registers all hotkeys

                self.signal_show_notification.emit("Settings Updated", "Settings saved successfully.")
                # Inform user about potential restart needs
                if dialog.restart_required:
                    QMessageBox.information(None, "Restart Required",
                                           "Some settings require an application restart to take effect (e.g., model size, device, sample rate).")

            else:
                 self.logger.warning("Settings dialog accepted, but no settings returned.")
        else:
            self.logger.info("Settings dialog cancelled.")

    @Slot() # Mark as a Slot
    @safe_execution()
    def toggle_debug_mode(self):
        """Toggle debug mode."""
        self.settings.debug_mode = not self.settings.debug_mode
        status = "enabled" if self.settings.debug_mode else "disabled"
        self.logger.info(f"Debug mode {status}")
        self.signal_show_notification.emit("Debug Mode", f"Audio saving {status}")
        self.config_manager.save_settings(self.settings)

    @Slot() # Mark as a Slot
    def exit_app(self):
        """Initiate the application shutdown sequence."""
        self.logger.info("Exit requested.")

        # 1. Stop accepting new work & signal threads
        self.active = False
        self.stop_queue_processor() # Set flag to false
        if hasattr(self, 'detection_event'):
            self.detection_event.set()

        self.logger.info("Stopping background threads...")

        # 2. Wait for threads to finish (with timeouts)
        if self.detection_thread and self.detection_thread.is_alive():
            self.logger.debug("Waiting for detection thread...")
            self.detection_thread.join(timeout=1.0)
            if self.detection_thread.is_alive():
                self.logger.warning("Detection thread did not terminate gracefully.")

        if self.queue_processor_thread and self.queue_processor_thread.is_alive():
            self.logger.debug("Waiting for queue processor thread...")
            self.queue_processor_thread.join(timeout=1.0) # Should finish quickly once flag is false
            if self.queue_processor_thread.is_alive():
                self.logger.warning("Queue processor thread did not terminate gracefully.")

        # 3. Clean up resources
        self.logger.info("Cleaning up resources...")
        self._force_stop_audio_capture() # Ensure PyAudio stream is closed
        if hasattr(self, 'audio_processor'):
            self.audio_processor.cleanup() # Terminate PyAudio

        # 4. Unregister hotkeys (important!)
        try:
            keyboard.remove_all_hotkeys()
            self.logger.info("Global hotkeys unregistered.")
        except Exception as e:
            self.logger.error(f"Error unregistering hotkeys: {e}")

        # 5. Clean up UI (Qt handles widget destruction, but hide tray)
        if self.system_tray:
            self.system_tray.hide()
            # self.system_tray.deleteLater() # Schedule for deletion if needed

        # 6. Signal Qt application to quit
        self.logger.info("Requesting Qt application quit.")
        self.signal_request_exit.emit()