"""
Entry point for the speech-to-text application using PySide6.
"""
import sys
import os
from PySide6.QtWidgets import QApplication
from speech_to_text.core.app import SpeechToTextApp

def main():
    """Main entry point for the application."""
    # --- Qt Application Setup ---
    # Must be created before core app that might use Qt features implicitly
    qt_app = QApplication(sys.argv)
    # Prevent application from closing when last window is hidden (for tray icon)
    qt_app.setQuitOnLastWindowClosed(False)

    # --- Core Application Setup ---
    core_app = SpeechToTextApp()

    # Add CUDA DLL directory if on Windows and using CUDA
    if sys.platform == 'win32' and core_app.settings.device == "cuda":
        cuda_path = core_app.settings.cuda_path
        if cuda_path and os.path.exists(cuda_path):
            try:
                # Check if add_dll_directory exists (Python 3.8+)
                if hasattr(os, 'add_dll_directory'):
                    os.add_dll_directory(cuda_path)
                    core_app.logger.info(f"Added CUDA path to DLL directories: {cuda_path}")
                else:
                     # Fallback for older Python: Modify PATH (less ideal)
                     os.environ['PATH'] = cuda_path + os.pathsep + os.environ['PATH']
                     core_app.logger.info(f"Added CUDA path to PATH environment variable: {cuda_path}")
            except Exception as e:
                core_app.logger.error(f"Error configuring CUDA path: {str(e)}")
        elif cuda_path:
             core_app.logger.warning(f"CUDA path specified but not found: {cuda_path}")


    # Initialize and run the core application logic (sets up signals/slots)
    if not core_app.run():
        # Handle initialization errors (e.g., model load failure)
        # Optionally show a Qt message box here
        sys.exit(1) # Exit if core setup fails

    # --- Start Qt Event Loop ---
    exit_code = qt_app.exec()
    core_app.logger.info(f"Qt event loop finished with exit code: {exit_code}")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()