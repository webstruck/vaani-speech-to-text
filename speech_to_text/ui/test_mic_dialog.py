"""
Microphone test dialog for the speech-to-text application (PySide6 version).
Uses Matplotlib for waveform display.
"""

import logging
import threading
import time
import numpy as np
import pyaudio

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                               QTextEdit, QWidget, QLabel, QMessageBox, QApplication)
from PySide6.QtCore import Qt, Slot, Signal, QObject, QThread, QTimer, QMetaObject

# Matplotlib integration for PySide6 (ensure backend is installed)
import matplotlib
matplotlib.use('QtAgg') # Explicitly use Qt backend
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas


from speech_to_text.models.settings import Settings
from speech_to_text.core.audio_processor import AudioProcessor
from speech_to_text.core.transcriber import Transcriber


# --- Worker Object for Running Test in Separate Thread ---
class MicTestWorker(QObject):
    """Runs the microphone test logic in a separate thread."""
    # Signals to update the UI
    signal_status_update = Signal(str)
    signal_waveform_update = Signal(object, object, int) # times, data, end_idx (use object for numpy arrays)
    signal_finished = Signal()
    signal_error = Signal(str)

    def __init__(self, settings: Settings, audio_processor: AudioProcessor, transcriber: Transcriber):
        super().__init__()
        self.settings = settings
        self.audio_processor = audio_processor
        self.transcriber = transcriber
        self._is_running = False
        self._stop_requested = False
        self.logger = logging.getLogger(__name__)

    @Slot()
    def run_test(self):
        """Execute the microphone test."""
        if self._is_running:
            self.logger.warning("Test already running.")
            return

        self._is_running = True
        self._stop_requested = False
        device_index = self.settings.input_device_index
        self.signal_status_update.emit("Starting microphone test...")

        FORMAT = pyaudio.paInt16
        CHANNELS = 1
        RATE = self.settings.sample_rate
        CHUNK = 1024
        RECORD_SECONDS = 5

        audio = None
        stream = None

        try:
            self.signal_status_update.emit(f"Preparing audio stream (Device Index: {device_index})...")
            audio = pyaudio.PyAudio()

            # Validate device index before opening stream
            try:
                device_info = "Default"
                if device_index is not None:
                     device_info = audio.get_device_info_by_index(device_index).get('name')
                self.signal_status_update.emit(f"Opening stream on: {device_info}...")
            except OSError as e:
                 self.logger.error(f"Invalid audio device index {device_index}: {e}")
                 self.signal_error.emit(f"Error: Invalid audio device (Index: {device_index}).\nPlease select a valid device in Settings.")
                 return # Stop execution

            stream = audio.open(format=FORMAT, channels=CHANNELS,
                                rate=RATE, input=True,
                                frames_per_buffer=CHUNK,
                                input_device_index=device_index)
            self.signal_status_update.emit(f"Recording for {RECORD_SECONDS} seconds...")

            frames = []
            times = np.linspace(0, RECORD_SECONDS, int(RATE * RECORD_SECONDS), endpoint=False)
            audio_data_full = np.zeros(len(times), dtype=np.float32) # Use float32 for normalized data
            max_chunks = int(RATE / CHUNK * RECORD_SECONDS)

            for i in range(max_chunks):
                if self._stop_requested:
                    self.signal_status_update.emit("Recording stopped by user.")
                    break

                try:
                    data = stream.read(CHUNK, exception_on_overflow=False)
                    frames.append(data)

                    # Process chunk for visualization
                    chunk_data = np.frombuffer(data, dtype=np.int16)
                    normalized_chunk = chunk_data.astype(np.float32) / 32768.0

                    start_idx = i * CHUNK
                    end_idx = min(start_idx + CHUNK, len(audio_data_full))
                    if end_idx > start_idx:
                        audio_data_full[start_idx:end_idx] = normalized_chunk[:end_idx-start_idx]

                    # Emit update signal periodically (e.g., 10 times per second)
                    if i % (RATE // CHUNK // 10) == 0 or i == max_chunks - 1:
                         # Send copies to avoid issues if arrays are modified later
                         self.signal_waveform_update.emit(times.copy(), audio_data_full.copy(), end_idx)

                except IOError as e:
                     self.logger.error(f"Stream read error during recording: {e}")
                     self.signal_error.emit(f"Error reading from audio stream: {e}")
                     break # Stop recording on error

            if not self._stop_requested:
                self.signal_status_update.emit("Recording complete. Processing audio...")

            # --- Audio Processing & Transcription ---
            if frames:
                 audio_data_bytes = b''.join(frames)
                 # Use the already collected float data if not stopped early
                 if len(audio_data_bytes) // 2 == len(audio_data_full) and not self._stop_requested:
                      audio_float = audio_data_full
                 else: # Recreate float data if recording was stopped or sizes mismatch
                      audio_np = np.frombuffer(audio_data_bytes, dtype=np.int16)
                      audio_float = audio_np.astype(np.float32) / 32768.0

                 processed_audio = self.audio_processor.preprocess_audio(audio_float)

                 if self.transcriber.stt_model:
                     self.signal_status_update.emit("Transcribing speech...")
                     text = self.transcriber.transcribe(processed_audio)
                     if text and text.strip():
                         self.signal_status_update.emit(f"Transcription result: \"{text}\"")
                     else:
                         self.signal_status_update.emit("No speech detected or transcribed in the recording.")
                 else:
                     self.signal_status_update.emit("Error: Speech recognition model not loaded.")
            else:
                 self.signal_status_update.emit("No audio recorded.")

        except pyaudio.PyAudioError as e:
             self.logger.error(f"PyAudio error during test: {e}", exc_info=True)
             self.signal_error.emit(f"Audio Error: {e}\nCheck selected device and permissions.")
        except Exception as e:
             self.logger.error(f"Unexpected error in microphone test worker: {str(e)}", exc_info=True)
             self.signal_error.emit(f"An unexpected error occurred: {e}")
        finally:
            if stream:
                try:
                    if stream.is_active(): stream.stop_stream()
                    stream.close()
                except Exception as e:
                    self.logger.error(f"Error closing stream: {e}")
            if audio:
                try:
                    audio.terminate()
                except Exception as e:
                    self.logger.error(f"Error terminating PyAudio: {e}")

            self._is_running = False
            self.signal_finished.emit() # Signal that processing is done

    @Slot()
    def request_stop(self):
        """Slot to signal the worker to stop."""
        self.logger.info("Stop requested for microphone test worker.")
        self._stop_requested = True


class TestMicDialog(QDialog):
    """Dialog for testing the microphone using PySide6 and Matplotlib."""

    def __init__(self, settings: Settings, audio_processor: AudioProcessor,
                 transcriber: Transcriber, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.settings = settings
        self.audio_processor = audio_processor
        self.transcriber = transcriber

        self.is_testing = False
        self.worker_thread = None
        self.worker = None

        self._setup_ui()
        self._setup_worker()

    def _setup_ui(self):
        """Create UI elements."""
        self.setWindowTitle("Microphone Test")
        self.setMinimumSize(650, 600) # Adjusted size

        layout = QVBoxLayout(self)

        # --- Waveform Plot ---
        plot_widget = QWidget()
        plot_layout = QVBoxLayout(plot_widget)
        plot_layout.setContentsMargins(0,0,0,0)

        self.figure = Figure(figsize=(6, 3), dpi=100) # Smaller figure
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)
        self.ax.set_ylim([-1.05, 1.05]) # Slightly larger limits
        self.ax.set_xlim([0, 5])  # 5 seconds
        self.ax.set_xlabel('Time (s)', fontsize=9)
        self.ax.set_ylabel('Amplitude', fontsize=9)
        self.ax.grid(True, linestyle='--', alpha=0.6)
        self.line, = self.ax.plot([], [], lw=1, color='#1976D2') # Thinner line
        self.figure.tight_layout(pad=0.5) # Add padding within figure

        plot_layout.addWidget(self.canvas)
        layout.addWidget(plot_widget, stretch=1) # Allow plot to stretch

        # --- Status Area ---
        status_label = QLabel("<b>Status:</b>")
        layout.addWidget(status_label)
        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setFixedHeight(150) # Fixed height for status
        self.status_text.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        layout.addWidget(self.status_text)

        # --- Buttons ---
        button_layout = QHBoxLayout()
        self.test_button = QPushButton("Start Test Recording (5s)")
        self.test_button.setStyleSheet("padding: 5px 10px; font-weight: bold;")
        self.close_button = QPushButton("Close")

        button_layout.addWidget(self.test_button)
        button_layout.addStretch(1)
        button_layout.addWidget(self.close_button)
        layout.addLayout(button_layout)

        # --- Connections ---
        self.test_button.clicked.connect(self._toggle_test)
        self.close_button.clicked.connect(self.reject) # Close dialog on Cancel

        self.setLayout(layout)
        self._update_status("Click 'Start Test' to begin recording.")

    def _setup_worker(self):
        """Initialize the worker object and thread."""
        self.worker_thread = QThread(self)
        self.worker = MicTestWorker(self.settings, self.audio_processor, self.transcriber)
        self.worker.moveToThread(self.worker_thread)

        # Connect worker signals to dialog slots
        self.worker.signal_status_update.connect(self._update_status)
        self.worker.signal_waveform_update.connect(self._update_waveform)
        self.worker.signal_finished.connect(self._test_finished)
        self.worker.signal_error.connect(self._test_error)

        # Connect thread signals
        self.worker_thread.started.connect(self.worker.run_test)
        # Ensure thread quits when worker signals finished (or on error)
        self.worker.signal_finished.connect(self.worker_thread.quit)
        self.worker.signal_error.connect(self.worker_thread.quit)
        # Optional: Wait for thread to actually finish after quit()
        # self.worker_thread.finished.connect(self._thread_cleanup_message)

    # --- Slots ---
    @Slot()
    def _toggle_test(self):
        """Start or stop the microphone test."""
        if not self.is_testing:
            # Start test
            self._clear_plot()
            self.status_text.clear()
            self._update_status("Starting test...")
            self.test_button.setText("Stop Test")
            self.test_button.setEnabled(False) # Disable briefly to prevent rapid clicks
            QTimer.singleShot(500, lambda: self.test_button.setEnabled(True))
            self.is_testing = True
            self.worker_thread.start() # Starts worker.run_test via started signal
        else:
            # Stop test
            self._update_status("Stopping test...")
            self.test_button.setEnabled(False) # Disable while stopping
            if self.worker:
                # Use invokeMethod or signal to call stop on worker thread
                 QMetaObject.invokeMethod(self.worker, "request_stop", Qt.ConnectionType.QueuedConnection)
            # Button will be re-enabled in _test_finished or _test_error

    @Slot(str)
    def _update_status(self, message: str):
        """Append message to the status text area."""
        timestamp = time.strftime('%H:%M:%S')
        self.status_text.append(f"[{timestamp}] {message}")
        self.status_text.verticalScrollBar().setValue(self.status_text.verticalScrollBar().maximum()) # Auto-scroll

    @Slot(object, object, int)
    def _update_waveform(self, times, audio_data, end_idx):
        """Update the waveform plot."""
        if end_idx > 0 and len(times) >= end_idx and len(audio_data) >= end_idx:
             try:
                 self.line.set_data(times[:end_idx], audio_data[:end_idx])
                 # Adjust x-axis limit dynamically if needed, or keep fixed at 5s
                 # self.ax.set_xlim(0, times[end_idx-1] if end_idx > 1 else 5)
                 self.ax.relim() # Recalculate limits if needed (use carefully)
                 self.ax.autoscale_view(tight=True, scalex=True, scaley=False) # Rescale x if needed
                 self.ax.set_ylim([-1.05, 1.05]) # Keep y-axis fixed
                 self.canvas.draw_idle() # Request redraw efficiently
             except Exception as e:
                  self.logger.error(f"Error updating waveform plot: {e}")
                  # Avoid crashing the UI for plot errors
        # else:
        #      self.logger.warning(f"Invalid data received for waveform update: end_idx={end_idx}, times_len={len(times)}, data_len={len(audio_data)}")


    def _clear_plot(self):
        """Clear the waveform plot."""
        self.line.set_data([], [])
        self.ax.set_xlim([0, 5])
        self.canvas.draw_idle()


    @Slot()
    def _test_finished(self):
        """Called when the worker signals it has finished normally."""
        self.logger.info("Mic test worker finished.")
        self.is_testing = False
        self.test_button.setText("Start Test Recording (5s)")
        self.test_button.setEnabled(True)
        # Ensure thread has quit before allowing another start
        if self.worker_thread and self.worker_thread.isRunning():
             self.worker_thread.quit()
             # self.worker_thread.wait(1000) # Optional wait


    @Slot(str)
    def _test_error(self, error_message: str):
        """Called when the worker signals an error."""
        self.logger.error(f"Mic test worker error: {error_message}")
        self._update_status(f"ERROR: {error_message}")
        self.is_testing = False
        self.test_button.setText("Start Test Recording (5s)")
        self.test_button.setEnabled(True)
        QMessageBox.warning(self, "Microphone Test Error", error_message)
         # Ensure thread has quit
        if self.worker_thread and self.worker_thread.isRunning():
             self.worker_thread.quit()


    def closeEvent(self, event):
        """Handle dialog close event."""
        self.logger.info("Test Mic dialog close event triggered.")
        if self.is_testing and self.worker:
            self._update_status("Stopping test due to window close...")
            # Signal worker to stop
            QMetaObject.invokeMethod(self.worker, "request_stop", Qt.ConnectionType.QueuedConnection)

        # Ensure thread is stopped and cleaned up
        if self.worker_thread and self.worker_thread.isRunning():
            self.logger.debug("Requesting worker thread quit...")
            self.worker_thread.quit()
            if not self.worker_thread.wait(1000): # Wait max 1 sec
                self.logger.warning("Worker thread did not quit gracefully on close. Terminating.")
                self.worker_thread.terminate() # Force terminate if needed

        self.logger.info("Accepting close event.")
        event.accept() # Proceed with closing

    # Optional cleanup message
    # def _thread_cleanup_message(self):
    #      self.logger.debug("Worker thread finished signal received.")