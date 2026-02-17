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
from tkinter import PhotoImage

import customtkinter
import httpx
import pyperclip
from customtkinter import CTkFont, CTkImage
from PIL import Image
from openai import OpenAI

BG_COLOR = "#DBDBDB"

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

customtkinter.set_appearance_mode("System")
customtkinter.set_default_color_theme("blue")


def app_help():
    print("Usage:")
    print(" ", sys.argv[0], "<ACTION>")
    print(" Supported actions: Rewrite, Ask, CustomPrompt")


class App(customtkinter.CTk):
    MAX_SIZE = 3000

    def __init__(self):
        super().__init__(className="AI Helper")
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

        # UI
        monospace_font = CTkFont(family="monospace", size=16, weight="normal")

        # configure window
        if self.action == 'Rewrite':
            self.title("AI Rewriter")
        elif self.action == 'CustomPrompt':
            prompt_number = self.get_custom_prompt_number(self.action_parameter)
            self.title(f"AI Rewriter - Custom Prompt {prompt_number}")
        else:
            self.title("AI Helper")

        # Question button
        question_button_title = self.action
        if self.action == 'CustomPrompt':
            question_button_title = 'Execute custom prompt'

        self.geometry(f"{615}x{1000}")
        self.iconphoto(False, PhotoImage(file=self.app_path / "assets/app-icon.png"))
        # Set application background color
        self.configure(fg_color=BG_COLOR)

        # configure grid layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self.textbox_question = customtkinter.CTkTextbox(self, wrap=customtkinter.WORD, font=monospace_font, height=150, fg_color=BG_COLOR)
        self.textbox_question.grid(row=0, column=0, columnspan=3, sticky="nsew")

        self.answer_button = customtkinter.CTkButton(master=self, text=question_button_title,
                                                     corner_radius=12,
                                                     fg_color="#2B7A4B",
                                                     hover_color="#236B3E",
                                                     font=CTkFont(size=14, weight="bold"),
                                                     height=36,
                                                     command=self.answer_button_event)
        self.answer_button.grid(row=1, column=0, padx=8, pady=8, sticky="nsew")

        # Label
        self.info_label = customtkinter.CTkLabel(self, text="", font=customtkinter.CTkFont(size=14, weight="bold"))
        self.info_label.grid(row=1, column=1, padx=20, pady=(5, 5))

        # 'Copy to clipboard' button
        self.copy_to_clipboard_button = customtkinter.CTkButton(master=self,
                                                                state=customtkinter.DISABLED,
                                                                text='',
                                                                image=CTkImage(light_image=Image.open(self.app_path / "assets/copy-icon.png"), size=(14, 14)),
                                                                width=36,
                                                                height=36,
                                                                corner_radius=10,
                                                                bg_color="transparent",
                                                                fg_color="transparent",
                                                                hover_color="#CBCBCB",
                                                                command=self.copy_answer_to_clipboard)
        self.copy_to_clipboard_button.grid(row=1, column=2, padx=8, pady=8, sticky="nsew")

        # Answer textbox
        self.textbox_answer = customtkinter.CTkTextbox(self, wrap=customtkinter.WORD, font=monospace_font, fg_color=BG_COLOR)
        self.textbox_answer.grid(row=2, column=0, columnspan=3, sticky="nsew")

        # Initialize
        self.user_input = pyperclip.paste()

        if self.action == 'Ask':
            self.user_input = 'Explain: ' + self.user_input

        if self.action == 'CustomPrompt':
            self.textbox_question.insert("0.0", self.get_custom_prompt(self.action_parameter))
        else:
            self.textbox_question.insert("0.0", self.user_input)

        self.textbox_question.focus_set()

        # Bind keyboard shortcuts
        self.textbox_question.bind(
            '<Control_L><Return>',
            # Return value "break" means that the event should not be processed by the default handler
            lambda event: "break" if self.answer_button_event() is None else None
        )
        self.textbox_question.bind('<Escape>', lambda event: self.quit())
        self.textbox_answer.bind('<Escape>', lambda event: self.quit())

        # Initial execution at the startup
        if self.action == 'Rewrite' and self.user_input is not None:
            self.answer_button_event()
        if self.action == 'CustomPrompt' and self.user_input is not None:
            self.answer_button_event()

    def copy_answer_to_clipboard(self):
        pyperclip.copy(self.textbox_answer.get("0.0", "end"))
        self.info_label.configure(text='Copied to clipboard')

    def answer_button_event(self):
        self.set_working_state('Let me think...')
        self.execute_in_thread(lambda: self.SUPPORTED_ACTIONS[self.action](
            self.clip_text(str(self.textbox_question.get("0.0", "end")), self.MAX_SIZE), self.action_parameter), ())

    def set_working_state(self, message):
        self.answer_button.configure(state=customtkinter.DISABLED, fg_color="#7A7A7A")
        self.info_label.configure(text='')
        self._spinner_frames = ["   ", ".  ", ".. ", "..."]
        self._spinner_index = 0
        self._spinning = True
        self._animate_spinner()

    def _animate_spinner(self):
        if not self._spinning:
            return
        frame = self._spinner_frames[self._spinner_index % len(self._spinner_frames)]
        self.answer_button.configure(text=f"Thinking{frame}")
        self._spinner_index += 1
        self._spinner_after_id = self.after(400, self._animate_spinner)

    def unset_working_state(self, message):
        self._spinning = False
        if hasattr(self, '_spinner_after_id'):
            self.after_cancel(self._spinner_after_id)
        question_button_title = self.action
        if self.action == 'CustomPrompt':
            question_button_title = 'Execute custom prompt'
        self.answer_button.configure(state=customtkinter.NORMAL, fg_color="#2B7A4B",
                                     text=question_button_title)
        self.copy_to_clipboard_button.configure(state=customtkinter.NORMAL)
        self.info_label.configure(text=message)

    def quit(self):
        self.destroy()

    def execute_rewrite(self, text_to_rewrite, _action_parameter):
        try:
            # Execute the prompt
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

            self.textbox_answer.delete("0.0", "end")
            self.textbox_answer.insert("0.0", result)

            pyperclip.copy(result)
            self.unset_working_state('Copied to clipboard')

            self.log_to_file('Rewrite', text_to_rewrite, result)
        except Exception as e:
            self.info_label.configure(text='Oops, something went wrong. Try again later.')
            self.unset_working_state('')

    def execute_ask_question(self, question, _action_parameter):
        try:
            # Execute the prompt
            completion = client.chat.completions.create(
                model=default_model, temperature=0,
                messages=[{"role": "user", "content": question}]
            )
            result = completion.choices[0].message.content

            self.textbox_answer.delete("0.0", "end")
            self.textbox_answer.insert("0.0", result)

            self.info_label.configure(text='')
            self.unset_working_state('')

            self.log_to_file('Question', question, result)
        except Exception as e:
            self.info_label.configure(text='Oops, something went wrong. Try again later.')
            self.unset_working_state('')

    def execute_custom_prompt(self, question, action_parameter):
        try:
            self.update_custom_prompt(question, action_parameter)

            # Execute the prompt
            custom_prompt = self.get_custom_prompt(action_parameter)
            prompt = self.render_custom_prompt(custom_prompt, pyperclip.paste())
            print(prompt)
            completion = client.chat.completions.create(
                model=default_model, temperature=0.8,
                messages=[{"role": "user", "content": prompt}]
            )
            result = completion.choices[0].message.content

            self.textbox_answer.delete("0.0", "end")
            self.textbox_answer.insert("0.0", result)
            print('-------')
            print(result)
            print('-------')

            self.info_label.configure(text='')
            self.unset_working_state('')

            self.log_to_file('CustomPrompt', prompt, result)
        except Exception as e:
            self.info_label.configure(text='Oops, something went wrong. Try again later.')
            self.unset_working_state('')

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

    @staticmethod
    def execute_in_thread(callback, args):
        thread = threading.Thread(target=callback, args=args)
        thread.start()


if __name__ == "__main__":
    app = App()
    app.mainloop()
