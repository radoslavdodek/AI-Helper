#!/usr/bin/python3
import errno
import logging.handlers
import logging.handlers
import sys

import PySimpleGUI as sg
import openai
import pyperclip

logger = logging.getLogger('ai_helper')
logger.setLevel(logging.DEBUG)
handler = logging.handlers.SysLogHandler(address='/dev/log')
logger.addHandler(handler)


def ui_execute_rewrite(text_to_rewrite):
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

    window['-GENERATED_TEXT-'].update(result)
    pyperclip.copy(result)

    window['-INFO_LABEL-'].update('Copied into the clipboard')


def ui_execute_ask_question(question):
    logger.info(f'ai_helper: Asking question: {question}')

    # Execute the prompt
    completion = openai.ChatCompletion.create(model="gpt-4", messages=[{"role": "user", "content": question}])
    result = completion.choices[0].message.content

    logger.info(f'ai_helper: Answer arrived')

    window['-GENERATED_TEXT-'].update(result)


# Check the parameter
# Possible values:
# - "rewrite"
# - "ask"

def help():
    print("Usage:")
    print(" ", sys.argv[0], "<ACTION>")
    print(" Supported actions: Rewrite, Ask")


SUPPORTED_ACTIONS = {
    "Rewrite": ui_execute_rewrite,
    "Ask": ui_execute_ask_question
}

action = sys.argv[1]
logger.info(f'Action: {action}')
if SUPPORTED_ACTIONS.get(action) is None:
    print('Unsupported action:', action)
    help()
    sys.exit(errno.EPERM)

MAX_SIZE = 1000


def clip_text(text, max_size):
    if text is None:
        return None

    if len(text) > max_size:
        return text[:max_size].strip()
    else:
        return text.strip()


sg.theme('Default1')

original_text = pyperclip.paste()
if action == 'Ask':
    original_text = 'Explain: ' + original_text

layout = [
    # Row 1
    [sg.Multiline(clip_text(original_text, MAX_SIZE), size=(100, 10), font='Courier 12', expand_x=True, expand_y=True,
                  key='-ORIGINAL_TEXT-')],
    # Row 2
    [sg.Multiline(size=(100, 30), font='Courier 12', expand_x=True, expand_y=True, key='-GENERATED_TEXT-')],
    # Row 3
    [sg.Button(action, key='-BTN_TRANSLATE-', expand_x=True), sg.Text('', key='-INFO_LABEL-'), sg.Button('Copy'),
     sg.Button('Cancel')]
]

window = sg.Window('AI helper', layout, default_element_size=(100, 50), finalize=True, use_ttk_buttons=True,
                   resizable=True, grab_anywhere=True)
window["-ORIGINAL_TEXT-"].bind("<Control_L><Return>", "CTRL_ENTER")
window["-ORIGINAL_TEXT-"].bind("<Escape>", "ESCAPE")
window["-GENERATED_TEXT-"].bind("<Escape>", "ESCAPE")

# Initial execution at the startup
if action == 'Rewrite' and original_text is not None:
    event, values = window.read(0)
    SUPPORTED_ACTIONS[action](clip_text(str(original_text), MAX_SIZE))

# Event Loop to process "events" and get the "values" of the inputs
while True:
    event, values = window.read()
    if (
            event == sg.WIN_CLOSED or
            event == 'Cancel' or
            event == '-ORIGINAL_TEXT-ESCAPE' or
            event == '-GENERATED_TEXT-ESCAPE'
    ):
        break

    if event == 'Copy':
        pyperclip.copy(values['-GENERATED_TEXT-'])
        window['-INFO_LABEL-'].update('Copied into the clipboard')

    else:
        original_text = values['-ORIGINAL_TEXT-']
        SUPPORTED_ACTIONS[action](original_text)

window.close()
