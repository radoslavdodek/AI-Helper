import errno
import json
import logging
import os
import sys
import textwrap
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path
from string import Template

import httpx
import pyperclip
from openai import OpenAI
from PySide6.QtCore import Qt, Signal, QObject, QTimer
from PySide6.QtGui import QFont, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTextEdit, QPushButton, QLabel,
    QHBoxLayout, QVBoxLayout, QWidget, QSplitter, QSizePolicy,
)

CUSTOM_PROMPT_FILE_NAME_TEMPLATE = ".custom_prompt_${prompt_number}.txt"
CLIPBOARD_PLACEHOLDER = "{CLIPBOARD}"

# See https://openai.com/index/spring-update
default_model = 'gpt-5.2'

APP_PATH = Path(__file__).resolve().parent

# Rotating log: 5 MB per file, keep 3 backups (up to 20 MB total)
_log_handler = RotatingFileHandler(
    APP_PATH / "ai_helper.log", maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
)
_log_handler.setFormatter(logging.Formatter("%(asctime)s\n%(message)s\n---"))
logger = logging.getLogger("ai_helper")
logger.setLevel(logging.INFO)
logger.addHandler(_log_handler)


def log_http_request_response(response: httpx.Response):
    request = response.request
    print(f"Request: {request.method} {request.url}")
    print("  Headers:")
    for key, value in request.headers.items():
        if key.lower() == "authorization":
            value = "[...]"
        if key.lower() == "cookie":
            value = value.split("=")[0] + "=..."
        print(f"    {key}: {value}")
    print("  Body:")
    try:
        request_body = json.loads(request.content)
        print(
            textwrap.indent(
                json.dumps(request_body, indent=2), "    "
            )
        )
    except json.JSONDecodeError:
        print(textwrap.indent(request.content.decode(), "    "))
    print(f"Response: status_code={response.status_code}")
    print("  Headers:")
    for key, value in response.headers.items():
        if key.lower() == "set-cookie":
            value = value.split("=")[0] + "=..."
        print(f"    {key}: {value}")


client = (OpenAI(http_client=httpx.Client(
    event_hooks={
        "response": [log_http_request_response]
    }
)))


def app_help():
    print("Usage:")
    print(" ", sys.argv[0], "<ACTION>")
    print(" Supported actions: Rewrite, Ask, CustomPrompt")


STYLESHEET = """
QMainWindow {
    background-color: #f5f5f7;
}
QTextEdit {
    background-color: #ffffff;
    color: #1d1d1f;
    border: 1px solid #d2d2d7;
    border-radius: 8px;
    padding: 10px;
    selection-background-color: #b4d7ff;
    selection-color: #1d1d1f;
}
QTextEdit:focus {
    border: 1px solid #34a853;
}
QPushButton#actionButton {
    background-color: #34a853;
    color: #ffffff;
    border: none;
    border-radius: 8px;
    padding: 8px 20px;
    font-size: 14px;
    font-weight: bold;
}
QPushButton#actionButton:hover {
    background-color: #2d9249;
}
QPushButton#actionButton:pressed {
    background-color: #267a3e;
}
QPushButton#actionButton:disabled {
    background-color: #d2d2d7;
    color: #86868b;
}
QPushButton#copyButton {
    background-color: transparent;
    border: 1px solid #d2d2d7;
    border-radius: 8px;
    padding: 6px;
    color: #86868b;
    font-size: 16px;
}
QPushButton#copyButton:hover {
    background-color: #e8e8ed;
    color: #1d1d1f;
}
QPushButton#copyButton:disabled {
    color: #d2d2d7;
    border-color: #e8e8ed;
}
QLabel#infoLabel {
    color: #6e6e73;
    font-size: 13px;
    font-weight: bold;
}
QSplitter::handle {
    background-color: #d2d2d7;
    height: 4px;
    border-radius: 2px;
    margin: 2px 40px;
}
QSplitter::handle:hover {
    background-color: #34a853;
}
"""


class WorkerSignals(QObject):
    finished = Signal(str, str)
    error = Signal()


class App(QMainWindow):
    MAX_SIZE = 3000

    def __init__(self):
        super().__init__()
        self.app_path = APP_PATH

        self.SUPPORTED_ACTIONS = {
            "Rewrite": self.execute_rewrite,
            "Ask": self.execute_ask_question,
            "CustomPrompt": self.execute_custom_prompt
        }

        if len(sys.argv) < 2:
            print("Missing parameter ACTION")
            app_help()
            sys.exit(errno.EPERM)

        self.action = sys.argv[1]
        if self.SUPPORTED_ACTIONS.get(self.action) is None:
            print('Unsupported action:', self.action)
            app_help()
            sys.exit(errno.EPERM)

        if len(sys.argv) > 2:
            self.action_parameter = sys.argv[2]
        else:
            self.action_parameter = None

        # Window title
        if self.action == 'Rewrite':
            self.setWindowTitle("AI Rewriter")
        elif self.action == 'CustomPrompt':
            prompt_number = self.get_custom_prompt_number(self.action_parameter)
            self.setWindowTitle(f"AI Rewriter - Custom Prompt {prompt_number}")
        else:
            self.setWindowTitle("AI Helper")

        self.setWindowIcon(QIcon(str(self.app_path / "assets/app-icon.png")))
        self.resize(650, 900)
        self.setStyleSheet(STYLESHEET)

        # Button title
        self._button_title = self.action
        if self.action == 'CustomPrompt':
            self._button_title = 'Execute custom prompt'

        # Fonts
        mono_font = QFont("monospace", 13)
        input_font = QFont("monospace", 10)

        # Signals for thread-safe UI updates
        self._signals = WorkerSignals()
        self._signals.finished.connect(self._on_work_finished)
        self._signals.error.connect(self._on_work_error)

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(0)

        # Splitter for question/answer
        splitter = QSplitter(Qt.Vertical)
        splitter.setHandleWidth(8)
        splitter.setChildrenCollapsible(False)

        # Question text area
        self.textbox_question = QTextEdit()
        self.textbox_question.setFont(input_font)
        self.textbox_question.setPlaceholderText("Enter your text here...")
        self.textbox_question.setAcceptRichText(False)
        self.textbox_question.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Answer text area
        self.textbox_answer = QTextEdit()
        self.textbox_answer.setFont(mono_font)
        self.textbox_answer.setReadOnly(True)
        self.textbox_answer.setPlaceholderText("Answer will appear here...")
        self.textbox_answer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Button bar (between the two text areas, outside the splitter)
        button_bar = QHBoxLayout()
        button_bar.setContentsMargins(0, 8, 0, 8)
        button_bar.setSpacing(8)

        self.answer_button = QPushButton(self._button_title)
        self.answer_button.setObjectName("actionButton")
        self.answer_button.setCursor(Qt.PointingHandCursor)
        self.answer_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.answer_button.setFixedHeight(38)
        self.answer_button.clicked.connect(self.answer_button_event)

        self.info_label = QLabel("")
        self.info_label.setObjectName("infoLabel")

        self.copy_button = QPushButton("\u2398")
        self.copy_button.setObjectName("copyButton")
        self.copy_button.setCursor(Qt.PointingHandCursor)
        self.copy_button.setFixedSize(38, 38)
        self.copy_button.setEnabled(False)
        self.copy_button.clicked.connect(self.copy_answer_to_clipboard)
        self.copy_button.setToolTip("Copy to clipboard")

        button_bar.addWidget(self.answer_button)
        button_bar.addWidget(self.info_label)
        button_bar.addWidget(self.copy_button)

        button_bar_widget = QWidget()
        button_bar_widget.setLayout(button_bar)

        # Assemble layout: question + button bar in a top container
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(0)
        top_layout.addWidget(self.textbox_question, 1)
        top_layout.addWidget(button_bar_widget, 0)

        splitter.addWidget(top_widget)
        splitter.addWidget(self.textbox_answer)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        layout.addWidget(splitter, 1)

        # Keyboard shortcuts
        shortcut_submit = QShortcut(QKeySequence("Ctrl+Return"), self)
        shortcut_submit.activated.connect(self.answer_button_event)

        shortcut_escape = QShortcut(QKeySequence("Escape"), self)
        shortcut_escape.activated.connect(self.close)

        # Spinner timer
        self._spinner_frames = ["   ", ".  ", ".. ", "..."]
        self._spinner_index = 0
        self._spinner_timer = QTimer(self)
        self._spinner_timer.timeout.connect(self._animate_spinner)

        # Initialize clipboard content
        self.user_input = pyperclip.paste()

        if self.action == 'Ask':
            self.user_input = 'Explain: ' + self.user_input

        if self.action == 'CustomPrompt':
            self.textbox_question.setPlainText(self.get_custom_prompt(self.action_parameter))
        else:
            self.textbox_question.setPlainText(self.user_input)

        self.textbox_question.setFocus()

        # Auto-execute for Rewrite and CustomPrompt
        if self.action in ('Rewrite', 'CustomPrompt') and self.user_input is not None:
            QTimer.singleShot(0, self.answer_button_event)

    def copy_answer_to_clipboard(self):
        pyperclip.copy(self.textbox_answer.toPlainText())
        self.info_label.setText('Copied to clipboard')

    def answer_button_event(self):
        self.set_working_state()
        question_text = self.clip_text(self.textbox_question.toPlainText(), self.MAX_SIZE)
        action_fn = self.SUPPORTED_ACTIONS[self.action]
        thread = threading.Thread(target=action_fn, args=(question_text, self.action_parameter))
        thread.start()

    def set_working_state(self):
        self.answer_button.setEnabled(False)
        self.info_label.setText('')
        self._spinner_index = 0
        self._spinner_timer.start(400)
        self._animate_spinner()

    def _animate_spinner(self):
        frame = self._spinner_frames[self._spinner_index % len(self._spinner_frames)]
        self.answer_button.setText(f"Thinking{frame}")
        self._spinner_index += 1

    def _on_work_finished(self, result, info_message):
        self._spinner_timer.stop()
        self.textbox_answer.setPlainText(result)
        self.answer_button.setEnabled(True)
        self.answer_button.setText(self._button_title)
        self.copy_button.setEnabled(True)
        self.info_label.setText(info_message)

    def _on_work_error(self):
        self._spinner_timer.stop()
        self.answer_button.setEnabled(True)
        self.answer_button.setText(self._button_title)
        self.info_label.setText('Oops, something went wrong. Try again later.')

    def execute_rewrite(self, text_to_rewrite, _action_parameter):
        try:
            prompt = f"""
                 Please rewrite the following text for more clarity and make it grammatically correct.
                 Give me the updated text. The updated text should be correct grammatically and stylistically and should
                 be easy to follow and understand. Only make a change if it's needed. Try to follow the style of the
                 original text.
                 Don't make it too formal or academic. Include only improved text no other commentary.

                 The text to check:
                 ---
                 {text_to_rewrite}
                 ---

                 Improved text:
                 """

            completion = client.chat.completions.create(
                model=default_model, temperature=1, max_tokens=3000,
                messages=[{"role": "user", "content": prompt}]
            )
            result = completion.choices[0].message.content

            pyperclip.copy(result)
            self._signals.finished.emit(result, 'Copied to clipboard')
            self.log_to_file('Rewrite', text_to_rewrite, result)
        except Exception:
            self._signals.error.emit()

    def execute_ask_question(self, question, _action_parameter):
        try:
            completion = client.chat.completions.create(
                model=default_model, temperature=0,
                messages=[{"role": "user", "content": question}]
            )
            result = completion.choices[0].message.content

            self._signals.finished.emit(result, '')
            self.log_to_file('Question', question, result)
        except Exception:
            self._signals.error.emit()

    def execute_custom_prompt(self, question, action_parameter):
        try:
            self.update_custom_prompt(question, action_parameter)

            custom_prompt = self.get_custom_prompt(action_parameter)
            prompt = self.render_custom_prompt(custom_prompt, pyperclip.paste())
            print(prompt)
            completion = client.chat.completions.create(
                model=default_model, temperature=0.8,
                messages=[{"role": "user", "content": prompt}]
            )
            result = completion.choices[0].message.content
            print('-------')
            print(result)
            print('-------')

            self._signals.finished.emit(result, '')
            self.log_to_file('CustomPrompt', prompt, result)
        except Exception:
            self._signals.error.emit()

    def log_to_file(self, input_type, content, answer):
        logger.info("%s: %s\nAnswer: %s", input_type, content, answer)

    def get_custom_prompt_filename(self, prompt_number):
        template = Template(CUSTOM_PROMPT_FILE_NAME_TEMPLATE)
        return template.substitute(prompt_number=prompt_number)

    def get_custom_prompt_number(self, action_parameter):
        prompt_number = 1
        if action_parameter is not None:
            prompt_number = int(action_parameter)
        return prompt_number

    def get_custom_prompt(self, action_parameter=None):
        custom_prompt_file = (
                self.app_path / self.get_custom_prompt_filename(self.get_custom_prompt_number(action_parameter)))

        if not os.path.exists(custom_prompt_file):
            with open(custom_prompt_file, 'w') as f:
                f.write(
                    f"Create a concise summary of the following text:\n\n"
                    f"```\n"
                    f"{CLIPBOARD_PLACEHOLDER}\n"
                    f"```")

        with open(custom_prompt_file, 'r') as file:
            return file.read()

    def update_custom_prompt(self, new_prompt, action_parameter=None):
        custom_prompt_file = (
                self.app_path / self.get_custom_prompt_filename(self.get_custom_prompt_number(action_parameter)))

        with open(custom_prompt_file, 'w') as f:
            if CLIPBOARD_PLACEHOLDER not in new_prompt:
                new_prompt = new_prompt + '\n\n' + CLIPBOARD_PLACEHOLDER
            f.write(new_prompt)

    def render_custom_prompt(self, prompt, text):
        return prompt.replace(CLIPBOARD_PLACEHOLDER, text)

    @staticmethod
    def clip_text(text, max_size):
        if text is None:
            return None

        if len(text) > max_size:
            return text[:max_size].strip()
        else:
            return text.strip()


if __name__ == "__main__":
    qt_app = QApplication(sys.argv)
    app = App()
    app.show()
    sys.exit(qt_app.exec())
