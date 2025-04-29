# Filename: direction.py

import time
import re
import logging
from typing import List, Tuple, Dict, Any, Optional # Added/Updated for type hinting

# --- Local Imports ---
# Assume these initialize their respective chains upon import
try:
    import socrates
    import confucius
    import moderator
except ImportError as e:
     # If imports fail here, Director init will raise ImportError
     logging.critical(f"Failed to import actor modules: {e}", exc_info=True)
     raise

# --- Configuration ---
MAX_RETRIES = 3
RETRY_DELAY = 2 # seconds

# Configure logging for the Director module
logging.basicConfig(level=logging.INFO, format='%(asctime)s - DIRECTOR - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__) # Use module-specific logger

# Regex for extracting <think> blocks (case-insensitive, dot matches newline)
THINK_BLOCK_REGEX = re.compile(r"<think>(.*?)</think>", re.DOTALL | re.IGNORECASE)

class Director:
    """
    Manages moderated or direct conversation flow between philosophers.
    Handles configuration (starting actor, rounds, moderation mode).
    Extracts <think> blocks, handles retries.
    Returns results synchronously for Streamlit.
    """
    def __init__(self):
        """Initializes the Director, loading actor chains."""
        chains_loaded = True
        error_details = []

        # Load and validate chains
        try:
            if hasattr(socrates, 'socrates_chain') and socrates.socrates_chain is not None:
                self.socrates_chain = socrates.socrates_chain
            else:
                chains_loaded = False; error_details.append("Socrates chain missing/None.")
                logger.error("Socrates chain init failed.")

            if hasattr(confucius, 'confucius_chain') and confucius.confucius_chain is not None:
                self.confucius_chain = confucius.confucius_chain
            else:
                chains_loaded = False; error_details.append("Confucius chain missing/None.")
                logger.error("Confucius chain init failed.")

            if hasattr(moderator, 'moderator_chain') and moderator.moderator_chain is not None:
                self.moderator_chain = moderator.moderator_chain
            else:
                # This is only an error if moderation is attempted later, but good to know
                self.moderator_chain = None # Explicitly set to None if missing
                logger.warning("Moderator chain missing/None. Moderation will fail if attempted.")
                # chains_loaded = False # Or consider this non-fatal if bypass is an option
                # error_details.append("Moderator chain missing/None.")

        except Exception as e:
            chains_loaded = False
            error_details.append(f"Exception during chain loading: {e}")
            logger.exception("Error during actor chain initialization.") # Log traceback

        if not chains_loaded:
            # Raise ImportError with details if essential chains failed
            raise ImportError(f"One or more essential actor chains failed to initialize: {'; '.join(error_details)}")
        else:
            logger.info("Director initialized successfully with philosopher chains.")
            if self.moderator_chain is None:
                 logger.warning("Director initialized WITHOUT moderator chain.")


    def _extract_and_clean(self, raw_response: Optional[str]) -> Tuple[str, Optional[str]]:
        """Extracts first <think> block and returns cleaned response."""
        if not raw_response:
             return "", None # Handle None or empty input

        monologue: Optional[str] = None
        clean_response: str = raw_response

        match = THINK_BLOCK_REGEX.search(raw_response)
        if match:
            monologue = match.group(1).strip()
            # Replace all occurrences to clean the response
            clean_response = THINK_BLOCK_REGEX.sub('', raw_response).strip()

        # Handle cases where cleaning might leave an empty string but raw had content
        if not clean_response and raw_response:
            logger.warning("Cleaned response was empty, original might have been entirely a think block.")
            # Decide behavior: return raw, or empty? Returning empty might be safer.
            return "", monologue # Return empty string as clean, but provide monologue
        elif not clean_response and not raw_response:
             return "", None

        return clean_response, monologue


    def _robust_invoke(self, chain: Any, input_dict: Dict[str, Any], actor_name: str, round_num: int) -> Tuple[Optional[str], Optional[str]]:
        """Invokes LLM chain with retry logic, returns (clean_response, monologue)."""
        if chain is None: # Added check if chain failed to load
             logger.error(f"Round {round_num}: Cannot invoke {actor_name}, chain is None.")
             return None, None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.info(f"Round {round_num}: Requesting {actor_name} (Attempt {attempt}/{MAX_RETRIES}). Input keys: {list(input_dict.keys())}")
                start_time = time.time()
                # Assuming chain.invoke returns a string or object convertible to string
                raw_response_obj = chain.invoke(input_dict)
                # Handle potential non-string responses if necessary
                raw_response = str(raw_response_obj) if raw_response_obj is not None else None
                end_time = time.time()
                logger.info(f"Round {round_num}: {actor_name} responded in {end_time - start_time:.2f}s.")

                if raw_response is not None and raw_response.strip():
                    clean_response, monologue = self._extract_and_clean(raw_response)
                    # Return even if clean_response is empty but monologue exists
                    return clean_response, monologue
                elif raw_response == "": # Handle intentionally empty response
                     logger.info(f"Round {round_num}: {actor_name} returned an empty string response.")
                     return "", None # Return empty string, no monologue
                else:
                    # Handle None or other non-string/empty responses after stripping
                    raise ValueError(f"Invalid or empty raw response received from {actor_name} after stripping: '{raw_response}'")

            except Exception as e:
                logger.error(f"Round {round_num}: {actor_name}'s turn failed (Attempt {attempt}): {e}", exc_info=True) # Log traceback for unexpected errors
                if attempt == MAX_RETRIES:
                    logger.error(f"Round {round_num}: {actor_name} failed permanently after {MAX_RETRIES} attempts.")
                    return None, None # Indicate permanent failure
                logger.info(f"Round {round_num}: Retrying {actor_name} in {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)

        logger.error(f"Round {round_num}: _robust_invoke finished loop unexpectedly for {actor_name}.")
        return None, None


    def _invoke_moderator_text(self, previous_speaker_name: str, previous_response: str, target_speaker_name: str, round_num: int) -> Tuple[Optional[str], str]:
        """Invokes the moderator, parses plain text SUMMARY/GUIDANCE output."""
        if self.moderator_chain is None: # Check if moderator loaded
             logger.error(f"Round {round_num}: Cannot invoke Moderator, chain is None.")
             return None, "" # Critical failure if moderator needed but not loaded

        moderator_user_input = (
            f"The previous speaker was {previous_speaker_name}.\n"
            f"Their response was:\n---\n{previous_response}\n---\n"
            f"The next speaker will be {target_speaker_name}.\n\n"
            f"[Instruction Reminder: Follow the required output format precisely - two lines starting with SUMMARY: and GUIDANCE:]"
        )

        moderator_raw_output, _ = self._robust_invoke(
            self.moderator_chain,
            {"input": moderator_user_input},
            "Moderator",
            round_num
        )

        if moderator_raw_output is None:
            logger.error(f"Round {round_num}: Moderator failed to respond evaluating {previous_speaker_name}.")
            return None, "" # Critical failure

        # Parse the expected two-line format
        summary_str: Optional[str] = None
        guidance_str: str = ""
        try:
            lines = [line.strip() for line in moderator_raw_output.strip().splitlines() if line.strip()]
            found_summary = False
            for line in lines:
                 line_upper = line.upper()
                 # Use .lstrip() to handle potential leading spaces in prefix
                 if line_upper.lstrip().startswith("SUMMARY:"):
                     # Split carefully to handle colons within the summary/guidance itself
                     parts = line.split(":", 1)
                     if len(parts) > 1: summary_str = parts[1].strip()
                     else: summary_str = "" # Handle case "SUMMARY:" with no text
                     found_summary = True
                 elif line_upper.lstrip().startswith("GUIDANCE:"):
                     parts = line.split(":", 1)
                     if len(parts) > 1: guidance_str = parts[1].strip()
                     else: guidance_str = "" # Handle case "GUIDANCE:" with no text

            if not found_summary:
                 logger.warning(f"Round {round_num}: Moderator output missing 'SUMMARY:' line. Treating as failure. Raw:\n{moderator_raw_output}")
                 return None, "" # Critical failure if summary is missing

            logger.info(f"Round {round_num}: Moderator summary/guidance parsed successfully for {previous_speaker_name}.")
            return summary_str, guidance_str

        except Exception as e:
            logger.error(f"Round {round_num}: Failed to parse Moderator text output for {previous_speaker_name}: {e}\nRaw:\n{moderator_raw_output}", exc_info=True)
            return None, "" # Critical failure on parsing error


    # --- Updated run_conversation_streamlit with run_moderated flag ---
    def run_conversation_streamlit(self,
                                  initial_input: str,
                                  num_rounds: int,
                                  starting_philosopher: str = "Socrates",
                                  run_moderated: bool = True # New flag, defaults to True
                                  ) -> Tuple[List[Dict[str, Any]], str, bool]:
        """
        Runs the conversation loop, either moderated or direct, based on run_moderated flag.
        """
        mode = "MODERATED" if run_moderated else "DIRECT"
        logger.info(f"Director starting {mode} conversation: Rounds={num_rounds}, Starter='{starting_philosopher}'.")
        generated_messages: List[Dict[str, Any]] = []
        conversation_successful: bool = True
        final_status: str = f"{mode} conversation in progress..."

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

        # Initialize input for the first turn
        current_input_content: str = initial_input

        for i in range(num_rounds):
            round_num = i + 1
            logger.info(f"--- Starting Round {round_num} ({mode}) ---")

            # --- 1. First Actor's Turn ---
            actor_1_response, actor_1_monologue = self._robust_invoke(
                actor_1_chain, {"input": current_input_content}, actor_1_name, round_num
            )
            if actor_1_response is None:
                error_msg = f"{actor_1_name} failed in round {round_num}."
                logger.error(error_msg)
                generated_messages.append({"role": "system", "content": f"Error: {error_msg}", "monologue": None})
                conversation_successful = False; final_status = f"Error: {actor_1_name} failed."; break
            generated_messages.append({"role": actor_1_name, "content": actor_1_response, "monologue": actor_1_monologue})

            # --- 2. Moderator (or bypass) ---
            summary_for_actor_2: Optional[str] = None
            guidance_for_actor_2: str = ""
            if run_moderated:
                if self.moderator_chain is None: # Double check moderator loaded if needed
                     error_msg = f"Moderator chain not loaded, cannot run moderated mode in round {round_num}."
                     logger.error(error_msg)
                     generated_messages.append({"role": "system", "content": f"Error: {error_msg}", "monologue": None})
                     conversation_successful = False; final_status = "Error: Moderator not available."; break

                summary_for_actor_2, guidance_for_actor_2 = self._invoke_moderator_text(
                    actor_1_name, actor_1_response, actor_2_name, round_num
                )
                mod_output_text_1 = f"MODERATOR CONTEXT (for {actor_2_name}):\nSUMMARY: {summary_for_actor_2 or 'N/A'}\nGUIDANCE: {guidance_for_actor_2 or 'None'}"
                generated_messages.append({"role": "system", "content": mod_output_text_1, "monologue": None})
                if summary_for_actor_2 is None: # Check for critical moderator failure
                     error_msg = f"Moderator failed after {actor_1_name} in round {round_num}."
                     logger.error(error_msg)
                     generated_messages.append({"role": "system", "content": f"Error: {error_msg}", "monologue": None})
                     conversation_successful = False; final_status = "Error: Moderator failed."; break
                actor_2_input_wrapper = (
                    f"{actor_1_response}\n\n"
                    f"--- Moderator Context ---\n"
                    f"Summary: {summary_for_actor_2}\n"
                    f"Guidance for your response: {guidance_for_actor_2 or 'Continue the discussion naturally.'}\n"
                    f"--- End Context ---"
                )
            else: # Bypass moderator
                actor_2_input_wrapper = actor_1_response # Direct response is input
                # Optionally add a system message indicating bypass
                # generated_messages.append({"role": "system", "content": "[Moderator Bypassed]", "monologue": None})


            # --- 3. Second Actor's Turn ---
            actor_2_response, actor_2_monologue = self._robust_invoke(
                actor_2_chain, {"input": actor_2_input_wrapper}, actor_2_name, round_num
            )
            if actor_2_response is None:
                error_msg = f"{actor_2_name} failed in round {round_num}."
                logger.error(error_msg)
                generated_messages.append({"role": "system", "content": f"Error: {error_msg}", "monologue": None})
                conversation_successful = False; final_status = f"Error: {actor_2_name} failed."; break
            generated_messages.append({"role": actor_2_name, "content": actor_2_response, "monologue": actor_2_monologue})

            # --- 4. Moderator (or bypass) for next round's input ---
            summary_for_actor_1: Optional[str] = None
            guidance_for_actor_1: str = ""
            if run_moderated:
                if self.moderator_chain is None: # Double check moderator loaded
                     error_msg = f"Moderator chain not loaded, cannot run moderated mode in round {round_num}."
                     logger.error(error_msg)
                     generated_messages.append({"role": "system", "content": f"Error: {error_msg}", "monologue": None})
                     conversation_successful = False; final_status = "Error: Moderator not available."; break

                summary_for_actor_1, guidance_for_actor_1 = self._invoke_moderator_text(
                    actor_2_name, actor_2_response, actor_1_name, round_num
                )
                mod_output_text_2 = f"MODERATOR CONTEXT (for {actor_1_name}):\nSUMMARY: {summary_for_actor_1 or 'N/A'}\nGUIDANCE: {guidance_for_actor_1 or 'None'}"
                generated_messages.append({"role": "system", "content": mod_output_text_2, "monologue": None})
                if summary_for_actor_1 is None: # Check for critical moderator failure
                     error_msg = f"Moderator failed after {actor_2_name} in round {round_num}."
                     logger.error(error_msg)
                     generated_messages.append({"role": "system", "content": f"Error: {error_msg}", "monologue": None})
                     conversation_successful = False; final_status = "Error: Moderator failed."; break
                 # --- 5. Prepare input for Actor 1 for the *next* round (Moderated) ---
                current_input_content = (
                    f"{actor_2_response}\n\n"
                    f"--- Moderator Context ---\n"
                    f"Summary: {summary_for_actor_1}\n"
                    f"Guidance for your response: {guidance_for_actor_1 or 'Continue the discussion naturally.'}\n"
                    f"--- End Context ---"
                )
            else: # Bypass moderator
                 # --- 5. Prepare input for Actor 1 for the *next* round (Direct) ---
                 current_input_content = actor_2_response
                 # Optionally add a system message indicating bypass
                 # generated_messages.append({"role": "system", "content": "[Moderator Bypassed]", "monologue": None})

            logger.info(f"--- Completed Round {round_num} ---")


        # End of loop
        if conversation_successful:
            final_status = f"{mode} conversation completed after {num_rounds} rounds (Started with {starting_philosopher})."
            logger.info(final_status)
        # If loop broke early, final_status should reflect the error

        return generated_messages, final_status, conversation_successful