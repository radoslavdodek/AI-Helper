import errno
import sys

import customtkinter
import openai
import pyperclip
from customtkinter import CTkFont

customtkinter.set_appearance_mode("System")  # Modes: "System" (standard), "Dark", "Light"
customtkinter.set_default_color_theme("blue")  # Themes: "blue" (standard), "green", "dark-blue"


class App(customtkinter.CTk):
    MAX_SIZE = 1000

    def __init__(self):
        super().__init__()

        self.SUPPORTED_ACTIONS = {
            "Rewrite": self.ui_execute_rewrite,
            "Ask": self.ui_execute_ask_question
        }

        if len(sys.argv) < 2:
            print("Missing parameter ACTION")
            self.help()
            sys.exit(errno.EPERM)

        self.action = sys.argv[1]
        if self.SUPPORTED_ACTIONS.get(self.action) is None:
            print('Unsupported action:', self.action)
            self.help()
            sys.exit(errno.EPERM)

        # UI
        monospace_font = CTkFont(family="monospace", size=16, weight="normal")

        # configure window
        self.title("AI Helper")
        self.geometry(f"{1000}x{700}")

        # configure grid layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=5)

        self.textbox_question = customtkinter.CTkTextbox(self, font=monospace_font)
        self.textbox_question.grid(row=0, column=0, columnspan=2, sticky="nsew")

        # Question button
        self.answer_button = customtkinter.CTkButton(master=self, text="Ask", command=self.answer_button_event)
        self.answer_button.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")

        # Label
        self.info_label = customtkinter.CTkLabel(self, text="", font=customtkinter.CTkFont(size=14, weight="bold"))
        self.info_label.grid(row=1, column=1, padx=20, pady=(5, 5))

        # Answer textbox
        self.textbox_answer = customtkinter.CTkTextbox(self, font=monospace_font)
        self.textbox_answer.grid(row=2, column=0, columnspan=2, sticky="nsew")
        self.textbox_answer.insert("0.0", "Some answer goes here.")

        # Initialize
        self.question = pyperclip.paste()
        if self.action == 'Ask':
            self.question = 'Explain: ' + self.question
        self.textbox_question.insert("0.0", self.question)
        self.textbox_question.focus_set()

        # Bind keyboard shortcuts
        self.textbox_question.bind('<Control_L><Return>', lambda event: self.answer_button_event())
        self.textbox_question.bind('<Escape>', lambda event: self.quit())
        self.textbox_answer.bind('<Escape>', lambda event: self.quit())

        # Initial execution at the startup
        if self.action == 'Rewrite' and self.question is not None:
            self.SUPPORTED_ACTIONS[self.action](self.clip_text(str(self.question), self.MAX_SIZE))

    def help(self):
        print("Usage:")
        print(" ", sys.argv[0], "<ACTION>")
        print(" Supported actions: Rewrite, Ask")

    def answer_button_event(self):
        print("Answer button clicked")
        self.SUPPORTED_ACTIONS[self.action](self.clip_text(str(self.question), self.MAX_SIZE))

    def quit(self):
        self.destroy()

    def ui_execute_rewrite(self, text_to_rewrite):
        # Execute the prompt
        prompt = f"Please rewrite the following text for more clarity and make it grammatically correct. Give me the " \
                 f"updated text. The updated text should be correct grammatically and stylistically and should be easy to " \
                 f"follow and understand. Don't make it too formal. Include only improved text no other " \
                 f"commentary.\n\nThe text to check:\n---\n{text_to_rewrite}\n---\n\nImproved text: "

        completion = openai.ChatCompletion.create(
            model="gpt-3.5-turbo", temperature=0.9,
            messages=[{"role": "user", "content": prompt}]
        )
        result = completion.choices[0].message.content

        self.textbox_answer.delete("0.0", "end")
        self.textbox_answer.insert("0.0", result)
        pyperclip.copy(result)

        self.info_label.configure(text='Copied into the clipboard')

    def ui_execute_ask_question(self, question):
        print("Asking question:", question)
        # Execute the prompt
        completion = openai.ChatCompletion.create(model="gpt-4", messages=[{"role": "user", "content": question}])
        result = completion.choices[0].message.content

        self.textbox_answer.delete("0.0", "end")
        self.textbox_answer.insert("0.0", result)

    def clip_text(self, text, max_size):
        if text is None:
            return None

        if len(text) > max_size:
            return text[:max_size].strip()
        else:
            return text.strip()


# Check the parameter
# Possible values:
# - "rewrite"
# - "ask"

if __name__ == "__main__":
    app = App()
    app.mainloop()

#
#
# # Event Loop to process "events" and get the "values" of the inputs
# while True:
#     event, values = window.read()
#     if (
#             event == sg.WIN_CLOSED or
#             event == 'Cancel' or
#             event == '-ORIGINAL_TEXT-ESCAPE' or
#             event == '-GENERATED_TEXT-ESCAPE'
#     ):
#         break
#
#     if event == 'Copy':
#         pyperclip.copy(values['-GENERATED_TEXT-'])
#         window['-INFO_LABEL-'].update('Copied into the clipboard')
#
#     else:
#         original_text = values['-ORIGINAL_TEXT-']
#         SUPPORTED_ACTIONS[action](original_text)
#
# window.close()
