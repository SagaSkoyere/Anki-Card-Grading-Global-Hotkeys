import threading
import time
from aqt import mw, gui_hooks
from aqt.reviewer import Reviewer
from anki.hooks import addHook, remHook
import sys
import os

# Add bundled lib directory to path for keyboard library
addon_dir = os.path.dirname(__file__)
lib_dir = os.path.join(addon_dir, "lib")
if lib_dir not in sys.path:
    sys.path.insert(0, lib_dir)

# Try to import keyboard library (bundled first, then system)
keyboard = None
try:
    import keyboard
    print(f"Keyboard library imported successfully from: {keyboard.__file__}")
except ImportError as e:
    print(f"Initial keyboard import failed: {e}")
    try:
        # Fallback: try system installation
        sys.path.append(lib_dir)
        import keyboard
        print(f"Keyboard library imported from lib directory: {keyboard.__file__}")
    except ImportError as e2:
        print(f"Keyboard library import failed completely: {e2}")
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
        print(f"start_listener called. keyboard={keyboard is not None}, running={self.running}")
        if keyboard is None:
            # Fallback to Qt shortcuts if keyboard library not available
            if QShortcut is not None:
                self._setup_qt_shortcuts()
                self.use_qt_shortcuts = True
                print("Using Qt shortcuts as fallback")
                mw.utils.tooltip("Using Qt shortcuts (limited global functionality)", period=2000)
            else:
                print("Neither keyboard library nor Qt shortcuts available")
                mw.utils.showInfo("Neither keyboard library nor Qt shortcuts available. Hotkeys will not work.")
            return

        if self.running:
            print("Listener already running")
            return

        print("Starting keyboard listener thread")
        self.running = True
        self.thread = threading.Thread(target=self._listen_for_hotkeys, daemon=True)
        self.thread.start()

    def _setup_qt_shortcuts(self):
        if not QShortcut or not mw:
            return

        # Clear existing shortcuts
        for shortcut in self.qt_shortcuts:
            shortcut.deleteLater()
        self.qt_shortcuts.clear()

        # Create Qt shortcuts (only work when Anki has focus)
        shortcuts = [
            (QKeySequence("Ctrl+Z"), lambda: self._score_card('good')),
            (QKeySequence("Ctrl+X"), lambda: self._score_card('again')),
            (QKeySequence("Ctrl+O"), lambda: self.toggle_always_on_top())
        ]

        for key_seq, callback in shortcuts:
            shortcut = QShortcut(key_seq, mw)
            shortcut.activated.connect(callback)
            self.qt_shortcuts.append(shortcut)

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
            print("Keyboard is None in _listen_for_hotkeys")
            return

        print("Hotkey listener started")
        while self.running:
            try:
                current_state = mw.state if mw else "unknown"
                if self.reviewer_active and current_state == "review":
                    if keyboard.is_pressed('ctrl+z'):
                        print("Ctrl+Z detected - scoring good")
                        self._score_card('good')
                        time.sleep(0.5)  # Prevent rapid firing
                    elif keyboard.is_pressed('ctrl+x'):
                        print("Ctrl+X detected - scoring again")
                        self._score_card('again')
                        time.sleep(0.5)  # Prevent rapid firing
                    elif keyboard.is_pressed('ctrl+o'):
                        print("Ctrl+O detected - toggling always on top")
                        self._toggle_always_on_top_threadsafe()
                        time.sleep(0.5)  # Prevent rapid firing
                # Debug output every 5 seconds
                elif hasattr(self, '_debug_counter'):
                    self._debug_counter += 1
                    if self._debug_counter >= 50:  # 50 * 0.1s = 5 seconds
                        print(f"Listener active. reviewer_active={self.reviewer_active}, mw.state={current_state}")
                        self._debug_counter = 0
                else:
                    self._debug_counter = 0

                time.sleep(0.1)  # Small delay to prevent excessive CPU usage
            except Exception as e:
                print(f"Hotkey listener error: {e}")
        print("Hotkey listener stopped")

    def _score_card(self, score):
        print(f"_score_card called with: {score}")
        if not mw.reviewer or not mw.reviewer.card:
            print("No reviewer or card available")
            return

        def score_on_main_thread():
            try:
                print(f"Executing score on main thread: {score}")
                if score == 'good':
                    # Score as Good (3)
                    mw.reviewer._answerCard(3)
                    print("Card scored as Good (3)")
                elif score == 'again':
                    # Score as Again (1)
                    mw.reviewer._answerCard(1)
                    print("Card scored as Again (1)")
            except Exception as e:
                print(f"Error scoring card: {e}")

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
        print(f"Reviewer showed question. Card: {card}")
        self.reviewer_active = True
        print(f"reviewer_active set to: {self.reviewer_active}")
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

# Cleanup when Anki closes
def on_unload():
    cleanup_hooks()

# Register cleanup
addHook("unloadProfile", on_unload)
addHook("profileClosed", on_unload)