# Filename: production.py

import PySimpleGUI as sg
import os
import datetime
import json # Added for model info loading
from direction import Director # Import the Director class

# --- Configuration ---
LOG_DIR = "logs"
# Ensure consistent naming with the original script if needed, or use a new name
OUTPUT_FILENAME = os.path.join(LOG_DIR, "moderated_conversation_log_v3_refactored.txt")
WINDOW_TITLE = "Philosopher Dialogue v3 (Refactored - Producer/Director)"
NUM_ROUNDS = 3 # Keep config here or move to Director? Decide based on control preference.

# --- Color Map --- (Can be moved to a config file later)
COLOR_MAP = {
    'Socrates': 'blue',
    'Confucius': 'green',
    'Moderator': 'purple', # Assuming moderator might speak directly or via Director logs
    'System': 'grey',
    'Error': 'red',
    'User': 'black',
    'Director': 'orange' # Color for Director status updates
}

class Producer:
    """
    Handles the "production" aspects: GUI, logging, status updates,
    and overall application flow. Owns the Director instance.
    """
    def __init__(self):
        self.window = None
        self.log_file_handle = None
        self.director = Director(
            update_status_callback=self.update_status,
            log_message_callback=self.log_message # Pass logging callback to Director
        )
        self.model_info = self._get_model_info_from_config()
        self._build_gui()

    def _get_model_info_from_config(self, config_path="llm_config.json"):
        """Loads model names from config file for display."""
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            # Provide default 'Unknown' if a persona or model_name is missing
            return {
                'Socrates': config.get('socrates', {}).get('model_name', 'Unknown'),
                'Confucius': config.get('confucius', {}).get('model_name', 'Unknown'),
                'Moderator': config.get('moderator', {}).get('model_name', 'Unknown'),
            }
        except FileNotFoundError:
            print(f"Warning: Config file not found at {config_path}")
            return {'Socrates': 'Unknown', 'Confucius': 'Unknown', 'Moderator': 'Unknown'}
        except Exception as e:
            print(f"Error loading model info from config: {e}")
            return {'Socrates': 'Unknown', 'Confucius': 'Unknown', 'Moderator': 'Unknown'}

    def _build_gui(self):
        """Builds the PySimpleGUI window layout."""
        sg.theme("SystemDefault")
        layout = [
            [sg.Text(WINDOW_TITLE, font=("Helvetica", 14), justification='center', expand_x=True)],
             [sg.Frame("Model Instances", [[
                sg.Text(f"Socrates: {self.model_info['Socrates']}", key='-MODEL-SOCRATES-', size=(40,1)),
                sg.Text(f"Confucius: {self.model_info['Confucius']}", key='-MODEL-CONFUCIUS-', size=(40,1)),
                sg.Text(f"Moderator: {self.model_info['Moderator']}", key='-MODEL-MODERATOR-', size=(40,1))
            ]], expand_x=True)],
            [sg.Frame("Director's Log & Debug Info", [[
                sg.Multiline(size=(110, 8), key='-DEBUG-', autoscroll=True, disabled=True, text_color='grey')
             ]], expand_x=True)],
            [sg.Frame("Full Conversation", [[
                sg.Multiline(size=(110, 24), key='-OUTPUT-', autoscroll=True, disabled=True, write_only=True)
            ]], expand_x=True)],
            [sg.Text("Enter Initial Question for Socrates:", font=("Helvetica", 11))],
            [sg.InputText(size=(70, 1), key='-INPUT-'), sg.Button("Start Conversation", key='-START-')],
            [sg.Text(f"Dialogue will run for {NUM_ROUNDS} rounds. Output also saved to {OUTPUT_FILENAME}", font=("Helvetica", 9))],
            [sg.Text("", size=(100, 1), key='-STATUS-', text_color='grey', font=("Helvetica", 10))],
        ]
        self.window = sg.Window(WINDOW_TITLE, layout, finalize=True)

    def _initialize_log(self):
        """Creates log directory and opens the log file."""
        try:
            os.makedirs(LOG_DIR, exist_ok=True)
            self.log_file_handle = open(OUTPUT_FILENAME, 'w', encoding='utf-8')
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.log_file_handle.write(f"Moderated Conversation Log - {timestamp}\n")
            self.log_file_handle.write(f"Rounds: {NUM_ROUNDS}\n")
            self.log_file_handle.write("========================================\n\n")
            return True
        except IOError as e:
            sg.popup_error(f"Error creating or writing to log file {OUTPUT_FILENAME}: {e}", title="File Error")
            return False

    def _close_log(self):
        """Closes the log file if it's open."""
        if self.log_file_handle:
            try:
                self.log_file_handle.write("\n--- Log file closed ---\n")
                self.log_file_handle.close()
                self.log_file_handle = None
            except Exception as e:
                 print(f"Error closing log file: {e}") # Log to console if GUI/file error


    # --- Callback Methods for Director ---
    def update_status(self, message, color='Director'):
        """Callback for Director to update the GUI status bar."""
        # Ensure GUI updates happen in the main thread if Director runs separately later
        if self.window:
             self.window['-STATUS-'].update(message, text_color=COLOR_MAP.get(color, 'grey'))
             self.window.refresh() # Needed to show update immediately

    def log_message(self, message, speaker="System", color=None):
        """Callback for Director (or Producer) to log messages to GUI and file."""
        if not color:
            color = COLOR_MAP.get(speaker, 'black')

        # Add speaker prefix if not already present (simple check)
        prefix = f"{speaker.upper()}: " if speaker != "System" and not message.strip().startswith(f"{speaker.upper()}:") else ""
        full_message = f"{prefix}{message}\n"

        if self.window:
            # Append to the main output window
            self.window['-OUTPUT-'].print(full_message, text_color=color, end='')
             # Optionally log director/system messages to debug window too
            if speaker in ["Director", "System", "Error"]:
                 self.window['-DEBUG-'].print(full_message, text_color=color, end='')

        if self.log_file_handle:
            try:
                # Write the raw message, assuming Director formats it appropriately if needed
                # Or adjust here to always add speaker if desired for log file consistency
                self.log_file_handle.write(message + "\n") # Ensure newline in file
            except Exception as e:
                # Handle potential write errors after file is opened
                 print(f"Error writing to log file: {e}")
                 self.update_status("Error writing to log file.", color='Error')


    # --- Main Event Loop ---
    def run(self):
        """Runs the main GUI event loop."""
        while True:
            event, values = self.window.read()
            if event == sg.WIN_CLOSED:
                break
            if event == '-START-':
                initial_input = values['-INPUT-'].strip()
                if not initial_input:
                    sg.popup("Please enter an initial question.", title="Input Required")
                    continue

                # Prepare UI for conversation
                self.window['-INPUT-'].update(disabled=True)
                self.window['-START-'].update(disabled=True)
                self.window['-OUTPUT-'].update("") # Clear previous output
                self.window['-DEBUG-'].update("") # Clear previous debug info
                self.update_status("Initializing production...", color='System')

                if not self._initialize_log():
                    self.update_status("Failed to initialize log file. Aborting.", color='Error')
                    self.window['-INPUT-'].update(disabled=False)
                    self.window['-START-'].update(disabled=False)
                    continue # Stop if log fails

                # Log initiator message
                initiator_line = f"YOU (Initiator): {initial_input}"
                self.log_message("----------------------------------------", speaker="System")
                self.log_message(initiator_line, speaker="User")
                self.log_message("----------------------------------------", speaker="System")

                try:
                    # --- Call the Director ---
                    self.update_status("Handing off to Director to start conversation...", color='System')
                    # The Director will use callbacks to update GUI/log during execution
                    success = self.director.run_conversation(initial_input, NUM_ROUNDS)

                    # --- Post-Conversation ---
                    if success:
                        final_status = f"Conversation completed after {NUM_ROUNDS} rounds."
                        self.update_status(final_status, color='green')
                        self.log_message(f"\n--- {final_status} ---\n", speaker="System")
                    else:
                        # Director should have logged the error via callback
                        self.update_status("Conversation failed or stopped prematurely.", color='Error')
                        self.log_message("\n--- Conversation failed or stopped prematurely ---\n", speaker="Error")

                except Exception as e:
                    # Catch errors happening *within* the Director call if not caught internally
                    error_msg = f"Unexpected error during direction: {e}"
                    sg.popup_error(error_msg, title="Runtime Error")
                    self.update_status("Critical error during conversation.", color='Error')
                    self.log_message(f"\n--- UNEXPECTED RUNTIME ERROR: {e} ---\n", speaker="Error")
                finally:
                     # --- Cleanup ---
                     self._close_log()
                     self.update_status("Ready for new conversation.") # Reset status
                     self.window['-INPUT-'].update(disabled=False)
                     self.window['-START-'].update(disabled=False)

        # --- Close House ---
        self._close_log() # Ensure log is closed if loop broken
        self.window.close()
        print("Production finished, house closed.")


if __name__ == "__main__":
    producer = Producer()
    producer.run()