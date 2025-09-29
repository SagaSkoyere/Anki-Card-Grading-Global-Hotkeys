import subprocess
import tempfile
import datetime
import os
import threading
import atexit
from aqt import mw, gui_hooks
from aqt.utils import tooltip, showInfo
from anki.hooks import addHook, remHook

# Try to import Qt components for Windows message handling and always-on-top functionality
try:
    from PyQt5.QtCore import Qt, QAbstractNativeEventFilter, QCoreApplication
    from PyQt5.QtWidgets import QShortcut
    from PyQt5.QtGui import QKeySequence
    import struct
except ImportError:
    try:
        from PyQt6.QtCore import Qt, QAbstractNativeEventFilter, QCoreApplication
        from PyQt6.QtWidgets import QShortcut
        from PyQt6.QtGui import QKeySequence
        import struct
    except ImportError:
        Qt = None
        QShortcut = None
        QKeySequence = None
        QAbstractNativeEventFilter = None
        QCoreApplication = None

# Setup debug logging
addon_dir = os.path.dirname(__file__)
debug_file = os.path.join(tempfile.gettempdir(), "anki_hotkey_debug.txt")

def debug_log(message):
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    with open(debug_file, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")
    print(message)  # Also print to console

# Clear previous debug log
try:
    with open(debug_file, "w", encoding="utf-8") as f:
        f.write(f"=== Anki AutoHotkey Global Hotkeys Debug Log Started at {datetime.datetime.now()} ===\n")
        f.write(f"Debug file location: {debug_file}\n\n")
except Exception as e:
    print(f"Could not create debug file: {e}")

class WindowsMessageFilter(QAbstractNativeEventFilter):
    """Filter to handle Windows messages from AutoHotkey PostMessage calls"""

    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        # Define custom message constants (WM_USER + offset)
        self.WM_ANKI_GOOD = 0x464   # WM_USER + 100
        self.WM_ANKI_AGAIN = 0x465  # WM_USER + 101
        self.WM_ANKI_TOGGLE_TOP = 0x466  # WM_USER + 102
        debug_log("WindowsMessageFilter initialized")

    def nativeEventFilter(self, eventType, message):
        """Handle native Windows messages"""
        try:
            if eventType == "windows_generic_MSG" or eventType == "windows_dispatcher_MSG":
                # Parse Windows message structure
                msg = struct.unpack('PPPPP', message[:struct.calcsize('PPPPP')])
                hwnd, msg_type, wparam, lparam, time = msg

                debug_log(f"Received Windows message: type={hex(msg_type)}, wparam={wparam}, lparam={lparam}")

                # Handle our custom messages
                if msg_type == self.WM_ANKI_GOOD:
                    debug_log("Received GOOD score message from AHK")
                    self.controller._score_card('good')
                    return True, 0
                elif msg_type == self.WM_ANKI_AGAIN:
                    debug_log("Received AGAIN score message from AHK")
                    self.controller._score_card('again')
                    return True, 0
                elif msg_type == self.WM_ANKI_TOGGLE_TOP:
                    debug_log("Received TOGGLE_TOP message from AHK")
                    self.controller.toggle_always_on_top()
                    return True, 0

        except Exception as e:
            debug_log(f"Error in nativeEventFilter: {e}")

        return False, 0

class AHKGlobalHotkeyController:
    def __init__(self):
        self.ahk_process = None
        self.ahk_script_path = None
        self.reviewer_active = False
        self.always_on_top_enabled = False
        self.qt_shortcuts = []
        self.message_filter = None

    def start_global_hotkeys(self):
        """Start AutoHotkey global hotkeys when reviewing begins"""
        debug_log("start_global_hotkeys called")

        if self.ahk_process is not None:
            debug_log("AutoHotkey process already running")
            return

        # Check if AutoHotkey.exe exists
        ahk_exe_path = os.path.join(addon_dir, "ahk", "AutoHotkey.exe")
        if not os.path.exists(ahk_exe_path):
            error_msg = f"AutoHotkey.exe not found at {ahk_exe_path}"
            debug_log(error_msg)
            showInfo(f"Global Hotkeys Error: {error_msg}\\n\\nPlease reinstall the addon.")
            return

        # Get AHK script path
        ahk_script_path = os.path.join(addon_dir, "ahk", "anki_hotkeys.ahk")
        if not os.path.exists(ahk_script_path):
            error_msg = f"AutoHotkey script not found at {ahk_script_path}"
            debug_log(error_msg)
            showInfo(f"Global Hotkeys Error: {error_msg}\\n\\nPlease reinstall the addon.")
            return

        try:
            # Start AutoHotkey process
            debug_log(f"Starting AutoHotkey process: {ahk_exe_path} {ahk_script_path}")
            self.ahk_process = subprocess.Popen(
                [ahk_exe_path, ahk_script_path],
                cwd=os.path.join(addon_dir, "ahk"),
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            debug_log(f"AutoHotkey process started with PID: {self.ahk_process.pid}")

            # Setup Windows message filter to catch PostMessage calls from AHK
            self._setup_windows_message_filter()

            tooltip("🎯 Global hotkeys active!\\n\\nCtrl+Z = Good, Ctrl+X = Again, Ctrl+O = Always on top\\nWorks everywhere - even when Anki is not in focus!", period=4000)

        except Exception as e:
            error_msg = f"Failed to start AutoHotkey: {e}"
            debug_log(error_msg)
            showInfo(f"Global Hotkeys Error: {error_msg}\\n\\nTry running Anki as administrator or check if antivirus is blocking AutoHotkey.")

    def stop_global_hotkeys(self):
        """Stop AutoHotkey global hotkeys when reviewing ends"""
        debug_log("stop_global_hotkeys called")

        if self.ahk_process is not None:
            try:
                debug_log(f"Terminating AutoHotkey process PID: {self.ahk_process.pid}")
                self.ahk_process.terminate()
                self.ahk_process.wait(timeout=3)
                debug_log("AutoHotkey process terminated successfully")
            except subprocess.TimeoutExpired:
                debug_log("AutoHotkey process did not terminate gracefully, forcing kill")
                self.ahk_process.kill()
            except Exception as e:
                debug_log(f"Error stopping AutoHotkey process: {e}")
            finally:
                self.ahk_process = None

        # Clean up Windows message filter
        if self.message_filter and QCoreApplication.instance():
            try:
                QCoreApplication.instance().removeNativeEventFilter(self.message_filter)
                debug_log("Windows message filter removed")
            except Exception as e:
                debug_log(f"Error removing Windows message filter: {e}")
            finally:
                self.message_filter = None

        # Clean up Qt shortcuts (legacy cleanup)
        for shortcut in self.qt_shortcuts:
            try:
                shortcut.deleteLater()
            except Exception as e:
                debug_log(f"Error deleting Qt shortcut: {e}")
        self.qt_shortcuts.clear()
        debug_log("Cleanup completed")

    def _setup_windows_message_filter(self):
        """Setup Windows message filter to catch PostMessage calls from AutoHotkey"""
        if not QAbstractNativeEventFilter or not QCoreApplication.instance():
            debug_log("Cannot setup Windows message filter: Qt components not available")
            return

        try:
            # Remove existing filter if any
            if self.message_filter:
                QCoreApplication.instance().removeNativeEventFilter(self.message_filter)

            # Create and install new message filter
            self.message_filter = WindowsMessageFilter(self)
            QCoreApplication.instance().installNativeEventFilter(self.message_filter)
            debug_log("Windows message filter installed successfully")

        except Exception as e:
            debug_log(f"Failed to setup Windows message filter: {e}")
            # Fallback to function key shortcuts for compatibility
            self._setup_function_key_shortcuts_fallback()

    def _setup_function_key_shortcuts_fallback(self):
        """Fallback to Qt shortcuts if Windows message filter fails"""
        debug_log("Setting up fallback Qt shortcuts")
        if not QShortcut or not mw:
            debug_log("Cannot setup Qt shortcuts: QShortcut or mw not available")
            return

        # Clear existing shortcuts
        for shortcut in self.qt_shortcuts:
            try:
                shortcut.deleteLater()
            except Exception as e:
                debug_log(f"Error deleting existing Qt shortcut: {e}")
        self.qt_shortcuts.clear()

        # Function key mappings (sent by AutoHotkey)
        shortcuts = [
            ("F13", lambda: self._score_card('good'), "Score card as Good (from AHK Ctrl+Z)"),
            ("F14", lambda: self._score_card('again'), "Score card as Again (from AHK Ctrl+X)"),
            ("F15", lambda: self.toggle_always_on_top(), "Toggle always on top (from AHK Ctrl+O)")
        ]

        success_count = 0
        for key_combination, callback, description in shortcuts:
            try:
                key_seq = QKeySequence(key_combination)
                if key_seq.isEmpty():
                    debug_log(f"Invalid key sequence: {key_combination}")
                    continue

                shortcut = QShortcut(key_seq, mw)
                shortcut.activated.connect(callback)
                shortcut.setContext(Qt.ApplicationShortcut)  # Work anywhere in Anki

                self.qt_shortcuts.append(shortcut)
                success_count += 1
                debug_log(f"Created fallback Qt shortcut: {key_combination} - {description}")

            except Exception as e:
                debug_log(f"Failed to create Qt shortcut {key_combination}: {e}")

        debug_log(f"Successfully created {success_count}/{len(shortcuts)} fallback Qt shortcuts")

    def _score_card(self, score):
        """Score the current card"""
        debug_log(f"_score_card called with: {score}")

        if not mw.reviewer or not mw.reviewer.card:
            debug_log("No reviewer or card available")
            tooltip("No card to score - start reviewing first!", period=1500)
            return

        def score_on_main_thread():
            try:
                debug_log(f"Executing score on main thread: {score}")
                if score == 'good':
                    # Score as Good (3)
                    mw.reviewer._answerCard(3)
                    debug_log("Card scored as Good (3)")
                    tooltip("✅ Card scored as Good", period=800)
                elif score == 'again':
                    # Score as Again (1)
                    mw.reviewer._answerCard(1)
                    debug_log("Card scored as Again (1)")
                    tooltip("🔄 Card scored as Again", period=800)
            except Exception as e:
                debug_log(f"Error scoring card: {e}")
                tooltip(f"Error scoring card: {e}", period=2000)

        # Execute on main thread
        mw.progress.timer(10, score_on_main_thread, False)

    def toggle_always_on_top(self):
        """Toggle Anki window always-on-top state"""
        if Qt is None:
            showInfo("Qt library not available for always-on-top functionality")
            return

        try:
            self.always_on_top_enabled = not self.always_on_top_enabled

            if self.always_on_top_enabled:
                # Enable always-on-top
                mw.setWindowFlags(mw.windowFlags() | Qt.WindowStaysOnTopHint)
                mw.show()
                tooltip("📌 Always-on-top enabled", period=1000)
                debug_log("Always-on-top enabled")
            else:
                # Disable always-on-top
                mw.setWindowFlags(mw.windowFlags() & ~Qt.WindowStaysOnTopHint)
                mw.show()
                tooltip("📌 Always-on-top disabled", period=1000)
                debug_log("Always-on-top disabled")
        except Exception as e:
            error_msg = f"Error toggling always-on-top: {e}"
            debug_log(error_msg)
            showInfo(error_msg)

    def on_reviewer_did_show_question(self, card):
        """Called when a card question is shown - start global hotkeys"""
        debug_log(f"Reviewer showed question. Card: {card}")
        self.reviewer_active = True
        self.start_global_hotkeys()

    def on_reviewer_will_end(self):
        """Called when reviewer is ending - stop global hotkeys"""
        debug_log("Reviewer ending")
        self.reviewer_active = False
        self.stop_global_hotkeys()

    def on_main_window_state_changed(self, new_state, old_state):
        """Called when Anki's main window state changes"""
        debug_log(f"Main window state changed: {old_state} -> {new_state}")
        if new_state != "review":
            self.reviewer_active = False
            self.stop_global_hotkeys()

# Global instance
hotkey_controller = AHKGlobalHotkeyController()

# Hook into Anki events
def setup_hooks():
    debug_log("Setting up Anki hooks")
    gui_hooks.reviewer_did_show_question.append(hotkey_controller.on_reviewer_did_show_question)
    gui_hooks.reviewer_will_end.append(hotkey_controller.on_reviewer_will_end)
    gui_hooks.state_did_change.append(hotkey_controller.on_main_window_state_changed)

def cleanup_hooks():
    debug_log("Cleaning up Anki hooks")
    try:
        gui_hooks.reviewer_did_show_question.remove(hotkey_controller.on_reviewer_did_show_question)
        gui_hooks.reviewer_will_end.remove(hotkey_controller.on_reviewer_will_end)
        gui_hooks.state_did_change.remove(hotkey_controller.on_main_window_state_changed)
    except ValueError:
        pass  # Hook wasn't registered

    # Stop global hotkeys and cleanup
    hotkey_controller.stop_global_hotkeys()

# Setup when add-on loads
debug_log("AutoHotkey Global Hotkey addon loading...")
setup_hooks()

# Show startup message
try:
    if mw:
        debug_log("Addon loaded successfully - showing startup message")
        startup_msg = "🎯 AutoHotkey Global Hotkeys loaded!\\n\\n"
        startup_msg += "Global Hotkeys (work everywhere):\\n"
        startup_msg += "• Ctrl+Z = Score card as Good\\n"
        startup_msg += "• Ctrl+X = Score card as Again\\n"
        startup_msg += "• Ctrl+O = Toggle always on top\\n\\n"
        startup_msg += "Using PostMessage for improved communication\\n"
        startup_msg += "Hotkeys will activate when you start reviewing cards!\\n"
        startup_msg += f"Debug log: {debug_file}"

        # Use a timer to show the message after Anki is fully loaded
        def show_startup_message():
            if mw:
                tooltip(startup_msg, period=5000)

        # Delay the message slightly to ensure Anki is ready
        from aqt.qt import QTimer
        QTimer.singleShot(2000, show_startup_message)
except Exception as e:
    debug_log(f"Error showing startup message: {e}")

# Cleanup when Anki closes
def on_unload():
    debug_log("Addon unloading...")
    cleanup_hooks()

# Register cleanup hooks
addHook("unloadProfile", on_unload)
addHook("profileClosed", on_unload)

# Ensure cleanup on process exit
atexit.register(cleanup_hooks)