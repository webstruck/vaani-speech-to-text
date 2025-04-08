# Vaani - Private, Offline, Universal AI Speech-to-Text Desktop App 🎤

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![PyPI version](https://badge.fury.io/py/vaani-speech-to-text.svg)](https://badge.fury.io/py/vaani-speech-to-text)

**Vaani (वाणी)**, meaning "speech" or "voice" in Sanskrit, is an open-source, AI-powered desktop application that provides **private, offline, real-time speech-to-text transcription**. Use your voice to type into **any application** on your desktop – web browsers, text editors, email clients, chat apps, and more. Your voice data is processed **entirely on your local machine**, ensuring your conversations and dictations remain confidential.

Vaani leverages the efficiency of `faster-whisper` and the flexibility of the PySide6 (Qt) framework to create a seamless, secure, and universal dictation experience.

<!-- It's HIGHLY recommended to add a screenshot or GIF demonstrating Vaani in action! -->
<!-- ![Vaani Screenshot](docs/screenshot.png) -->

## ✨ Features
*   **<a name="universal-input"></a>🌐 Universal Input:** Dictate directly into **virtually any application or text field** that accepts keyboard input on your desktop. Works seamlessly across browsers, documents, code editors, chat clients, etc.
*   **🔒 Privacy First - Offline Processing:** All transcription happens locally on your computer. Your voice data is **never sent to the cloud**.
*   **Real-time Transcription:** Speak and watch your words appear in almost any active application.
*   **High-Quality AI Model:** Powered by `faster-whisper`, offering various model sizes (tiny to large) for a balance between speed and accuracy. Models are downloaded once and run locally.
*   **GPU Acceleration:** Supports CUDA (NVIDIA GPUs) for significantly faster *local* transcription (CPU fallback available).
*   **System Tray Control:** Runs conveniently in the system tray for easy access.
*   **Configurable Global Hotkeys:** Start/stop listening, open settings, test microphone, and more with customizable keyboard shortcuts (using the `keyboard` library).
*   **Visual Recording Indicator:** An optional, movable, always-on-top window shows when Vaani is actively listening, including a real-time audio energy meter.
*   **Robust Text Insertion (Windows):** Uses multiple techniques (`pywin32` APIs, fallback methods) for reliable text input across different Windows applications.
*   **Comprehensive Settings:**
    *   Select audio input device.
    *   Choose Whisper model size and processing device (CPU/CUDA).
    *   Adjust audio parameters (silence thresholds, padding).
    *   Configure hotkeys.
    *   Toggle noise reduction.
*   **Microphone Testing Utility:** Includes a tool to visually test your microphone input and perform a sample transcription.
*   **Optional Noise Reduction:** Helps filter out background noise for clearer transcriptions (requires `noisereduce`).

## <a name="privacy--offline-operation"></a> 🔒 Privacy & Offline Operation

A core design principle of Vaani is user privacy.
*   **Local Processing:** Speech recognition is performed entirely on your device using the `faster-whisper` library and downloaded models.
*   **No Cloud Dependency:** Unlike many commercial speech-to-text services, Vaani does not require an internet connection for its core transcription functionality (only for the initial model download if not present) and never sends your audio data to external servers.
*   **Confidentiality:** Your dictations, conversations, or sensitive information spoken while Vaani is active remain on your computer.

## 🎯 Target Audience & Platform

This project is currently aimed primarily at **Python developers and technical users** comfortable with installing Python packages and potentially troubleshooting environment issues.

Vaani has been primarily developed and tested on **Windows**. While the core components use cross-platform libraries (PySide6, faster-whisper), features like global hotkeys (`keyboard`) and the primary text insertion method (`pywin32`) have platform-specific behaviors or requirements:
*   **Windows:** Best supported platform currently. Text insertion is most robust.
*   **Linux/macOS:** May require additional setup (especially for `pyaudio`). Global hotkeys via the `keyboard` library **require root/administrator privileges** and might interfere with system settings. Text insertion relies on the `pyperclip`/`pyautogui` fallback, which may have limitations. Contributions to improve cross-platform support are welcome!

## 🛠️ Prerequisites

*   **Python:** Version 3.10 or higher.
*   **pip:** Python's package installer (usually comes with Python).
*   **Audio Backend (PyAudio):** `pyaudio` installation can sometimes be tricky. You might need:
    *   **Windows:** Usually works out-of-the-box if installing from wheels. Might require Microsoft Visual C++ Build Tools if building from source.
    *   **Linux:** `portaudio19-dev` (Debian/Ubuntu) or `portaudio-devel` (Fedora).
    *   **macOS:** `portaudio` (via Homebrew: `brew install portaudio`).
*   **(Optional) NVIDIA GPU & CUDA:** For GPU acceleration:
    *   A CUDA-compatible NVIDIA GPU.
    *   NVIDIA CUDA Toolkit installed and configured correctly (Vaani attempts to find it via the path specified in Settings, falling back to PATH environment variable on Windows). `faster-whisper` requires specific CUDA versions - check their [documentation](https://github.com/SYSTRAN/faster-whisper?tab=readme-ov-file#gpu) for details.
*   **(Linux/macOS) Root/Admin Privileges:** Required for the `keyboard` library to capture global hotkeys.

## 🚀 Installation

*Install from PyPI:*

```bash
pip install vaani-speech-to-text
```
or 

*Install from GitHub:*

```bash

git clone https://github.com/webstruck/vaani-speech-to-text.git
cd vaani-speech-to-text
uv pip install -r pyproject.toml
```

**Note:** The first time you run Vaani or select a new model size, the `faster-whisper` library will download the required model files (this requires an internet connection). Subsequent uses of that model will be fully offline.

## ▶️ Usage

Once installed, run the application from your terminal:

```bash
vaani
```

The application icon will appear in your system tray.

**Default Hotkeys:**

*   **Toggle Listening:** `Ctrl+Alt+Z`
*   **Open Settings:** `Ctrl+Alt+Q`
*   **Test Microphone:** `Ctrl+Alt+T`
*   **Toggle Debug Mode:** `Ctrl+Alt+D` (Saves audio chunks locally if enabled)
*   **Exit Application:** `Ctrl+Alt+X`

Right-click the system tray icon for menu options (Start/Stop, Settings, Test Mic, Exit).

## ⚙️ Configuration

Settings are stored in a `settings.json` file located in:

*   **Windows:** `%USERPROFILE%\.speech_to_text_app` (e.g., `C:\Users\YourName\.speech_to_text_app`)
*   **Linux/macOS:** `~/.speech_to_text_app` (e.g., `/home/yourname/.speech_to_text_app`)

You can configure various options through the Settings dialog (accessible via hotkey or tray menu), including:

*   Audio input device
*   Whisper model size (`tiny`, `base`, `small`, `medium`, `large`)
*   Processing device (`cpu` or `cuda`)
*   CUDA Toolkit path (if needed)
*   Silence detection parameters
*   Hotkeys
*   UI options (visual indicator)

## 📦 Dependencies

Key dependencies include:

*   `PySide6`: For the graphical user interface.
*   `faster-whisper`: The core **local** AI transcription engine.
*   `keyboard`: For global hotkey management.
*   `pyaudio`: For microphone access.
*   `numpy`, `scipy`: For audio data manipulation and processing.
*   `matplotlib`: For the microphone test waveform display.
*   `pywin32`: (Windows only) For robust text insertion.
*   `pyperclip`, `pyautogui`: Fallback text insertion.
*   `noisereduce`: Optional background noise reduction.

*(See `pyproject.toml` for specific version requirements)*

## 🩺 Troubleshooting

*   **Hotkeys Not Working:**
    *   **Linux/macOS:** Ensure you are running the application with `sudo` or as root (required by the `keyboard` library). This has security implications, be aware!
    *   **All Platforms:** Check for conflicts with other applications using global hotkeys. Ensure the key names in the settings match those expected by the `keyboard` library.
*   **Audio Device Issues:**
    *   Ensure the correct microphone is selected in Settings -> Audio.
    *   Verify `pyaudio` installed correctly for your OS (see Prerequisites).
    *   Check OS-level microphone permissions for Python or the terminal.
    *   Try the "Test Microphone" utility.
*   **Text Not Inserting:**
    *   On Windows, Vaani tries multiple methods. Some specific applications (games, remote desktops, apps running with elevated privileges) might still resist input simulation.
    *   On Linux/macOS, relies on `pyperclip`/`pyautogui`, which might not work in all environments (e.g., Wayland without specific setup).
*   **Slow Transcription:**
    *   If using CPU, select a smaller model size (e.g., `tiny`, `base`, `small`).
    *   If you have a compatible NVIDIA GPU, ensure CUDA is set up correctly and selected as the device in Settings. Remember, all processing is local, so performance depends entirely on your hardware.
*   **Model Download Failed:** Ensure you have an internet connection the first time you select a specific model size. Check for firewall issues blocking the download.

## 🗺️ Future Plans / Roadmap

*   [ ] Create user-friendly installers for Windows (and potentially other platforms).
*   [ ] Improve cross-platform compatibility (text insertion, hotkey alternatives).
*   [ ] Explore alternative transcription backends or customization options (while maintaining offline capability).
*   [ ] Add more post-processing text options.
*   [ ] Language selection for transcription (requires corresponding Whisper models).

## 🙌 Contributing

Contributions are welcome! If you'd like to help improve Vaani, please feel free to:

1.  Fork the repository.
2.  Create a new branch (`git checkout -b feature/YourFeature` or `bugfix/YourBugfix`).
3.  Make your changes.
4.  Commit your changes (`git commit -m 'Add some feature'`).
5.  Push to the branch (`git push origin feature/YourFeature`).
6.  Open a Pull Request.

Please report bugs or suggest features using the GitHub Issues tab.

## 📄 License

Distributed under the **Apache-2.0** License. See `LICENSE` file for more information.

## 🙏 Acknowledgements

*   The team behind [Whisper](https://github.com/openai/whisper) and [faster-whisper](https://github.com/guillaumekln/faster-whisper) for enabling high-quality, local transcription.
*   The developers of [Qt](https://www.qt.io/) and the [PySide6](https://www.qt.io/qt-for-python) project.
*   All the creators of the dependent Python libraries.