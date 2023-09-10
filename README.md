# AI Helper

Simple AI helper utility for daily tasks.

This utility is designed to be used with hotkeys, allowing you to easily and quickly receive the answer you are looking
for.

## Setup hotkeys on Ubuntu

Open Settings -> Keyboard Shortcuts -> Custom Shortcuts

### Rewrite text

This feature automatically rewrites any text that is currently in the clipboard.
The newly rewritten text will then be placed back into the clipboard.

| Name               | Shortcut             | Command                        | Description                   |
|--------------------|----------------------|--------------------------------|-------------------------------|
| AI Helper: Rewrite | `Ctrl+Alt+Shift+F10` | `python3 ai_helper.py Rewrite` | Rewrite text using AI helper. |

### Ask question

| Name           | Shortcut             | Command                    | Description               |
|----------------|----------------------|----------------------------|---------------------------|
| AI Helper: Ask | `Ctrl+Alt+Shift+F11` | `python3 ai_helper.py Ask` | Ask AI helper a question. |

