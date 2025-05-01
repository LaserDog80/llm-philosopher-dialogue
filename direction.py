# Filename: direction.py

import time
import re
import logging
from typing import List, Tuple, Dict, Any, Optional

# --- Local Imports ---
# Import the modules to access their get_chain functions
try:
    import socrates
    import confucius
    import moderator
except ImportError as e:
     logging.critical(f"Failed to import actor modules: {e}", exc_info=True)
     raise # Stop if modules can't be imported

# --- Configuration ---
MAX_RETRIES = 3
RETRY_DELAY = 2 # seconds

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - DIRECTOR - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

THINK_BLOCK_REGEX = re.compile(r"<think>(.*?)</think>", re.DOTALL | re.IGNORECASE)

class Director:
    """
    Manages moderated or direct conversation flow between philosophers.
    Handles configuration (starting actor, rounds, moderation mode).
    Loads appropriate chains based on mode for each run.
    Extracts <think> blocks, handles retries.
    Returns results synchronously for Streamlit.
    """
    def __init__(self):
        """Initializes the Director WITHOUT pre-loading chains."""
        # Chains are now loaded dynamically within run_conversation_streamlit
        logger.info("Director initialized (chains will be loaded per conversation mode).")

    def _extract_and_clean(self, raw_response: Optional[str]) -> Tuple[str, Optional[str]]:
        """Extracts first <think> block and returns cleaned response."""
        # (Code identical to previous version - kept for brevity)
        if not raw_response: return "", None
        monologue: Optional[str] = None; clean_response: str = raw_response
        match = THINK_BLOCK_REGEX.search(raw_response)
        if match: monologue = match.group(1).strip(); clean_response = THINK_BLOCK_REGEX.sub('', raw_response).strip()
        if not clean_response and raw_response: logger.warning("Cleaned response was empty, original might have been entirely a think block."); return "", monologue
        elif not clean_response and not raw_response: return "", None
        return clean_response, monologue


    def _robust_invoke(self, chain: Any, input_dict: Dict[str, Any], actor_name: str, round_num: int) -> Tuple[Optional[str], Optional[str]]:
        """Invokes LLM chain with retry logic, returns (clean_response, monologue)."""
        # (Code identical to previous version - kept for brevity)
        if chain is None: logger.error(f"Round {round_num}: Cannot invoke {actor_name}, chain is None."); return None, None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.info(f"Round {round_num}: Requesting {actor_name} (Attempt {attempt}/{MAX_RETRIES}). Input keys: {list(input_dict.keys())}")
                start_time = time.time(); raw_response_obj = chain.invoke(input_dict); raw_response = str(raw_response_obj) if raw_response_obj is not None else None; end_time = time.time()
                logger.info(f"Round {round_num}: {actor_name} responded in {end_time - start_time:.2f}s.")
                if raw_response is not None and raw_response.strip(): clean_response, monologue = self._extract_and_clean(raw_response); return clean_response, monologue
                elif raw_response == "": logger.info(f"Round {round_num}: {actor_name} returned an empty string."); return "", None
                else: raise ValueError(f"Invalid or empty raw response from {actor_name}: '{raw_response}'")
            except Exception as e:
                logger.error(f"Round {round_num}: {actor_name}'s turn failed (Attempt {attempt}): {e}", exc_info=True)
                if attempt == MAX_RETRIES: logger.error(f"Round {round_num}: {actor_name} failed permanently."); return None, None
                logger.info(f"Round {round_num}: Retrying {actor_name} in {RETRY_DELAY}s..."); time.sleep(RETRY_DELAY)
        logger.error(f"Round {round_num}: _robust_invoke finished loop unexpectedly for {actor_name}."); return None, None

    # Note: _invoke_moderator_text now needs the moderator_chain passed to it
    def _invoke_moderator_text(self, moderator_chain: Any, previous_speaker_name: str, previous_response: str, target_speaker_name: str, round_num: int) -> Tuple[Optional[str], str]:
        """Invokes the moderator, parses plain text SUMMARY/GUIDANCE output."""
        if moderator_chain is None: # Check if moderator loaded for this run
             logger.error(f"Round {round_num}: Cannot invoke Moderator, chain is None for this mode/run.")
             # Return critical failure indication
             # Returning None for summary signifies failure to the main loop
             return None, "Error: Moderator chain not available for this mode."

        moderator_user_input = (
            f"The previous speaker was {previous_speaker_name}.\n"
            f"Their response was:\n---\n{previous_response}\n---\n"
            f"The next speaker will be {target_speaker_name}.\n\n"
            f"[Instruction Reminder: Follow the required output format precisely - two lines starting with SUMMARY: and GUIDANCE:]"
        )

        # Use the passed-in moderator_chain
        moderator_raw_output, _ = self._robust_invoke(
            moderator_chain,
            {"input": moderator_user_input},
            "Moderator",
            round_num
        )

        if moderator_raw_output is None:
            logger.error(f"Round {round_num}: Moderator failed to respond evaluating {previous_speaker_name}.")
            return None, "Error: Moderator failed to generate response." # Critical failure

        # (Parsing logic identical to previous version - kept for brevity)
        summary_str: Optional[str] = None; guidance_str: str = ""
        try:
            lines = [line.strip() for line in moderator_raw_output.strip().splitlines() if line.strip()]
            found_summary = False
            for line in lines:
                 line_upper = line.upper()
                 if line_upper.lstrip().startswith("SUMMARY:"): parts = line.split(":", 1); summary_str = parts[1].strip() if len(parts) > 1 else ""; found_summary = True
                 elif line_upper.lstrip().startswith("GUIDANCE:"): parts = line.split(":", 1); guidance_str = parts[1].strip() if len(parts) > 1 else ""
            if not found_summary: logger.warning(f"Round {round_num}: Moderator output missing 'SUMMARY:'. Raw:\n{moderator_raw_output}"); return None, "Error: Moderator output format invalid (Missing SUMMARY)."
            logger.info(f"Round {round_num}: Moderator summary/guidance parsed successfully for {previous_speaker_name}.")
            return summary_str, guidance_str
        except Exception as e:
            logger.error(f"Round {round_num}: Failed to parse Moderator text output: {e}\nRaw:\n{moderator_raw_output}", exc_info=True)
            return None, "Error: Failed to parse moderator output." # Critical failure


    # --- Modified run_conversation_streamlit to accept mode and load chains ---
    def run_conversation_streamlit(self,
                                  initial_input: str,
                                  num_rounds: int,
                                  starting_philosopher: str = "Socrates",
                                  run_moderated: bool = True,
                                  mode: str = 'philosophy' # <-- Added mode argument
                                  ) -> Tuple[List[Dict[str, Any]], str, bool]:
        """
        Runs the conversation loop, dynamically loading chains based on the mode.
        """
        run_mode_desc = "MODERATED" if run_moderated else "DIRECT"
        logger.info(f"Director starting {run_mode_desc} conversation in '{mode}' mode: Rounds={num_rounds}, Starter='{starting_philosopher}'.")
        generated_messages: List[Dict[str, Any]] = []
        conversation_successful: bool = True
        final_status: str = f"{run_mode_desc} conversation ('{mode}' mode) in progress..."

        # --- Dynamically load chains for this run based on mode ---
        try:
            socrates_chain = socrates.get_chain(mode=mode)
            confucius_chain = confucius.get_chain(mode=mode)
            # Load moderator chain only if needed for this run
            moderator_chain = moderator.get_chain(mode=mode) if run_moderated else None

            if socrates_chain is None or confucius_chain is None:
                 raise ImportError(f"Failed to load philosopher chains for mode '{mode}'.")
            if run_moderated and moderator_chain is None:
                 # Log warning but maybe allow proceeding if bypass is an option?
                 # For now, treat as error if moderation was requested but chain failed.
                 logger.error(f"Moderation requested but failed to load moderator chain for mode '{mode}'.")
                 raise ImportError(f"Failed to load moderator chain for mode '{mode}'.")

            logger.info(f"Chains loaded successfully for mode '{mode}'.")

        except ImportError as e:
            logger.critical(f"Chain loading failed: {e}", exc_info=True)
            return [], f"Error: Failed to load necessary models for '{mode}' mode.", False
        except Exception as e:
             logger.critical(f"Unexpected error during chain loading: {e}", exc_info=True)
             return [], f"Error: Unexpected error loading models.", False
        # --- End Chain Loading ---


        # Determine initial actors using the dynamically loaded chains
        if starting_philosopher == "Socrates":
            actor_1_name, actor_1_chain = "Socrates", socrates_chain
            actor_2_name, actor_2_chain = "Confucius", confucius_chain
        elif starting_philosopher == "Confucius":
            actor_1_name, actor_1_chain = "Confucius", confucius_chain
            actor_2_name, actor_2_chain = "Socrates", socrates_chain
        else:
            logger.error(f"Invalid starting philosopher: {starting_philosopher}")
            return [], "Error: Invalid starting philosopher.", False

        current_input_content: str = initial_input

        # --- Conversation Loop ---
        for i in range(num_rounds):
            round_num = i + 1
            logger.info(f"--- Starting Round {round_num} ({run_mode_desc}, Mode: {mode}) ---")

            # 1. First Actor's Turn
            actor_1_response, actor_1_monologue = self._robust_invoke(
                actor_1_chain, {"input": current_input_content}, actor_1_name, round_num
            )
            if actor_1_response is None:
                error_msg = f"{actor_1_name} failed in round {round_num}."; logger.error(error_msg)
                generated_messages.append({"role": "system", "content": f"Error: {error_msg}", "monologue": None})
                conversation_successful = False; final_status = f"Error: {actor_1_name} failed."; break
            generated_messages.append({"role": actor_1_name, "content": actor_1_response, "monologue": actor_1_monologue})

            # 2. Moderator (or bypass)
            summary_for_actor_2: Optional[str] = None
            guidance_for_actor_2: str = ""
            actor_2_input_wrapper: str
            if run_moderated:
                # Pass the dynamically loaded moderator_chain
                summary_for_actor_2, guidance_for_actor_2 = self._invoke_moderator_text(
                    moderator_chain, actor_1_name, actor_1_response, actor_2_name, round_num
                )
                mod_output_text_1 = f"MODERATOR CONTEXT (for {actor_2_name}):\nSUMMARY: {summary_for_actor_2 or 'N/A'}\nGUIDANCE: {guidance_for_actor_2 or 'None'}"
                generated_messages.append({"role": "system", "content": mod_output_text_1, "monologue": None})

                # Check for critical moderator failure (indicated by summary being None)
                if summary_for_actor_2 is None:
                     error_msg = f"Moderator failed after {actor_1_name} in round {round_num}. Details: {guidance_for_actor_2}" # Guidance holds error msg here
                     logger.error(error_msg)
                     # Append the specific error from moderator invocation
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
                actor_2_input_wrapper = actor_1_response

            # 3. Second Actor's Turn
            actor_2_response, actor_2_monologue = self._robust_invoke(
                actor_2_chain, {"input": actor_2_input_wrapper}, actor_2_name, round_num
            )
            if actor_2_response is None:
                error_msg = f"{actor_2_name} failed in round {round_num}."; logger.error(error_msg)
                generated_messages.append({"role": "system", "content": f"Error: {error_msg}", "monologue": None})
                conversation_successful = False; final_status = f"Error: {actor_2_name} failed."; break
            generated_messages.append({"role": actor_2_name, "content": actor_2_response, "monologue": actor_2_monologue})

            # 4. Moderator (or bypass) for next round's input
            summary_for_actor_1: Optional[str] = None
            guidance_for_actor_1: str = ""
            if run_moderated:
                # Pass the dynamically loaded moderator_chain again
                summary_for_actor_1, guidance_for_actor_1 = self._invoke_moderator_text(
                    moderator_chain, actor_2_name, actor_2_response, actor_1_name, round_num
                )
                mod_output_text_2 = f"MODERATOR CONTEXT (for {actor_1_name}):\nSUMMARY: {summary_for_actor_1 or 'N/A'}\nGUIDANCE: {guidance_for_actor_1 or 'None'}"
                generated_messages.append({"role": "system", "content": mod_output_text_2, "monologue": None})

                if summary_for_actor_1 is None: # Check for critical moderator failure
                     error_msg = f"Moderator failed after {actor_2_name} in round {round_num}. Details: {guidance_for_actor_1}"
                     logger.error(error_msg)
                     generated_messages.append({"role": "system", "content": f"Error: {error_msg}", "monologue": None})
                     conversation_successful = False; final_status = "Error: Moderator failed."; break

                 # 5. Prepare input for Actor 1 for the *next* round (Moderated)
                current_input_content = (
                    f"{actor_2_response}\n\n"
                    f"--- Moderator Context ---\n"
                    f"Summary: {summary_for_actor_1}\n"
                    f"Guidance for your response: {guidance_for_actor_1 or 'Continue the discussion naturally.'}\n"
                    f"--- End Context ---"
                )
            else: # Bypass moderator
                 # 5. Prepare input for Actor 1 for the *next* round (Direct)
                 current_input_content = actor_2_response

            logger.info(f"--- Completed Round {round_num} ---")
        # --- End Loop ---

        if conversation_successful:
            final_status = f"{run_mode_desc} conversation ('{mode}' mode) completed after {num_rounds} rounds."
            logger.info(final_status)

        return generated_messages, final_status, conversation_successful