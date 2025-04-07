"""
Text insertion utility for Windows platforms.
Provides robust methods to insert text into active applications.
"""

import logging
import time
import platform
import traceback

class TextInserter:
    """
    Utility class for inserting text into active applications on Windows.
    Provides multiple insertion methods with fallbacks for reliability.
    """
    
    def __init__(self):
        """Initialize the text inserter with platform-specific capabilities."""
        self.logger = logging.getLogger(__name__)
        self.is_windows = platform.system() == "Windows"
        
        # Try to import Windows-specific modules if on Windows
        self.win32_available = False
        self.ctypes_available = False
        
        if self.is_windows:
            try:
                import win32clipboard
                import win32con
                import win32gui
                self.win32_available = True
                self.logger.debug("win32 modules loaded successfully")
            except ImportError:
                self.logger.warning("win32 modules not available. Some text insertion methods will be disabled.")
            
            try:
                import ctypes
                self.ctypes_available = True
                self.logger.debug("ctypes module loaded successfully")
            except ImportError:
                self.logger.warning("ctypes module not available. Some text insertion methods will be disabled.")
    
    def insert_text(self, text):
        """
        Insert text using the most robust available method.
        
        Args:
            text: The text to insert
            
        Returns:
            bool: True if text was inserted successfully, False otherwise
        """
        if not text:
            return True  # Nothing to insert
            
        self.logger.debug(f"Attempting to insert text: {text[:20]}{'...' if len(text) > 20 else ''}")
        
        # Try methods in order of preference
        if self.is_windows:
            # Try direct message to control first (most reliable for text fields)
            # if self.win32_available and self._insert_text_direct(text):
            #     return True
                
            # Then try Windows clipboard API (good for most applications)
            if self.win32_available and self._insert_text_clipboard(text):
                return True
                
            # Then try SendInput API (good for applications that don't support clipboard)
            if self.ctypes_available and self._insert_text_sendinput(text):
                return True
        
        # Finally fall back to cross-platform pyautogui method
        return self._insert_text_fallback(text)
    
    def _insert_text_direct(self, text):
        """
        Try to insert text directly to active control using Windows API.
        
        Args:
            text: The text to insert
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.win32_available:
            return False
            
        try:
            import win32gui
            import win32con
            import win32api
            
            # Get handle to focused control
            focused = win32gui.GetFocus()
            
            if focused:
                # Try to send text directly to control
                for char in text:
                    win32api.SendMessage(focused, win32con.WM_CHAR, ord(char), 0)
                
                self.logger.info(f"Inserted text using SendMessage")
                return True
            return False
                
        except Exception as e:
            self.logger.error(f"Error inserting text with SendMessage: {str(e)}")
            self.logger.debug(traceback.format_exc())
            return False
    
    def _insert_text_clipboard(self, text):
        """
        Insert text using Windows clipboard API.
        
        Args:
            text: The text to insert
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.win32_available:
            return False
            
        try:
            import win32clipboard
            import win32con
            import ctypes
            
            user32 = ctypes.windll.user32
            
            # Save original clipboard content
            original = None
            win32clipboard.OpenClipboard()
            try:
                if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                    original = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
            except Exception as e:
                self.logger.warning(f"Could not get original clipboard content: {e}")
            finally:
                win32clipboard.CloseClipboard()
            
            # Set new content
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(text, win32con.CF_UNICODETEXT)
            win32clipboard.CloseClipboard()
            
            # Simulate Ctrl+V
            user32.keybd_event(0x11, 0, 0, 0)  # CTRL down
            user32.keybd_event(0x56, 0, 0, 0)  # V down
            time.sleep(0.05)  # Small delay
            user32.keybd_event(0x56, 0, 2, 0)  # V up
            user32.keybd_event(0x11, 0, 2, 0)  # CTRL up
            
            time.sleep(0.1)  # Short delay
            
            # Restore original clipboard
            if original is not None:
                try:
                    win32clipboard.OpenClipboard()
                    win32clipboard.EmptyClipboard()
                    win32clipboard.SetClipboardText(original, win32con.CF_UNICODETEXT)
                    win32clipboard.CloseClipboard()
                except Exception as e:
                    self.logger.warning(f"Could not restore clipboard: {e}")
            
            self.logger.info("Inserted text using Windows clipboard API")
            return True
        except Exception as e:
            self.logger.error(f"Error inserting text with Windows clipboard API: {str(e)}")
            self.logger.debug(traceback.format_exc())
            return False
    
    def _insert_text_sendinput(self, text):
        """
        Insert text by simulating keystrokes using Windows SendInput API.
        
        Args:
            text: The text to insert
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.ctypes_available:
            return False
            
        try:
            import ctypes
            from ctypes import wintypes
            
            user32 = ctypes.windll.user32
            
            # Define necessary structures and constants
            class KEYBDINPUT(ctypes.Structure):
                _fields_ = [
                    ("wVk", wintypes.WORD),
                    ("wScan", wintypes.WORD),
                    ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD),
                    ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG))
                ]
            
            class INPUT_union(ctypes.Union):
                _fields_ = [
                    ("ki", KEYBDINPUT),
                    ("padding", ctypes.c_ubyte * 24),
                ]
            
            class INPUT(ctypes.Structure):
                _fields_ = [
                    ("type", wintypes.DWORD),
                    ("u", INPUT_union)
                ]
            
            INPUT_KEYBOARD = 1
            KEYEVENTF_UNICODE = 0x0004
            KEYEVENTF_KEYUP = 0x0002
            
            # Function to send a single character
            def send_char(char):
                inp = INPUT()
                inp.type = INPUT_KEYBOARD
                inp.u.ki.wVk = 0
                inp.u.ki.wScan = ord(char)
                inp.u.ki.dwFlags = KEYEVENTF_UNICODE
                inp.u.ki.time = 0
                inp.u.ki.dwExtraInfo = ctypes.pointer(wintypes.ULONG(0))
                
                # Send key down
                user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))
                
                # Send key up
                inp.u.ki.dwFlags |= KEYEVENTF_KEYUP
                user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))
                
                # Small delay between characters
                time.sleep(0.005)
            
            # Type each character
            for char in text:
                send_char(char)
                
            self.logger.info("Inserted text using SendInput API")
            return True
        except Exception as e:
            self.logger.error(f"Error inserting text with SendInput API: {str(e)}")
            self.logger.debug(traceback.format_exc())
            return False
    
    def _insert_text_fallback(self, text):
        """
        Fall back to cross-platform pyautogui method.
        
        Args:
            text: The text to insert
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            import pyperclip
            import pyautogui
            
            # Save original clipboard content
            try:
                original = pyperclip.paste()
            except Exception:
                original = ""
            
            # Copy transcribed text to clipboard
            pyperclip.copy(text)
            
            # Simulate Ctrl+V to paste
            pyautogui.hotkey('ctrl', 'v')
            
            # Wait a bit and restore original clipboard
            time.sleep(0.2)
            try:
                pyperclip.copy(original)
            except Exception as e:
                self.logger.warning(f"Could not restore clipboard: {e}")
            
            self.logger.info("Inserted text using pyautogui fallback")
            return True
        except Exception as e:
            self.logger.error(f"Error inserting text with fallback method: {str(e)}")
            self.logger.debug(traceback.format_exc())
            return False