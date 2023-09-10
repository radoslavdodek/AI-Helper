# AI Helper

Simple AI helper utility for daily tasks.

This utility is designed to be used with global hotkeys, making it easy and quick for you to get the answer
you're looking for. By utilizing the clipboard, you can easily copy the text you want to rewrite or ask about,
and then press the global hotkey. The answer will automatically be copied back to the clipboard for your convenience.

When you're using the application, simply press `Ctrl+Enter` on question field to get the answer.
If you want to exit the application, just press `ESC`.

## Pre-requisites

- Python 3.6 or higher
- OpenAI API key. Set the key in the `OPENAI_API_KEY` environment variable.

## Install dependencies

```bash
pip3 install -r requirements.txt
```

## Setup global hotkeys in Ubuntu

This application is designed to work with global hotkeys. To set it up in Ubuntu, simply follow these steps:

Open _Settings -> Keyboard Shortcuts -> Custom Shortcuts_ and create the following shortcuts:

### Rewrite text

This feature automatically rewrites any text currently in the clipboard.
The newly rewritten text will be displayed in the user interface and then placed back into the clipboard.

| Name               | Suggested shortcut   | Command                        | Description                   |
|--------------------|----------------------|--------------------------------|-------------------------------|
| AI Helper: Rewrite | `Ctrl+Alt+Shift+F10` | `python3 ai_helper.py Rewrite` | Rewrite text using AI helper. |

### Ask question

This feature takes the content of the clipboard and puts it into the question field in the following format:

```
Explain: <CLIPBOARD_CONTENT>
```

To send this question to OpenAI, simply press `Ctrl+Enter`. The answer will be displayed in the user interface.

| Name           | Suggested shortcut   | Command                    | Description               |
|----------------|----------------------|----------------------------|---------------------------|
| AI Helper: Ask | `Ctrl+Alt+Shift+F11` | `python3 ai_helper.py Ask` | Ask AI helper a question. |

