# Filename: direction.py

import time
import re
import socrates
import confucius
import moderator
import logging
from typing import List, Tuple # Added for type hinting

# --- Configuration ---
MAX_RETRIES = 3
RETRY_DELAY = 2

logging.basicConfig(level=logging.INFO, format='%(asctime)s - DIRECTOR - %(levelname)s - %(message)s')

THINK_BLOCK_REGEX = re.compile(r"<think>(.*?)</think>", re.DOTALL | re.IGNORECASE)

class Director:
    """
    Manages moderated conversation flow using text-based Summary/Guidance from Moderator.
    Configurable starting actor and rounds. Extracts <think> blocks, handles retries.
    Returns results synchronously for Streamlit.
    MODIFIED: Passes conversation history to the moderator.
    """
    def __init__(self):
        # (Initialization loads S, C, M chains - same as before)
        chains_loaded = True
        try:
            if not hasattr(socrates, 'socrates_chain') or socrates.socrates_chain is None: chains_loaded = False; logging.error("Socrates chain init failed.")
            else: self.socrates_chain = socrates.socrates_chain
            if not hasattr(confucius, 'confucius_chain') or confucius.confucius_chain is None: chains_loaded = False; logging.error("Confucius chain init failed.")
            else: self.confucius_chain = confucius.confucius_chain
            if not hasattr(moderator, 'moderator_chain') or moderator.moderator_chain is None: chains_loaded = False; logging.error("Moderator chain init failed.")
            else: self.moderator_chain = moderator.moderator_chain
        except Exception as e: chains_loaded = False; logging.error(f"Error during actor chain initialization: {e}")
        if not chains_loaded: raise ImportError("One or more actor chains failed to initialize.")
        else: logging.info("Director initialized successfully with all chains.")

    def _extract_and_clean(self, raw_response: str) -> Tuple[str, str | None]:
        # (Identical to previous version)
        monologue = None
        clean_response = raw_response
        # Use search instead of findall to handle potential multiple blocks (take first)
        match = THINK_BLOCK_REGEX.search(raw_response)
        if match:
            monologue = match.group(1).strip()
            # Replace all occurrences to clean the response
            clean_response = THINK_BLOCK_REGEX.sub('', raw_response).strip()
        # Handle cases where cleaning might leave an empty string but raw had content
        if not clean_response and raw_response:
            # If cleaning resulted in empty, return original non-empty raw as clean
            # This might happen if the *entire* response was a think block
            # Log a warning as this is unusual
            logging.warning("Cleaned response was empty, returning raw response. Was the entire response a think block?")
            return raw_response.strip(), monologue # Return raw as clean, but still provide monologue if found
        elif not clean_response and not raw_response:
             # If both raw and clean are empty/None, return empty string and None
             return "", None
        # Otherwise, return the cleaned response and monologue
        return clean_response, monologue

    def _robust_invoke(self, chain, input_dict: dict, actor_name: str, round_num: int) -> Tuple[str | None, str | None]:
        # (Modified to return Tuple[Optional[str], Optional[str]])
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logging.info(f"Round {round_num}: Requesting {actor_name} (Attempt {attempt}/{MAX_RETRIES})...")
                start_time = time.time()
                raw_response = chain.invoke(input_dict)
                end_time = time.time()
                logging.info(f"Round {round_num}: {actor_name} responded in {end_time - start_time:.2f}s.")

                # Check if response is valid before cleaning
                if raw_response and isinstance(raw_response, str) and raw_response.strip():
                    clean_response, monologue = self._extract_and_clean(raw_response)
                    # Check if cleaning resulted in an empty but usable response
                    if clean_response is not None: # Check for None explicitly if _extract_and_clean can return None
                         return clean_response, monologue
                    else:
                         # Handle case where cleaning might fail unexpectedly, though unlikely with current logic
                         raise ValueError("Cleaned response became None unexpectedly.")
                elif raw_response == "": # Handle intentionally empty response if needed by logic downstream
                     return "", None # Return empty string, no monologue
                else:
                    # Handle None or non-string/empty responses
                    raise ValueError(f"Invalid or empty raw response received from {actor_name}: {raw_response}")

            except Exception as e:
                # Log specific Langchain input errors if available
                if "Input to ChatPromptTemplate is missing variables" in str(e):
                    logging.error(f"LANGCHAIN INPUT ERROR - Round {round_num}, {actor_name}, Attempt {attempt}: {e}")
                else:
                    logging.error(f"Round {round_num}: {actor_name}'s turn failed (Attempt {attempt}): {e}")

                if attempt == MAX_RETRIES:
                    logging.error(f"Round {round_num}: {actor_name} failed permanently after {MAX_RETRIES} attempts.")
                    return None, None # Indicate permanent failure
                logging.info(f"Round {round_num}: Retrying {actor_name} in {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)

        # Should only be reached if loop finishes unexpectedly (e.g., MAX_RETRIES=0)
        logging.error(f"Round {round_num}: _robust_invoke finished loop unexpectedly for {actor_name}.")
        return None, None


    # --- UPDATED: Moderator Invocation uses history ---
    def _invoke_moderator_text(self, conversation_history: List[str], target_speaker_name: str, round_num: int) -> Tuple[str | None, str]:
        """
        Invokes the moderator, providing conversation history. Parses SUMMARY/GUIDANCE.

        Args:
            conversation_history (list[str]): Formatted list of dialogue turns ("SPEAKER: Content").
            target_speaker_name (str): The philosopher who will speak next.
            round_num (int): The current round number.

        Returns:
            tuple: (summary_str or None, guidance_str or "")
                   Returns (None, "") on critical failure (moderator fail or missing SUMMARY).
                   Guidance is returned as "" if not found or empty.
        """
        if not conversation_history:
            logging.error(f"Round {round_num}: _invoke_moderator_text called with empty history.")
            return None, "" # Cannot moderate without history

        # --- CONTEXT WINDOW WARNING ---
        # Passing the entire history might exceed the Moderator LLM's context limit.
        # For this prototype, we pass the full history as requested.
        # Consider limiting history (e.g., `conversation_history[-6:]`) for production.
        formatted_history = "\n\n".join(conversation_history)
        # -----------------------------

        # Get speaker name from the last entry in the history
        last_speaker = "Unknown"
        if conversation_history:
             parts = conversation_history[-1].split(":", 1)
             if len(parts) > 0:
                 last_speaker = parts[0].strip()


        # Construct the input providing the history context.
        moderator_user_input = (
            f"Here is the conversation history so far:\n"
            f"------ HISTORY START ------\n"
            f"{formatted_history}\n"
            f"------ HISTORY END ------\n\n"
            f"The last speaker was {last_speaker}.\n"
            f"The next speaker will be {target_speaker_name}.\n\n"
            f"[Instruction Reminder: Summarise the dialogue history concisely (include the exact last sentence spoken). Provide GUIDANCE for {target_speaker_name}. Follow the required output format precisely - two lines starting with SUMMARY: and GUIDANCE:]"
        )

        # Invoke moderator chain
        moderator_raw_output, _ = self._robust_invoke(
            self.moderator_chain,
            {"input": moderator_user_input}, # Pass the new input with history
            "Moderator",
            round_num
        )

        if moderator_raw_output is None:
            logging.error(f"Round {round_num}: Moderator failed to respond evaluating history ending with {last_speaker}.")
            return None, ""

        # Parse the expected two-line format
        summary_str = None
        guidance_str = ""
        try:
            lines = [line.strip() for line in moderator_raw_output.strip().splitlines() if line.strip()]
            found_summary = False
            for line in lines:
                line_upper = line.upper()
                # Use .lstrip() to handle potential leading spaces in prefix
                if line_upper.lstrip().startswith("SUMMARY:"):
                    summary_str = line.split(":", 1)[1].strip() # Split carefully
                    found_summary = True
                elif line_upper.lstrip().startswith("GUIDANCE:"):
                    guidance_str = line.split(":", 1)[1].strip() # Split carefully

            if not found_summary:
                logging.warning(f"Round {round_num}: Moderator output missing 'SUMMARY:' line. Raw:\n{moderator_raw_output}")
                return None, "" # Critical failure if summary is missing

            logging.info(f"Round {round_num}: Moderator summary/guidance parsed successfully for {last_speaker}.")
            return summary_str, guidance_str

        except Exception as e:
            logging.error(f"Round {round_num}: Failed to parse Moderator text output for {last_speaker}: {e}\nRaw:\n{moderator_raw_output}")
            return None, ""


    def run_conversation_streamlit(self, initial_input: str, num_rounds: int, starting_philosopher: str = "Socrates") -> Tuple[List[dict], str, bool]:
        """
        Runs the MODERATED conversation loop using text-based Summary/Guidance based on history.
        """
        logging.info(f"Director starting MODERATED conversation with HISTORY: Rounds={num_rounds}, Starter='{starting_philosopher}'.")
        generated_messages = []
        conversation_successful = True
        final_status = "Moderated conversation in progress..."

        # Determine initial actors
        if starting_philosopher == "Socrates":
            actor_1_name, actor_1_chain = "Socrates", self.socrates_chain
            actor_2_name, actor_2_chain = "Confucius", self.confucius_chain
        elif starting_philosopher == "Confucius":
            actor_1_name, actor_1_chain = "Confucius", self.confucius_chain
            actor_2_name, actor_2_chain = "Socrates", self.socrates_chain
        else:
            logging.error(f"Invalid starting philosopher: {starting_philosopher}")
            return [], "Error: Invalid starting philosopher.", False

        # --- Initialize conversation history tracking ---
        # Start history with the user's initial input. Format: "SPEAKER: Content"
        conversation_history: List[str] = [f"USER: {initial_input}"]
        # ----------------------------------------------------

        # Actor 1 starts with just the initial input for the *first* round
        current_input_content_for_actor = initial_input

        for i in range(num_rounds):
            round_num = i + 1
            logging.info(f"--- Starting Round {round_num} ({actor_1_name} -> M -> {actor_2_name} -> M) ---")

            # --- 1. First Actor's Turn ---
            # Actor receives previous turn's output + guidance (or initial input)
            actor_1_response, actor_1_monologue = self._robust_invoke(
                actor_1_chain, {"input": current_input_content_for_actor}, actor_1_name, round_num
            )
            if actor_1_response is None:
                error_msg = f"{actor_1_name} failed in round {round_num}."
                logging.error(error_msg)
                generated_messages.append({"role": "system", "content": error_msg, "monologue": None})
                conversation_successful = False
                final_status = f"Error: {actor_1_name} failed."
                break # Stop the loop

            # Add Actor 1 response to message list for UI/logging
            generated_messages.append({"role": actor_1_name, "content": actor_1_response, "monologue": actor_1_monologue})
            # Add Actor 1 response to history tracker
            conversation_history.append(f"{actor_1_name.upper()}: {actor_1_response}")

            # --- 2. Moderator evaluates history ending with Actor 1 -> provides Guidance for Actor 2 ---
            summary_for_actor_2, guidance_for_actor_2 = self._invoke_moderator_text(
                conversation_history, # Pass the accumulated history
                actor_2_name,
                round_num
            )
            # Add Moderator output to message list
            mod_output_text_1 = f"MODERATOR CONTEXT (for {actor_2_name}):\nSUMMARY: {summary_for_actor_2 or 'N/A'}\nGUIDANCE: {guidance_for_actor_2 or 'None'}"
            generated_messages.append({"role": "system", "content": mod_output_text_1, "monologue": None})

            # Check for critical failure (missing summary)
            if summary_for_actor_2 is None:
                error_msg = f"Moderator failed to generate valid summary after {actor_1_name} in round {round_num}."
                logging.error(error_msg)
                # Add specific error message for UI
                generated_messages.append({"role": "system", "content": f"Error: {error_msg}", "monologue": None})
                conversation_successful = False
                final_status = "Error: Moderator failed."
                break # Stop the loop

            # --- 3. Second Actor's Turn ---
            # Construct input for Actor 2 including summary and guidance
            actor_2_input_wrapper = (
                f"The previous speaker ({actor_1_name}) said:\n---\n{actor_1_response}\n---\n\n" # Clearly delimit previous response
                f"--- Moderator Context ---\n"
                f"Summary of conversation so far: {summary_for_actor_2}\n"
                f"Guidance for your response: {guidance_for_actor_2 or 'Continue the discussion naturally.'}\n"
                f"--- End Context ---\n\n"
                f"Your response:" # Optional prompt for the actor to respond
            )
            actor_2_response, actor_2_monologue = self._robust_invoke(
                actor_2_chain, {"input": actor_2_input_wrapper}, actor_2_name, round_num
            )
            if actor_2_response is None:
                error_msg = f"{actor_2_name} failed in round {round_num}."
                logging.error(error_msg)
                generated_messages.append({"role": "system", "content": error_msg, "monologue": None})
                conversation_successful = False
                final_status = f"Error: {actor_2_name} failed."
                break # Stop the loop

            # Add Actor 2 response to message list
            generated_messages.append({"role": actor_2_name, "content": actor_2_response, "monologue": actor_2_monologue})
            # Add Actor 2 response to history tracker
            conversation_history.append(f"{actor_2_name.upper()}: {actor_2_response}")

            # --- 4. Moderator evaluates history ending with Actor 2 -> provides Guidance for Actor 1 (next round) ---
            summary_for_actor_1, guidance_for_actor_1 = self._invoke_moderator_text(
                conversation_history, # Pass the accumulated history
                actor_1_name,
                round_num
            )
            # Add Moderator output to message list
            mod_output_text_2 = f"MODERATOR CONTEXT (for {actor_1_name}):\nSUMMARY: {summary_for_actor_1 or 'N/A'}\nGUIDANCE: {guidance_for_actor_1 or 'None'}"
            generated_messages.append({"role": "system", "content": mod_output_text_2, "monologue": None})

            # Check for critical failure
            if summary_for_actor_1 is None:
                error_msg = f"Moderator failed to generate valid summary after {actor_2_name} in round {round_num}."
                logging.error(error_msg)
                generated_messages.append({"role": "system", "content": f"Error: {error_msg}", "monologue": None})
                conversation_successful = False
                final_status = "Error: Moderator failed."
                break # Stop the loop

            # --- 5. Prepare input for Actor 1 for the *next* round ---
            current_input_content_for_actor = (
                 f"The previous speaker ({actor_2_name}) said:\n---\n{actor_2_response}\n---\n\n" # Clearly delimit
                 f"--- Moderator Context ---\n"
                 f"Summary of conversation so far: {summary_for_actor_1}\n"
                 f"Guidance for your response: {guidance_for_actor_1 or 'Continue the discussion naturally.'}\n"
                 f"--- End Context ---\n\n"
                 f"Your response:" # Optional prompt
            )
            logging.info(f"--- Completed Round {round_num} ---")


        # End of loop
        if conversation_successful:
            final_status = f"Moderated conversation completed after {num_rounds} rounds (Started with {starting_philosopher})."
            logging.info(final_status)
        # If loop broke early, final_status reflects the error

        return generated_messages, final_status, conversation_successful