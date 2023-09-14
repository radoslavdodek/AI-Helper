import errno
import sys
import threading
from pathlib import Path
from tkinter import PhotoImage

import customtkinter
import openai
import pyperclip
from customtkinter import CTkFont

customtkinter.set_appearance_mode("System")
customtkinter.set_default_color_theme("blue")


def app_help():
    print("Usage:")
    print(" ", sys.argv[0], "<ACTION>")
    print(" Supported actions: Rewrite, Ask")


class App(customtkinter.CTk):
    MAX_SIZE = 1000

    def __init__(self):
        super().__init__(className="AI Helper")

        self.SUPPORTED_ACTIONS = {
            "Rewrite": self.execute_rewrite,
            "Ask": self.execute_ask_question
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

        # UI
        monospace_font = CTkFont(family="monospace", size=16, weight="normal")

        # configure window
        self.title("AI Helper")
        self.geometry(f"{1000}x{700}")
        self.app_path = Path(__file__).resolve().parent
        self.iconphoto(False, PhotoImage(file=self.app_path / "assets/app-icon.png"))

        # configure grid layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self.textbox_question = customtkinter.CTkTextbox(self, font=monospace_font, height=150)
        self.textbox_question.grid(row=0, column=0, columnspan=2, sticky="nsew")

        # Question button
        self.answer_button = customtkinter.CTkButton(master=self, text=self.action, command=self.answer_button_event)
        self.answer_button.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")

        # Label
        self.info_label = customtkinter.CTkLabel(self, text="", font=customtkinter.CTkFont(size=14, weight="bold"))
        self.info_label.grid(row=1, column=1, padx=20, pady=(5, 5))

        # Answer textbox
        self.textbox_answer = customtkinter.CTkTextbox(self, font=monospace_font)
        self.textbox_answer.grid(row=2, column=0, columnspan=2, sticky="nsew")

        # Initialize
        self.question = pyperclip.paste()
        if self.action == 'Ask':
            self.question = 'Explain: ' + self.question
        self.textbox_question.insert("0.0", self.question)
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
        if self.action == 'Rewrite' and self.question is not None:
            self.answer_button_event()

    def answer_button_event(self):
        self.set_working_state('Working...')
        self.execute_in_thread(lambda: self.SUPPORTED_ACTIONS[self.action](
            self.clip_text(str(self.textbox_question.get("0.0", "end")), self.MAX_SIZE)), ())

    def set_working_state(self, message):
        self.answer_button.configure(state='disabled')
        self.info_label.configure(text=message)

    def unset_working_state(self, message):
        self.answer_button.configure(state='normal')
        self.info_label.configure(text=message)

    def quit(self):
        self.destroy()

    def execute_rewrite(self, text_to_rewrite):
        # Execute the prompt
        prompt = f"Please rewrite the following text for more clarity and make it grammatically correct. Give me the " \
                 f"updated text. The updated text should be correct grammatically and stylistically and should be " \
                 f"easy to follow and understand. Don't make it too formal. Include only improved text no other " \
                 f"commentary.\n\nThe text to check:\n---\n{text_to_rewrite}\n---\n\nImproved text: "

        completion = openai.ChatCompletion.create(
            model="gpt-4", temperature=0.9,
            messages=[{"role": "user", "content": prompt}]
        )
        result = completion.choices[0].message.content

        self.textbox_answer.delete("0.0", "end")
        self.textbox_answer.insert("0.0", result)

        pyperclip.copy(result)
        self.unset_working_state('Copied to clipboard')

        self.store_to_file('Rewrite', text_to_rewrite, result)

    def execute_ask_question(self, question):
        # Execute the prompt
        completion = openai.ChatCompletion.create(
            model="gpt-4", temperature=0,
            messages=[{"role": "user", "content": question}]
        )
        result = completion.choices[0].message.content

        self.textbox_answer.delete("0.0", "end")
        self.textbox_answer.insert("0.0", result)

        self.info_label.configure(text='')
        self.unset_working_state('')

        self.store_to_file('Question', question, result)

    def store_to_file(self, type, content, answer):
        log_file = self.app_path / "ai_helper.log"

        with open(log_file, 'a') as f:
            f.write(f'{type}: {content}\n')
            f.write(f'Answer: {answer}\n---\n')

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
