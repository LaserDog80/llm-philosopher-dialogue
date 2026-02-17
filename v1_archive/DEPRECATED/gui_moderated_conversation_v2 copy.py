python
import PySimpleGUI as sg
import os
import datetime
import re
import time

import socrates
import confucius
import moderator

# --- Configuration ---
NUM_ROUNDS = 3
LOG_DIR = "logs"
OUTPUT_FILENAME = os.path.join(LOG_DIR, "moderated_conversation_log_v2.txt")
WINDOW_TITLE = "Philosopher Dialogue (with Moderator, Debugging & Model Info)"
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

# --- Model Info ---
def get_model_info_from_config(config_path="llm_config.json"):
    import json
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        return {
            'Socrates': config.get('socrates', {}).get('model_name', 'Unknown'),
            'Confucius': config.get('confucius', {}).get('model_name', 'Unknown'),
            'Moderator': config.get('moderator', {}).get('model_name', 'Unknown'),
        }
    except Exception:
        return {'Socrates': 'Unknown', 'Confucius': 'Unknown', 'Moderator': 'Unknown'}

# --- Utility Functions ---
def extract_think_blocks(text):
    """Returns a list of all <think>...</think> blocks in text."""
    return re.findall(r'<think>(.*?)</think>', text, flags=re.DOTALL)

def remove_think_blocks(text):
    """Removes all <think>...</think> blocks from text."""
    return re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()

def robust_invoke(chain, input_dict, who, debug_area, round_num):
    """Invoke a chain with retry on timeout, logging failures to debug_area."""
    for attempt in range(1, MAX_RETRIES+1):
        try:
            response = chain.invoke(input_dict)
            return response, None
        except Exception as e:
            err_msg = f"[Round {round_num}] {who} attempt {attempt} failed: {e}\n"
            debug_area.update(debug_area.get() + err_msg)
            if attempt == MAX_RETRIES:
                return None, e
            time.sleep(RETRY_DELAY)
    return None, Exception("Unknown error")

def print_colored_multiline(window, key, text, color):
    window[key].print(text, text_color=color, end='')

def log_message_colored(window, key, text, color, file_handle=None):
    print_colored_multiline(window, key, text, color)
    if file_handle:
        file_handle.write(text)

# --- GUI Layout ---
sg.theme("SystemDefault")
model_info = get_model_info_from_config()

layout = [
    [sg.Text("Philosopher Dialogue (with Moderator, Debugging & Model Info)", font=("Helvetica", 14), justification='center', expand_x=True)],
    [sg.Frame("Model Instances", [[
        sg.Text(f"Socrates: {model_info['Socrates']}", key='-MODEL-SOCRATES-', size=(40,1)),
        sg.Text(f"Confucius: {model_info['Confucius']}", key='-MODEL-CONFUCIUS-', size=(40,1)),
        sg.Text(f"Moderator: {model_info['Moderator']}", key='-MODEL-MODERATOR-', size=(40,1))
    ]], expand_x=True)],
    [sg.Frame("Debug Reasoning (<think> blocks)", [[
        sg.Multiline(size=(110, 8), key='-DEBUG-', autoscroll=True, disabled=True)
    ]], expand_x=True)],
    [sg.Frame("Full Conversation", [[
        sg.Multiline(size=(110, 24), key='-OUTPUT-', autoscroll=True, disabled=True, write_only=True)
    ]], expand_x=True)],
    [sg.Text("Enter Initial Question for Socrates:", font=("Helvetica", 11))],
    [sg.InputText(size=(70, 1), key='-INPUT-'), sg.Button("Start Conversation", key='-START-')],
    [sg.Text(f"Dialogue will run for {NUM_ROUNDS} rounds. Output also saved to {OUTPUT_FILENAME}", font=("Helvetica", 9))],
    [sg.Text("", size=(100, 1), key='-STATUS-', text_color='grey', font=("Helvetica", 10))],
]

window = sg.Window(WINDOW_TITLE, layout, finalize=True)

# Color map for each persona
COLOR_MAP = {
    'Socrates': 'blue',
    'Confucius': 'green',
    'Moderator': 'purple',
}

file_log_handle = None
try:
    while True:
        event, values = window.read()
        if event == sg.WIN_CLOSED:
            break
        if event == '-START-':
            initial_input = values['-INPUT-'].strip()
            if not initial_input:
                sg.popup("Please enter an initial question.", title="Input Required")
                continue
            window['-INPUT-'].update(disabled=True)
            window['-OUTPUT-'].update("")
            window['-DEBUG-'].update("")
            window['-STATUS-'].update("Starting moderated conversation...")
            window.refresh()

            try:
                os.makedirs(LOG_DIR, exist_ok=True)
                file_log_handle = open(OUTPUT_FILENAME, 'w', encoding='utf-8')
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                file_log_handle.write(f"Moderated Conversation Log - {timestamp}\n")
                file_log_handle.write(f"Rounds: {NUM_ROUNDS}\n")
                file_log_handle.write("========================================\n\n")

                initiator_line = f"YOU (Initiator): {initial_input}\n"
                log_message_colored(window, '-OUTPUT-', "----------------------------------------\n", 'black', file_log_handle)
                log_message_colored(window, '-OUTPUT-', initiator_line, 'black', file_log_handle)
                log_message_colored(window, '-OUTPUT-', "----------------------------------------\n\n", 'black', file_log_handle)
                current_turn_input = initial_input
                conversation_successful = True

                for i in range(NUM_ROUNDS):
                    round_header = f"--- ROUND {i+1} ---\n"
                    log_message_colored(window, '-OUTPUT-', round_header, 'black', file_log_handle)

                    # Socrates' Turn
                    try:
                        window['-STATUS-'].update(f"Round {i+1}: Socrates thinking...")
                        window.refresh()
                        socrates_response = socrates.socrates_chain.invoke({"input": current_turn_input})
                        socrates_line = f"SOCRATES:\n{socrates_response}\n"
                        log_message_colored(window, '-OUTPUT-', socrates_line, COLOR_MAP['Socrates'], file_log_handle)
                        log_message_colored(window, '-OUTPUT-', "----------------------------------------\n\n", 'black', file_log_handle)
                        current_turn_input = socrates_response  # Output becomes input for next turn
                    except Exception as e:
                        error_line = f"\nError during Socrates' turn (Round {i+1}): {e}\n"
                        log_message_colored(window, '-OUTPUT-', error_line, 'red', file_log_handle)
                        window['-STATUS-'].update(f"Error during Socrates' turn (Round {i+1}). Conversation stopped.", text_color='red')
                        conversation_successful = False
                        break

                    # Confucius' Turn
                    try:
                        window['-STATUS-'].update(f"Round {i+1}: Confucius contemplating...")
                        window.refresh()
                        confucius_response = confucius.confucius_chain.invoke({"input": current_turn_input})
                        confucius_line = f"CONFUCIUS:\n{confucius_response}\n"
                        log_message_colored(window, '-OUTPUT-', confucius_line, COLOR_MAP['Confucius'], file_log_handle)
                        log_message_colored(window, '-OUTPUT-', "----------------------------------------\n\n", 'black', file_log_handle)
                        current_turn_input = confucius_response  # Next input
                    except Exception as e:
                        error_line = f"\nError during Confucius' turn (Round {i+1}): {e}\n"
                        log_message_colored(window, '-OUTPUT-', error_line, 'red', file_log_handle)
                        window['-STATUS-'].update(f"Error during Confucius' turn (Round {i+1}). Conversation stopped.", text_color='red')
                        conversation_successful = False
                        break

                if conversation_successful:
                    end_line = f"\n--- Conversation ended after {i+1} round(s) ---\n"
                    log_message_colored(window, '-OUTPUT-', end_line, 'black', file_log_handle)
                    window['-STATUS-'].update("Conversation completed successfully.", text_color='green')
                else:
                    end_line = f"\n--- Conversation ended prematurely after {i+1} round(s) ---\n"
                    log_message_colored(window, '-OUTPUT-', end_line, 'red', file_log_handle)

            except IOError as e:
                sg.popup_error(f"Error writing to file {OUTPUT_FILENAME}: {e}", title="File Error")
                window['-STATUS-'].update(f"File error occurred.", text_color='red')
            except Exception as e:
                sg.popup_error(f"An unexpected error occurred during conversation: {e}", title="Runtime Error")
                window['-STATUS-'].update(f"Runtime error occurred.", text_color='red')
                if file_log_handle:
                    log_message_colored(window, '-OUTPUT-', f"\nUNEXPECTED RUNTIME ERROR: {e}\n", 'red', file_log_handle)
            finally:
                if file_log_handle:
                    file_log_handle.close()
                    file_log_handle = None
                window['-INPUT-'].update(disabled=False)
                window['-START-'].update(disabled=False)
finally:
    if file_log_handle:
        file_log_handle.close()
    window.close()

print("Moderated GUI v2 closed.")
```