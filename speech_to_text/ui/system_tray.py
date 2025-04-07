"""
System tray icon for the speech-to-text application (PySide6 version).
Uses QSystemTrayIcon.
"""
import logging
from PySide6.QtWidgets import QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon, QAction, QPainter, QColor, QPixmap
from PySide6.QtCore import Slot
from PySide6.QtCore import Qt, QRect

class SystemTrayIcon(QSystemTrayIcon):
    """Manages the system tray icon and menu using QSystemTrayIcon."""

    def __init__(self, tooltip: str,
                 toggle_callback: Slot, test_callback: Slot,
                 settings_callback: Slot, debug_callback: Slot,
                 exit_callback: Slot, parent=None):
        """
        Initialize the system tray icon.

        Args:
            tooltip: Tooltip text for the icon.
            toggle_callback: Slot to call when 'Start/Stop' is triggered.
            test_callback: Slot to call when 'Test Mic' is triggered.
            settings_callback: Slot to call when 'Settings' is triggered.
            debug_callback: Slot to call when 'Debug Mode' is triggered.
            exit_callback: Slot to call when 'Exit' is triggered.
            parent: Parent QObject.
        """
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)

        # Create icon
        icon = self._create_icon_pixmap()
        self.setIcon(icon)
        self.setToolTip(tooltip)

        # Create context menu
        self.menu = QMenu()

        # Create actions and connect them to the provided callbacks (slots)
        self.toggle_action = QAction("Start/Stop Listening", self)
        self.toggle_action.triggered.connect(toggle_callback)
        self.menu.addAction(self.toggle_action)

        self.test_action = QAction("Test Microphone", self)
        self.test_action.triggered.connect(test_callback)
        self.menu.addAction(self.test_action)

        self.menu.addSeparator()

        self.settings_action = QAction("Settings", self)
        self.settings_action.triggered.connect(settings_callback)
        self.menu.addAction(self.settings_action)

        self.debug_action = QAction("Toggle Debug Mode", self)
        self.debug_action.triggered.connect(debug_callback)
        self.menu.addAction(self.debug_action)

        self.menu.addSeparator()

        self.exit_action = QAction("Exit", self)
        self.exit_action.triggered.connect(exit_callback)
        self.menu.addAction(self.exit_action)

        # Set the context menu
        self.setContextMenu(self.menu)

        # Optional: Handle left-click activation (e.g., toggle listening)
        # self.activated.connect(self.handle_activation)

        self.logger.info("System tray icon initialized.")

    def _create_icon_pixmap(self) -> QIcon:
        """Create the icon image as a QPixmap."""
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent) # Start with transparent

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw a simple microphone icon (adjust colors/shapes as needed)
        mic_body_color = QColor(0, 120, 212) # Blue
        mic_head_color = QColor(200, 200, 200) # Light Gray

        # Stand/Base (optional)
        # painter.setBrush(mic_body_color)
        # painter.drawRect(28, 40, 8, 10)

        # Body
        painter.setBrush(mic_body_color)
        painter.setPen(Qt.PenStyle.NoPen)
        body_rect = QRect(24, 22, 16, 20) # x, y, w, h
        painter.drawRoundedRect(body_rect, 4, 4)

        # Head (circle/ellipse)
        painter.setBrush(mic_head_color)
        head_rect = QRect(20, 12, 24, 16) # x, y, w, h
        painter.drawEllipse(head_rect)

        painter.end()
        return QIcon(pixmap)

    # --- Public Slots ---
    @Slot(str, str, QSystemTrayIcon.MessageIcon, int)
    def show_message_slot(self, title: str, message: str,
                          icon: QSystemTrayIcon.MessageIcon = QSystemTrayIcon.MessageIcon.Information,
                          msecs: int = 3000):
        """Slot to display a system tray notification."""
        self.logger.debug(f"Showing notification: Title='{title}', Message='{message}'")
        self.showMessage(title, message, icon, msecs)

    # Optional: Handle activation reason (left click, double click etc)
    # def handle_activation(self, reason):
    #     if reason == QSystemTrayIcon.ActivationReason.Trigger: # Left click
    #         # Example: toggle listening on left click
    #         self.toggle_action.trigger()
    #     elif reason == QSystemTrayIcon.ActivationReason.Context: # Right click
    #         pass # Menu is shown automatically