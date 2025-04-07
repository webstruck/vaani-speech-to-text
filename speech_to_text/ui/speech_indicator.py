"""
Speech indicator UI for the speech-to-text application (PySide6 version).
Uses a frameless QWidget.
"""

import logging
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QApplication, QSizePolicy
from PySide6.QtGui import QColor, QPainter, QMouseEvent, QScreen, QPaintEvent, QFont
from PySide6.QtCore import Qt, Slot, QPoint, QTimer, QRect
from speech_to_text.models.settings import Settings

class EnergyMeterWidget(QWidget):
    """A simple widget to display an energy level bar."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.energy_level = 0.0  # Normalized 0.0 to 1.0
        self.background_color = QColor("#B71C1C") # Darker red
        self.meter_color = QColor("#FFEB3B") # Yellow
        self.setMinimumHeight(10)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_energy(self, level: float):
        """Set normalized energy level (0.0 to 1.0)."""
        self.energy_level = max(0.0, min(1.0, level))
        self.update() # Trigger repaint

    def paintEvent(self, event: QPaintEvent):
        """Paint the energy meter."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw background
        painter.fillRect(self.rect(), self.background_color)

        # Draw meter bar
        meter_width = int(self.width() * self.energy_level)
        if meter_width > 0:
             meter_rect = QRect(0, 0, meter_width, self.height())
             painter.fillRect(meter_rect, self.meter_color)

        painter.end()


class SpeechIndicator(QWidget):
    """A frameless, always-on-top window to indicate speech recording."""

    # UI constants
    DEFAULT_WIDTH = 220
    DEFAULT_HEIGHT = 60
    HANDLE_HEIGHT = 15 # Approximate area for dragging
    DEFAULT_MARGIN = 40

    def __init__(self, settings, config_manager, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.settings = settings
        self.config_manager = config_manager
        self._drag_position = None
        self._is_visible = False

        self._setup_ui()
        self._load_position()

        # Timer to periodically ensure it stays on top (workaround for some WMs)
        self._topmost_timer = QTimer(self)
        self._topmost_timer.timeout.connect(self._ensure_topmost)
        self._topmost_timer.setInterval(1000) # Check every second when visible

    def _setup_ui(self):
        """Configure window flags and create widgets."""
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |    # No border or title bar
            Qt.WindowType.WindowStaysOnTopHint | # Always on top
            Qt.WindowType.Tool                   # Less likely to get focus, potentially skip taskbar
        )
        # --- START FIX ---
        # Explicitly tell Qt not to activate the window (give it focus) when shown.
        # This is crucial to prevent stealing focus from the target application.
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        # --- END FIX ---

        # Set attribute to delete widget when closed (if it were closable)
        # self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self.setWindowTitle("Speech Indicator")
        self.setFixedSize(self.DEFAULT_WIDTH, self.DEFAULT_HEIGHT) # Fixed size for simplicity

        # --- Styling (similar to Tkinter version) ---
        self.setStyleSheet("""
            QWidget {
                background-color: #E53935; /* Main red background */
                border: 2px solid #C62828; /* Darker red border */
                border-radius: 5px; /* Slightly rounded corners */
            }
            QLabel#TitleLabel {
                color: white;
                font-size: 12pt;
                font-weight: bold;
                border: none; /* Remove border from label */
                background-color: transparent; /* Make background transparent */
                padding-left: 5px;
            }
             QLabel#DragHintLabel {
                color: white;
                font-size: 7pt;
                border: none;
                background-color: #C62828; /* Darker red for handle area bg */
                padding: 2px 5px 2px 5px;
                min-height: 15px; /* Ensure handle area height */
                border-top-left-radius: 3px; /* Match outer radius */
                border-top-right-radius: 3px;
                border-bottom-left-radius: 0px;
                border-bottom-right-radius: 0px;
            }
        """)

        # --- Layout and Widgets ---
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(2, 2, 2, 2) # Margins inside the border
        self.layout.setSpacing(0) # No space between widgets

        # Simulate drag handle area with a label background
        self.drag_handle_label = QLabel("••• Drag to move", self)
        self.drag_handle_label.setObjectName("DragHintLabel")
        self.drag_handle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.drag_handle_label)

        self.indicator_label = QLabel("🎤 Recording Speech", self)
        self.indicator_label.setObjectName("TitleLabel") # For styling
        self.indicator_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.indicator_label, stretch=1) # Allow label to take vertical space

        self.energy_meter = EnergyMeterWidget(self)
        self.layout.addWidget(self.energy_meter)

        self.setLayout(self.layout)
        self.hide() # Start hidden

    def _load_position(self):
        """Load position from settings or set default."""
        position = self.settings.indicator_position
        screen = QApplication.primaryScreen()
        if not screen:
            self.logger.warning("Could not get primary screen info.")
            return

        screen_geometry = screen.availableGeometry() # Geometry excluding taskbar etc.
        default_x = screen_geometry.right() - self.width() - self.DEFAULT_MARGIN
        default_y = screen_geometry.bottom() - self.height() - self.DEFAULT_MARGIN

        if isinstance(position, dict) and "x" in position and "y" in position:
            x = position.get("x", default_x)
            y = position.get("y", default_y)
             # Ensure it's visible on *some* screen
            is_visible = False
            for s in QApplication.screens():
                if s.geometry().contains(x, y):
                    is_visible = True
                    break
            if not is_visible:
                self.logger.warning(f"Saved position ({x},{y}) is off-screen. Resetting.")
                x, y = default_x, default_y
                self._save_position(x, y) # Save the reset position
            self.move(x, y)
        else:
            self.logger.info("No valid indicator position found, using default.")
            self.move(default_x, default_y)
            self._save_position(default_x, default_y) # Save initial default

    def _save_position(self, x=None, y=None):
        """Save the current window position to settings."""
        if x is None or y is None:
            current_pos = self.pos()
            x = current_pos.x()
            y = current_pos.y()

        if self.settings.indicator_position.get("x") != x or self.settings.indicator_position.get("y") != y:
            self.settings.indicator_position = {'x': x, 'y': y}
            if self.config_manager:
                self.config_manager.save_settings(self.settings)
                self.logger.info(f"Saved indicator position: x={x}, y={y}")
            else:
                self.logger.warning("Config manager not available, cannot save indicator position.")

    def reset_position(self):
        """Reset position to default on primary screen."""
        self.logger.info("Resetting indicator position to default.")
        screen = QApplication.primaryScreen()
        if not screen: return
        screen_geometry = screen.availableGeometry()
        default_x = screen_geometry.right() - self.width() - self.DEFAULT_MARGIN
        default_y = screen_geometry.bottom() - self.height() - self.DEFAULT_MARGIN
        self.move(default_x, default_y)
        self._save_position(default_x, default_y)

    def _ensure_topmost(self):
        """Periodically raise the window to ensure it stays on top."""
        if self.isVisible():
            self.raise_()
            # --- START FIX ---
            # Remove activateWindow() to prevent focus stealing
            # self.activateWindow() # Try to bring it forward more forcefully - REMOVED
            # --- END FIX ---

    # --- Dragging Implementation ---
    def mousePressEvent(self, event: QMouseEvent):
        """Capture mouse press event for dragging."""
        if event.button() == Qt.MouseButton.LeftButton:
            # Use globalPos for screen coordinates, pos for window-local
            self._drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        """Move window if dragging."""
        if event.buttons() == Qt.MouseButton.LeftButton and self._drag_position:
            new_pos = event.globalPosition().toPoint() - self._drag_position
            self.move(new_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Stop dragging and save position."""
        if event.button() == Qt.MouseButton.LeftButton and self._drag_position:
            self._save_position() # Save final position
            self._drag_position = None
            event.accept()

    # --- Public Slots ---
    @Slot(bool)
    def show_indicator_slot(self, visible: bool):
        """Slot to show or hide the indicator window."""
        self.logger.debug(f"Slot show_indicator_slot called with: {visible}")
        should_show = visible and self.settings.visual_feedback
        if should_show:
            if not self._is_visible:
                self.logger.info("Showing speech indicator.")
                self.show() # WA_ShowWithoutActivating prevents this from stealing focus
                self.raise_() # Bring to front visually
                # --- START FIX ---
                # Remove activateWindow() to prevent focus stealing
                # self.activateWindow() # REMOVED
                # --- END FIX ---
                self._ensure_topmost() # Immediate check (which also no longer activates)
                if not self._topmost_timer.isActive():
                    self._topmost_timer.start()
                self._is_visible = True
        else:
             if self._is_visible:
                self.logger.info("Hiding speech indicator.")
                self.hide()
                if self._topmost_timer.isActive():
                    self._topmost_timer.stop()
                self._is_visible = False

    @Slot(float)
    def update_energy_slot(self, energy_level: float):
        """Slot to update the energy meter visualization."""
        if self.isVisible() and self.settings.visual_feedback:
             # Normalize energy (assuming threshold is baseline noise * factor)
             # Heuristic: Max energy is maybe 4-5x the silence threshold? Adjust as needed.
             max_expected_energy = self.settings.silence_threshold * (self.settings.speech_energy_threshold + 2) # Estimate
             normalized = 0.0
             if max_expected_energy > 0:
                 normalized = min(1.0, energy_level / max_expected_energy)

             # Clamp small values to make silence more obvious visually
             if normalized < 0.05:
                  normalized = 0.0

             self.energy_meter.set_energy(normalized)

    @Slot(Settings)
    def update_settings(self, new_settings):
        """Update internal settings reference."""
        self.settings = new_settings
        # Re-evaluate visibility based on new settings
        self.show_indicator_slot(self._is_visible) # Force update based on new visual_feedback setting