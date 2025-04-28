# Filename: direction.py

import time
import socrates # Import actor module
import confucius # Import actor module
# import moderator # Import if moderator logic is needed within the loop

# --- Configuration ---
# Consider moving these if they purely relate to direction logic
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

class Director:
    """
    Manages the core conversation flow, interacting with Actors (LLMs)
    and handling retries. Uses callbacks to report status and messages
    back to the Producer.
    """
    def __init__(self, update_status_callback, log_message_callback):
        """
        Initializes the Director.

        Args:
            update_status_callback: Function to call for status updates (e.g., producer.update_status).
            log_message_callback: Function to call for logging messages (e.g., producer.log_message).
        """
        self.update_status = update_status_callback
        self.log_message = log_message_callback

        # Validate and store actor chains (ensure they are loaded)
        # The actor modules (socrates.py, confucius.py) should have created these
        if not hasattr(socrates, 'socrates_chain') or socrates.socrates_chain is None:
             raise ImportError("Socrates chain failed to initialize. Check socrates.py and dependencies.")
        if not hasattr(confucius, 'confucius_chain') or confucius.confucius_chain is None:
            raise ImportError("Confucius chain failed to initialize. Check confucius.py and dependencies.")
        # Add moderator check if used in the loop
        # if not hasattr(moderator, 'moderator_chain') or moderator.moderator_chain is None:
        #     raise ImportError("Moderator chain failed to initialize. Check moderator.py and dependencies.")

        self.socrates_chain = socrates.socrates_chain
        self.confucius_chain = confucius.confucius_chain
        # self.moderator_chain = moderator.moderator_chain # If needed

        self.log_message("Director initialized.", speaker="Director")


    def _robust_invoke(self, chain, input_dict, actor_name, round_num):
        """
        Invokes an LLM chain with retry logic on failure.

        Args:
            chain: The Langchain chain object to invoke.
            input_dict: The input dictionary for the chain.
            actor_name: Name of the actor (for logging).
            round_num: The current conversation round number.

        Returns:
            The response string from the chain, or None if it fails after retries.
        """
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                self.update_status(f"Round {round_num}: {actor_name} thinking (Attempt {attempt}/{MAX_RETRIES})...")
                start_time = time.time()
                response = chain.invoke(input_dict)
                end_time = time.time()
                self.log_message(f"Director Log: {actor_name} responded in {end_time - start_time:.2f}s.", speaker="Director")
                # Add debug logging if needed:
                # self.log_message(f"Director Debug: {actor_name} Raw Output: {response}", speaker="Director")
                return response
            except Exception as e:
                error_msg = f"Director ERROR: {actor_name}'s turn failed (Round {round_num}, Attempt {attempt}): {e}"
                self.log_message(error_msg, speaker="Error")
                if attempt == MAX_RETRIES:
                    self.update_status(f"Round {round_num}: {actor_name} failed after {MAX_RETRIES} attempts.", color='Error')
                    return None # Failed after all retries
                self.update_status(f"Round {round_num}: {actor_name} failed (Attempt {attempt}). Retrying in {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)
        return None # Should not be reached, but as a fallback


    def run_conversation(self, initial_input, num_rounds):
        """
        Runs the main conversation loop between actors.

        Args:
            initial_input (str): The starting prompt for the conversation.
            num_rounds (int): The number of rounds (Socrates -> Confucius = 1 round).

        Returns:
            bool: True if the conversation completed successfully, False otherwise.
        """
        self.log_message(f"Director starting conversation for {num_rounds} rounds.", speaker="Director")
        current_turn_input = initial_input
        conversation_successful = True

        for i in range(num_rounds):
            round_num = i + 1
            round_header = f"--- ROUND {round_num} ---"
            self.log_message(round_header, speaker="System") # Log round headers via callback

            # --- Socrates' Turn ---
            self.update_status(f"Round {round_num}: Socrates' turn...")
            socrates_response = self._robust_invoke(
                self.socrates_chain,
                {"input": current_turn_input},
                "Socrates",
                round_num
            )

            if socrates_response is None:
                self.log_message(f"Director stopped: Socrates failed to respond in round {round_num}.", speaker="Error")
                conversation_successful = False
                break # Exit loop if Socrates fails

            # Log Socrates' response via callback
            # Prefixing with speaker name might be redundant if log_message handles it, adjust as needed
            self.log_message(f"SOCRATES:\n{socrates_response}", speaker="Socrates")
            self.log_message("----------------------------------------", speaker="System")
            current_turn_input = socrates_response # Output becomes input for the next turn

            # --- Add Moderator logic here if needed ---
            # Example: Evaluate Socrates' response before Confucius' turn
            # moderator_eval = self._robust_invoke(...)
            # if moderator_eval: process eval, maybe adapt current_turn_input

            # --- Confucius' Turn ---
            self.update_status(f"Round {round_num}: Confucius' turn...")
            confucius_response = self._robust_invoke(
                self.confucius_chain,
                {"input": current_turn_input}, # Pass Socrates' output (or modified input)
                "Confucius",
                round_num
            )

            if confucius_response is None:
                self.log_message(f"Director stopped: Confucius failed to respond in round {round_num}.", speaker="Error")
                conversation_successful = False
                break # Exit loop if Confucius fails

            # Log Confucius' response via callback
            self.log_message(f"CONFUCIUS:\n{confucius_response}", speaker="Confucius")
            self.log_message("----------------------------------------", speaker="System")
            current_turn_input = confucius_response # Output becomes input for the next round (Socrates)

            # --- Add Moderator logic here if needed ---
            # Example: Evaluate Confucius' response before the next round


        # End of loop
        self.log_message("Director finished conversation loop.", speaker="Director")
        return conversation_successful