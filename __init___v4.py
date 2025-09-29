import subprocess
import tempfile
import datetime
import os
import atexit
from aqt import mw, gui_hooks
from aqt.utils import tooltip, showInfo
from anki.hooks import addHook, remHook

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
        f.write(f"=== Anki AutoHotkey Global Hotkeys v4 (PostMessage) Debug Log Started at {datetime.datetime.now()} ===\n")
        f.write(f"Debug file location: {debug_file}\n\n")
except Exception as e:
    print(f"Could not create debug file: {e}")

class AHKGlobalHotkeyController:
    def __init__(self):
        self.ahk_process = None
        self.reviewer_active = False
        # NO Qt shortcuts needed for PostMessage method!

    def start_global_hotkeys(self):
        """Start AutoHotkey global hotkeys when reviewing begins"""
        debug_log("start_global_hotkeys called (PostMessage method)")

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

        # Get AHK script path for PostMessage version
        ahk_script_path = os.path.join(addon_dir, "ahk", "anki_hotkeys_v4.ahk")
        if not os.path.exists(ahk_script_path):
            error_msg = f"AutoHotkey script not found at {ahk_script_path}"
            debug_log(error_msg)
            showInfo(f"Global Hotkeys Error: {error_msg}\\n\\nPlease reinstall the addon.")
            return

        try:
            # Start AutoHotkey process
            debug_log(f"Starting AutoHotkey PostMessage process: {ahk_exe_path} {ahk_script_path}")
            self.ahk_process = subprocess.Popen(
                [ahk_exe_path, ahk_script_path],
                cwd=os.path.join(addon_dir, "ahk"),
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            debug_log(f"AutoHotkey PostMessage process started with PID: {self.ahk_process.pid}")

            # No Qt shortcuts needed - PostMessage sends Windows messages directly!
            debug_log("PostMessage method: No Qt shortcuts needed, AHK sends Windows messages directly to Anki")

            tooltip("🎯 Global hotkeys active (PostMessage)!\\n\\nCtrl+Z = Good (3), Ctrl+X = Again (1), Ctrl+O = Options\\nMost robust method - works everywhere!", period=4000)

        except Exception as e:
            error_msg = f"Failed to start AutoHotkey PostMessage: {e}"
            debug_log(error_msg)
            showInfo(f"Global Hotkeys Error: {error_msg}\\n\\nTry running Anki as administrator or check if antivirus is blocking AutoHotkey.")

    def stop_global_hotkeys(self):
        """Stop AutoHotkey global hotkeys when reviewing ends"""
        debug_log("stop_global_hotkeys called (PostMessage method)")

        if self.ahk_process is not None:
            try:
                debug_log(f"Terminating AutoHotkey PostMessage process PID: {self.ahk_process.pid}")
                self.ahk_process.terminate()
                self.ahk_process.wait(timeout=3)
                debug_log("AutoHotkey PostMessage process terminated successfully")
            except subprocess.TimeoutExpired:
                debug_log("AutoHotkey PostMessage process did not terminate gracefully, forcing kill")
                self.ahk_process.kill()
            except Exception as e:
                debug_log(f"Error stopping AutoHotkey PostMessage process: {e}")
            finally:
                self.ahk_process = None

        debug_log("PostMessage method cleanup complete")

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
    debug_log("Setting up Anki hooks (PostMessage method)")
    gui_hooks.reviewer_did_show_question.append(hotkey_controller.on_reviewer_did_show_question)
    gui_hooks.reviewer_will_end.append(hotkey_controller.on_reviewer_will_end)
    gui_hooks.state_did_change.append(hotkey_controller.on_main_window_state_changed)

def cleanup_hooks():
    debug_log("Cleaning up Anki hooks (PostMessage method)")
    try:
        gui_hooks.reviewer_did_show_question.remove(hotkey_controller.on_reviewer_did_show_question)
        gui_hooks.reviewer_will_end.remove(hotkey_controller.on_reviewer_will_end)
        gui_hooks.state_did_change.remove(hotkey_controller.on_main_window_state_changed)
    except ValueError:
        pass  # Hook wasn't registered

    # Stop global hotkeys and cleanup
    hotkey_controller.stop_global_hotkeys()

# Setup when add-on loads
debug_log("AutoHotkey Global Hotkey addon v4 (PostMessage) loading...")
setup_hooks()

# Show startup message
try:
    if mw:
        debug_log("Addon loaded successfully - showing startup message")
        startup_msg = "🎯 AutoHotkey Global Hotkeys v4 (PostMessage) loaded!\\n\\n"
        startup_msg += "Global Hotkeys (work everywhere):\\n"
        startup_msg += "• Ctrl+Z = Score card as Good (Windows msg '3')\\n"
        startup_msg += "• Ctrl+X = Score card as Again (Windows msg '1')\\n"
        startup_msg += "• Ctrl+O = Options (Windows msg 'O')\\n\\n"
        startup_msg += "Uses PostMessage - most robust method!\\n"
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
    debug_log("Addon v4 (PostMessage) unloading...")
    cleanup_hooks()

# Register cleanup hooks
addHook("unloadProfile", on_unload)
addHook("profileClosed", on_unload)

# Ensure cleanup on process exit
atexit.register(cleanup_hooks)