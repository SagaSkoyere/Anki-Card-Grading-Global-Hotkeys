import subprocess
import tempfile
import datetime
import os
import threading
import atexit
from aqt import mw, gui_hooks
from aqt.utils import tooltip, showInfo
from anki.hooks import addHook, remHook

# Try to import Qt components for shortcuts and always-on-top functionality
try:
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QShortcut
    from PyQt5.QtGui import QKeySequence
except ImportError:
    try:
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QShortcut
        from PyQt6.QtGui import QKeySequence
    except ImportError:
        Qt = None
        QShortcut = None
        QKeySequence = None

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

class AHKGlobalHotkeyController:
    def __init__(self):
        self.ahk_process = None
        self.ahk_script_path = None
        self.reviewer_active = False
        self.always_on_top_enabled = False
        self.qt_shortcuts = []

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

            # Setup Qt shortcuts to catch function keys from AHK
            self._setup_function_key_shortcuts()

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

        # Clean up Qt shortcuts
        for shortcut in self.qt_shortcuts:
            try:
                shortcut.deleteLater()
            except Exception as e:
                debug_log(f"Error deleting Qt shortcut: {e}")
        self.qt_shortcuts.clear()
        debug_log("Qt shortcuts cleaned up")

    def _setup_function_key_shortcuts(self):
        """Setup Qt shortcuts to catch function keys sent by AutoHotkey"""
        # Enhanced diagnostics for debugging
        debug_log(f"_setup_function_key_shortcuts called - QShortcut={QShortcut is not None}, mw={mw is not None}")

        if QShortcut is not None:
            debug_log(f"QShortcut available from: {QShortcut}")
        else:
            debug_log("QShortcut is None - Qt import failed")

        if mw is not None:
            debug_log(f"mw available: {type(mw)}, has app: {hasattr(mw, 'app')}")
            debug_log(f"mw state: {getattr(mw, 'state', 'no state attr')}")
        else:
            debug_log("mw is None - main window not ready")

        # Check for basic Qt availability
        if not QShortcut:
            debug_log("Cannot setup Qt shortcuts: QShortcut not available")
            return False

        # Check if mw is ready with retry logic
        if not mw or not hasattr(mw, 'app'):
            debug_log("mw not ready yet, attempting delayed setup...")
            self._retry_qt_shortcuts_setup()
            return False

        # Proceed with setup
        return self._create_qt_shortcuts()

    def _retry_qt_shortcuts_setup(self):
        """Retry Qt shortcuts setup after a delay"""
        debug_log("Scheduling Qt shortcuts retry in 500ms...")
        try:
            from aqt.qt import QTimer
            QTimer.singleShot(500, self._delayed_qt_shortcuts_setup)
        except Exception as e:
            debug_log(f"Failed to schedule Qt shortcuts retry: {e}")

    def _delayed_qt_shortcuts_setup(self):
        """Delayed Qt shortcuts setup with better error handling"""
        debug_log("Attempting delayed Qt shortcuts setup...")

        if not mw or not hasattr(mw, 'app'):
            debug_log("mw still not ready after delay, giving up on Qt shortcuts")
            return

        success = self._create_qt_shortcuts()
        if success:
            debug_log("✅ Delayed Qt shortcuts setup successful!")
        else:
            debug_log("❌ Delayed Qt shortcuts setup failed")

    def _create_qt_shortcuts(self):
        """Actually create the Qt shortcuts"""
        debug_log("Creating Qt shortcuts...")

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
                debug_log(f"✅ Created Qt shortcut: {key_combination} - {description}")

            except Exception as e:
                debug_log(f"❌ Failed to create Qt shortcut {key_combination}: {e}")

        debug_log(f"Successfully created {success_count}/{len(shortcuts)} Qt shortcuts for AHK communication")
        return success_count > 0

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