import threading
import time
from aqt import mw, gui_hooks
from aqt.reviewer import Reviewer
from anki.hooks import addHook, remHook
import sys
import os
import tempfile
import datetime

# Add bundled lib directory to path for keyboard library
addon_dir = os.path.dirname(__file__)
lib_dir = os.path.join(addon_dir, "lib")
if lib_dir not in sys.path:
    sys.path.insert(0, lib_dir)

# Setup debug logging
debug_file = os.path.join(tempfile.gettempdir(), "anki_hotkey_debug.txt")
def debug_log(message):
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    with open(debug_file, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")
    print(message)  # Also print to console

# Clear previous debug log
try:
    with open(debug_file, "w", encoding="utf-8") as f:
        f.write(f"=== Anki Hotkey Debug Log Started at {datetime.datetime.now()} ===\n")
        f.write(f"Debug file location: {debug_file}\n\n")
except Exception as e:
    print(f"Could not create debug file: {e}")

# Try to import keyboard library (bundled first, then system)
keyboard = None
keyboard_status = ""
try:
    import keyboard
    keyboard_status = f"✓ Keyboard library imported from: {keyboard.__file__}"
    debug_log(keyboard_status)
except ImportError as e:
    keyboard_status = f"✗ Initial keyboard import failed: {e}"
    debug_log(keyboard_status)
    try:
        # Fallback: try system installation
        sys.path.append(lib_dir)
        import keyboard
        keyboard_status = f"✓ Keyboard library imported from lib directory: {keyboard.__file__}"
        debug_log(keyboard_status)
    except ImportError as e2:
        keyboard_status = f"✗ Keyboard library import failed completely: {e2}"
        debug_log(keyboard_status)
        keyboard = None

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

class GlobalHotkeyController:
    def __init__(self):
        self.thread = None
        self.running = False
        self.reviewer_active = False
        self.always_on_top_enabled = False
        self.qt_shortcuts = []
        self.use_qt_shortcuts = False

    def start_listener(self):
        debug_log(f"start_listener called. keyboard={keyboard is not None}, running={self.running}")

        if keyboard is None:
            # Fallback to Qt shortcuts if keyboard library not available
            if QShortcut is not None:
                self._setup_qt_shortcuts()
                self.use_qt_shortcuts = True
                debug_log("Using Qt shortcuts as fallback")
                mw.utils.tooltip("Hotkeys active: Ctrl+Z (Good), Ctrl+X (Again), Ctrl+O (Always on top)\nOnly works when Anki has focus", period=4000)
            else:
                error_msg = "Neither keyboard library nor Qt shortcuts available"
                debug_log(error_msg)
                mw.utils.showInfo(f"Hotkey Error: {error_msg}\nCheck {debug_file} for details")
            return

        if self.running:
            debug_log("Listener already running")
            return

        # Test keyboard library functionality before starting thread
        try:
            debug_log("Testing keyboard library functionality...")
            # This will trigger keyboard hook initialization on first call
            test_result = keyboard.is_pressed('f24')  # F24 key unlikely to be pressed
            debug_log(f"Keyboard library test successful: {test_result}")
        except RuntimeError as e:
            debug_log(f"Windows keyboard hook failed: {e}")
            error_msg = str(e)

            # Provide user-friendly guidance for common Windows issues
            user_msg = "Global hotkeys failed to initialize.\n\n"
            if "Access denied" in error_msg:
                user_msg += "• Try running Anki as administrator\n"
                user_msg += "• Check if antivirus software is blocking keyboard hooks\n"
            elif "error code: 5" in error_msg.lower():
                user_msg += "• Try running Anki as administrator\n"
                user_msg += "• Check Windows security settings\n"
            else:
                user_msg += "• Try running Anki as administrator\n"
                user_msg += "• Check if antivirus software is blocking the application\n"
                user_msg += "• Temporarily disable Windows Defender real-time protection\n"

            user_msg += f"\nFalling back to limited hotkeys (only when Anki has focus).\nTechnical details: {error_msg}\n\nCheck {debug_file} for more information."

            # Fall back to Qt shortcuts
            if QShortcut is not None:
                self._setup_qt_shortcuts()
                self.use_qt_shortcuts = True
                debug_log("Falling back to Qt shortcuts after Windows hook failure")
                mw.utils.showInfo(user_msg)
            else:
                debug_log("Qt shortcuts also unavailable after Windows hook failure")
                mw.utils.showInfo(f"Hotkey Error: {user_msg}")
            return
        except Exception as e:
            debug_log(f"Unexpected keyboard library error: {e}")
            # Fall back to Qt shortcuts for any other keyboard library errors
            if QShortcut is not None:
                self._setup_qt_shortcuts()
                self.use_qt_shortcuts = True
                debug_log("Falling back to Qt shortcuts after unexpected keyboard error")
                mw.utils.tooltip("Using Qt shortcuts due to keyboard library error", period=3000)
            else:
                error_msg = f"Keyboard library error: {e}"
                debug_log(error_msg)
                mw.utils.showInfo(f"Hotkey Error: {error_msg}\nCheck {debug_file} for details")
            return

        debug_log("Starting keyboard listener thread")
        self.running = True
        self.thread = threading.Thread(target=self._listen_for_hotkeys, daemon=True)
        self.thread.start()
        mw.utils.tooltip("Global hotkeys active: Ctrl+Z (Good), Ctrl+X (Again), Ctrl+O (Always on top)\nWorks even when Anki is not in focus!", period=4000)

    def _setup_qt_shortcuts(self):
        if not QShortcut or not mw:
            debug_log("Cannot setup Qt shortcuts: QShortcut or mw not available")
            return

        # Clear existing shortcuts
        for shortcut in self.qt_shortcuts:
            try:
                shortcut.deleteLater()
            except Exception as e:
                debug_log(f"Error deleting Qt shortcut: {e}")
        self.qt_shortcuts.clear()
        debug_log("Cleared existing Qt shortcuts")

        # Create Qt shortcuts (only work when Anki has focus)
        shortcuts = [
            ("Ctrl+Z", lambda: self._qt_score_card_safe('good'), "Score card as Good"),
            ("Ctrl+X", lambda: self._qt_score_card_safe('again'), "Score card as Again"),
            ("Ctrl+O", lambda: self._qt_toggle_always_on_top_safe(), "Toggle always on top")
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

                # Set context to only work when the main window has focus
                shortcut.setContext(Qt.WindowShortcut)

                self.qt_shortcuts.append(shortcut)
                success_count += 1
                debug_log(f"Created Qt shortcut: {key_combination} - {description}")

            except Exception as e:
                debug_log(f"Failed to create Qt shortcut {key_combination}: {e}")

        debug_log(f"Successfully created {success_count}/{len(shortcuts)} Qt shortcuts")
        if success_count > 0:
            debug_log("Qt shortcuts active: Ctrl+Z (Good), Ctrl+X (Again), Ctrl+O (Always on top)")

    def _qt_score_card_safe(self, score):
        """Thread-safe wrapper for scoring cards from Qt shortcuts"""
        try:
            debug_log(f"Qt shortcut triggered: score={score}")

            # Check if we're in the right context (reviewing)
            if not mw or not mw.reviewer or not mw.reviewer.card:
                debug_log("Qt shortcut ignored: not in review mode")
                mw.utils.tooltip("Hotkey only works during card review", period=1500)
                return

            current_state = mw.state if mw else "unknown"
            if current_state != "review":
                debug_log(f"Qt shortcut ignored: wrong state ({current_state})")
                mw.utils.tooltip("Hotkey only works during card review", period=1500)
                return

            debug_log(f"Qt shortcut executing: scoring card as {score}")
            self._score_card(score)

        except Exception as e:
            debug_log(f"Error in Qt shortcut score card: {e}")
            mw.utils.tooltip(f"Hotkey error: {e}", period=2000)

    def _qt_toggle_always_on_top_safe(self):
        """Thread-safe wrapper for toggling always on top from Qt shortcuts"""
        try:
            debug_log("Qt shortcut triggered: toggle always on top")
            self.toggle_always_on_top()
        except Exception as e:
            debug_log(f"Error in Qt shortcut always on top: {e}")
            mw.utils.tooltip(f"Always on top error: {e}", period=2000)

    def stop_listener(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)

        # Clean up Qt shortcuts
        if self.use_qt_shortcuts:
            for shortcut in self.qt_shortcuts:
                shortcut.deleteLater()
            self.qt_shortcuts.clear()
            self.use_qt_shortcuts = False

    def _listen_for_hotkeys(self):
        if keyboard is None:
            debug_log("Keyboard is None in _listen_for_hotkeys")
            return

        debug_log("Hotkey listener started")
        self._debug_counter = 0
        while self.running:
            try:
                current_state = mw.state if mw else "unknown"
                if self.reviewer_active and current_state == "review":
                    if keyboard.is_pressed('ctrl+z'):
                        debug_log("Ctrl+Z detected - scoring good")
                        self._score_card('good')
                        time.sleep(0.5)  # Prevent rapid firing
                    elif keyboard.is_pressed('ctrl+x'):
                        debug_log("Ctrl+X detected - scoring again")
                        self._score_card('again')
                        time.sleep(0.5)  # Prevent rapid firing
                    elif keyboard.is_pressed('ctrl+o'):
                        debug_log("Ctrl+O detected - toggling always on top")
                        self._toggle_always_on_top_threadsafe()
                        time.sleep(0.5)  # Prevent rapid firing
                # Debug output every 5 seconds
                self._debug_counter += 1
                if self._debug_counter >= 50:  # 50 * 0.1s = 5 seconds
                    debug_log(f"Listener active. reviewer_active={self.reviewer_active}, mw.state={current_state}")
                    self._debug_counter = 0

                time.sleep(0.1)  # Small delay to prevent excessive CPU usage
            except Exception as e:
                debug_log(f"Hotkey listener error: {e}")
        debug_log("Hotkey listener stopped")

    def _score_card(self, score):
        debug_log(f"_score_card called with: {score}")
        if not mw.reviewer or not mw.reviewer.card:
            debug_log("No reviewer or card available")
            return

        def score_on_main_thread():
            try:
                debug_log(f"Executing score on main thread: {score}")
                if score == 'good':
                    # Score as Good (3)
                    mw.reviewer._answerCard(3)
                    debug_log("Card scored as Good (3)")
                elif score == 'again':
                    # Score as Again (1)
                    mw.reviewer._answerCard(1)
                    debug_log("Card scored as Again (1)")
            except Exception as e:
                debug_log(f"Error scoring card: {e}")

        # Execute on main thread
        mw.progress.timer(10, score_on_main_thread, False)

    def toggle_always_on_top(self):
        if Qt is None:
            mw.utils.showInfo("Qt library not available for always-on-top functionality")
            return

        try:
            self.always_on_top_enabled = not self.always_on_top_enabled

            if self.always_on_top_enabled:
                # Enable always-on-top
                mw.setWindowFlags(mw.windowFlags() | Qt.WindowStaysOnTopHint)
                mw.show()
                mw.utils.tooltip("Always-on-top enabled", period=1000)
            else:
                # Disable always-on-top
                mw.setWindowFlags(mw.windowFlags() & ~Qt.WindowStaysOnTopHint)
                mw.show()
                mw.utils.tooltip("Always-on-top disabled", period=1000)
        except Exception as e:
            print(f"Error toggling always-on-top: {e}")
            mw.utils.showInfo(f"Error toggling always-on-top: {e}")

    def _toggle_always_on_top_threadsafe(self):
        # Execute always-on-top toggle on main thread
        mw.progress.timer(10, self.toggle_always_on_top, False)

    def on_reviewer_did_show_question(self, card):
        debug_log(f"Reviewer showed question. Card: {card}")
        self.reviewer_active = True
        debug_log(f"reviewer_active set to: {self.reviewer_active}")
        if not self.running:
            self.start_listener()

    def on_reviewer_will_end(self):
        self.reviewer_active = False

    def on_main_window_state_changed(self, new_state, old_state):
        if new_state != "review":
            self.reviewer_active = False

# Global instance
hotkey_controller = GlobalHotkeyController()

# Hook into Anki events
def setup_hooks():
    gui_hooks.reviewer_did_show_question.append(hotkey_controller.on_reviewer_did_show_question)
    gui_hooks.reviewer_will_end.append(hotkey_controller.on_reviewer_will_end)
    gui_hooks.state_did_change.append(hotkey_controller.on_main_window_state_changed)

def cleanup_hooks():
    try:
        gui_hooks.reviewer_did_show_question.remove(hotkey_controller.on_reviewer_did_show_question)
        gui_hooks.reviewer_will_end.remove(hotkey_controller.on_reviewer_will_end)
        gui_hooks.state_did_change.remove(hotkey_controller.on_main_window_state_changed)
    except ValueError:
        pass  # Hook wasn't registered

    hotkey_controller.stop_listener()

# Setup when add-on loads
setup_hooks()

# Show startup message with addon info
try:
    if mw and mw.utils:
        debug_log("Addon loaded successfully - showing startup message")
        startup_msg = "Global Hotkey Card Control addon loaded!\n\n"
        startup_msg += "Hotkeys:\n"
        startup_msg += "• Ctrl+Z = Score card as Good\n"
        startup_msg += "• Ctrl+X = Score card as Again\n"
        startup_msg += "• Ctrl+O = Toggle always on top\n\n"
        startup_msg += "Hotkeys will activate when you start reviewing cards.\n"
        startup_msg += f"Debug log: {debug_file}"

        # Use a timer to show the message after Anki is fully loaded
        def show_startup_message():
            if mw and mw.utils:
                mw.utils.tooltip(startup_msg, period=5000)

        # Delay the message slightly to ensure Anki is ready
        from aqt.qt import QTimer
        QTimer.singleShot(2000, show_startup_message)
except Exception as e:
    debug_log(f"Error showing startup message: {e}")

# Cleanup when Anki closes
def on_unload():
    cleanup_hooks()

# Register cleanup
addHook("unloadProfile", on_unload)
addHook("profileClosed", on_unload)