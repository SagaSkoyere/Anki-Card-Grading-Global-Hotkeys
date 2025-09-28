# Anki Global Hotkey Card Control

An Anki add-on that enables global hotkey control for card scoring during review sessions.

## Features

- **Global Hotkeys**: Control card scoring even when Anki is not in focus
- **Ctrl + Z**: Score card as "Good" (pass card)
- **Ctrl + X**: Score card as "Again" (fail card)
- **Ctrl + O**: Toggle always-on-top mode for Anki window
- **Automatic Lifecycle**: Starts listening when reviewing cards, stops when Anki closes
- **Thread-Safe**: Runs in a separate thread to avoid blocking Anki's UI

## Installation

1. Copy this add-on to your Anki add-ons directory:
   - Windows: `%APPDATA%\Anki2\addons21\`
   - macOS: `~/Library/Application Support/Anki2/addons21/`
   - Linux: `~/.local/share/Anki2/addons21/`

2. Restart Anki

**No additional dependencies required!** The keyboard library is bundled with the add-on.

## Usage

1. Start a review session in Anki
2. The hotkey listener will automatically start when you open a card
3. Use the following hotkeys anywhere on your system:
   - **Ctrl + Z**: Score the current card as "Good" and move to next
   - **Ctrl + X**: Score the current card as "Again" and move to next
   - **Ctrl + O**: Toggle always-on-top mode (keeps Anki window above all others)
4. The listener stops automatically when you exit the review session or close Anki

## Requirements

- Anki 2.1.45+
- Administrative privileges may be required for global hotkey detection on some systems

**Dependencies are automatically handled** - no manual installation needed!

## Notes

- The add-on only listens for hotkeys during active review sessions
- There's a 0.5-second delay between hotkey presses to prevent rapid firing
- **Automatic fallback**: If global hotkeys aren't available, Qt shortcuts are used (require Anki focus)
- Always-on-top mode is off by default and can be toggled with Ctrl+O
- Visual tooltips confirm when always-on-top mode is enabled/disabled
- Dependencies are bundled - no separate installation required
