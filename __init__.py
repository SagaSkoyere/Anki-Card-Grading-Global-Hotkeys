import subprocess
import tempfile
import datetime
import os
import threading
import atexit
from aqt import mw, gui_hooks
from aqt.utils import tooltip, showInfo
from anki.hooks import addHook, remHook

# Try to import Qt components for always-on-top functionality
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

            tooltip("Global hotkeys active!Ctrl+Shift+A = Show Answer, Ctrl+Z = Again, Ctrl+X = Good", period=4000)

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

        debug_log("AutoHotkey cleanup completed")

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
        startup_msg = "🎯 AutoHotkey Global Hotkeys loaded!"

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
