# Filename: direction.py

import time
import re
import json
import socrates
import confucius
import moderator
import logging

# --- Configuration ---
MAX_RETRIES = 3
RETRY_DELAY = 2

logging.basicConfig(level=logging.INFO, format='%(asctime)s - DIRECTOR - %(levelname)s - %(message)s')

THINK_BLOCK_REGEX = re.compile(r"<think>(.*?)</think>", re.DOTALL | re.IGNORECASE)

class Director:
    """
    Manages moderated conversation flow with configurable options.
    Uses a separate method for single-round logic for modularity.
    Extracts <think> blocks, handles retries.
    Returns results synchronously for Streamlit.
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

    def _extract_and_clean(self, raw_response):
        # (Identical to previous version)
        monologue = None; clean_response = raw_response
        match = THINK_BLOCK_REGEX.search(raw_response)
        if match: monologue = match.group(1).strip(); clean_response = THINK_BLOCK_REGEX.sub('', raw_response).strip()
        if not clean_response and raw_response: return raw_response.strip(), None
        return clean_response, monologue

    def _robust_invoke(self, chain, input_dict, actor_name, round_num):
        # (Identical to previous version - returns clean_response, monologue)
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logging.info(f"Round {round_num}: Requesting {actor_name} (Attempt {attempt}/{MAX_RETRIES})...")
                start_time = time.time(); raw_response = chain.invoke(input_dict); end_time = time.time()
                logging.info(f"Round {round_num}: {actor_name} responded in {end_time - start_time:.2f}s.")
                if raw_response and isinstance(raw_response, str) and raw_response.strip():
                    clean_response, monologue = self._extract_and_clean(raw_response)
                    if clean_response: return clean_response, monologue
                    else: raise ValueError("Cleaned response is empty")
                else: raise ValueError("Empty raw response received")
            except Exception as e:
                logging.error(f"Round {round_num}: {actor_name}'s turn failed (Attempt {attempt}): {e}")
                if attempt == MAX_RETRIES: return None, None
                logging.info(f"Round {round_num}: Retrying {actor_name} in {RETRY_DELAY}s..."); time.sleep(RETRY_DELAY)
        return None, None

    def _invoke_moderator(self, previous_speaker_name, previous_response, target_speaker_name, round_num):
         # (Identical to previous version - returns addendum, log_output)
        moderator_input_text = (
            f"**Context:**\nPrevious speaker: {previous_speaker_name}\nResponse:\n```\n{previous_response}\n```\n"
            f"**Task:** Evaluate {previous_speaker_name}'s response. Provide summary. Generate 'next_prompt_addendum' for {target_speaker_name} if needed. Output only valid JSON."
        )
        moderator_raw_output, _ = self._robust_invoke(self.moderator_chain, {"input": moderator_input_text}, "Moderator", round_num)
        if moderator_raw_output is None: return None, f"Error: Moderator failed to respond evaluating {previous_speaker_name}."
        try:
            if moderator_raw_output.strip().startswith("```json"): moderator_raw_output = moderator_raw_output.strip()[7:-3].strip()
            elif moderator_raw_output.strip().startswith("```"): moderator_raw_output = moderator_raw_output.strip()[3:-3].strip()
            moderator_data = json.loads(moderator_raw_output)
            addendum = moderator_data.get("next_prompt_addendum", "")
            log_output = json.dumps(moderator_data, indent=2)
            logging.info(f"Round {round_num}: Moderator evaluation successful for {previous_speaker_name}.")
            return addendum, log_output
        except Exception as e:
            logging.error(f"Round {round_num}: Failed to process Moderator output for {previous_speaker_name}: {e}\nRaw:\n{moderator_raw_output}")
            error_log = f"Error processing Moderator output for {previous_speaker_name}.\nRaw:\n{moderator_raw_output}"
            return "", error_log

    # --- NEW: Separated function for executing one round ---
    def _execute_one_moderated_round(self, current_input_for_actor_1,
                                      actor_1_name, actor_1_chain,
                                      actor_2_name, actor_2_chain,
                                      round_num):
        """
        Executes one full moderated round: Actor1 -> Mod -> Actor2 -> Mod.

        Args:
            current_input_for_actor_1 (str): The input content for the first actor.
            actor_1_name (str): Name of the first actor.
            actor_1_chain: Langchain chain for the first actor.
            actor_2_name (str): Name of the second actor.
            actor_2_chain: Langchain chain for the second actor.
            round_num (int): The current round number.

        Returns:
            tuple: (round_messages, next_input_for_actor_1, round_success)
        """
        round_messages = []
        round_success = True
        next_input_for_actor_1 = None # Initialize

        # --- 1. First Actor's Turn ---
        actor_1_response, actor_1_monologue = self._robust_invoke(
            actor_1_chain, {"input": current_input_for_actor_1}, actor_1_name, round_num
        )
        if actor_1_response is None:
            error_msg = f"Director stopped: {actor_1_name} failed in round {round_num}."
            round_messages.append({"role": "system", "content": error_msg, "monologue": None})
            return round_messages, None, False # Round failed
        round_messages.append({"role": actor_1_name, "content": actor_1_response, "monologue": actor_1_monologue})

        # --- 2. Moderator evaluates Actor 1 -> provides addendum for Actor 2 ---
        addendum_for_actor_2, mod_log_1 = self._invoke_moderator(actor_1_name, actor_1_response, actor_2_name, round_num)
        round_messages.append({"role": "system", "content": f"MODERATOR EVALUATION (for {actor_2_name}):\n```json\n{mod_log_1}\n```", "monologue": None})
        if addendum_for_actor_2 is None: # Moderator failed
             error_msg = f"Director stopped: Moderator failed after {actor_1_name} in round {round_num}."
             round_messages.append({"role": "system", "content": error_msg, "monologue": None})
             return round_messages, None, False # Round failed

        # --- 3. Second Actor's Turn ---
        actor_2_input_content = f"{actor_1_response}\n\n[Moderator Guidance: {addendum_for_actor_2}]" if addendum_for_actor_2 else actor_1_response
        actor_2_response, actor_2_monologue = self._robust_invoke(
            actor_2_chain, {"input": actor_2_input_content}, actor_2_name, round_num
        )
        if actor_2_response is None:
            error_msg = f"Director stopped: {actor_2_name} failed in round {round_num}."
            round_messages.append({"role": "system", "content": error_msg, "monologue": None})
            return round_messages, None, False # Round failed
        round_messages.append({"role": actor_2_name, "content": actor_2_response, "monologue": actor_2_monologue})

        # --- 4. Moderator evaluates Actor 2 -> provides addendum for Actor 1 (next round) ---
        addendum_for_actor_1, mod_log_2 = self._invoke_moderator(actor_2_name, actor_2_response, actor_1_name, round_num)
        round_messages.append({"role": "system", "content": f"MODERATOR EVALUATION (for {actor_1_name}):\n```json\n{mod_log_2}\n```", "monologue": None})
        if addendum_for_actor_1 is None: # Moderator failed
             error_msg = f"Director stopped: Moderator failed after {actor_2_name} in round {round_num}."
             round_messages.append({"role": "system", "content": error_msg, "monologue": None})
             return round_messages, None, False # Round failed

        # --- 5. Prepare input for Actor 1 for the *next* round ---
        next_input_for_actor_1 = f"{actor_2_response}\n\n[Moderator Guidance: {addendum_for_actor_1}]" if addendum_for_actor_1 else actor_2_response

        # logging.info(f"--- Completed Round {round_num} internally ---")
        return round_messages, next_input_for_actor_1, True


    def run_conversation_streamlit(self, initial_input, num_rounds, starting_philosopher="Socrates"):
        """
        Runs the MODERATED conversation loop by calling the round execution function.
        """
        logging.info(f"Director starting MODERATED conversation: Rounds={num_rounds}, Starter='{starting_philosopher}'.")
        generated_messages = [] # Accumulate messages from all rounds
        conversation_successful = True
        final_status = "Moderated conversation in progress..."

        # Determine initial actors based on starting choice
        if starting_philosopher == "Socrates":
            actor_1_name, actor_1_chain = "Socrates", self.socrates_chain
            actor_2_name, actor_2_chain = "Confucius", self.confucius_chain
        elif starting_philosopher == "Confucius":
            actor_1_name, actor_1_chain = "Confucius", self.confucius_chain
            actor_2_name, actor_2_chain = "Socrates", self.socrates_chain
        else:
            logging.error(f"Invalid starting philosopher: {starting_philosopher}")
            return [], "Error: Invalid starting philosopher selected.", False

        # Initialize the input for the first actor for the first round
        current_input_content = initial_input

        for i in range(num_rounds):
            round_num = i + 1
            logging.info(f"--- Orchestrating Round {round_num} ---")

            # Execute one round using the separated function
            round_messages, next_input, round_success = self._execute_one_moderated_round(
                current_input_content,
                actor_1_name, actor_1_chain,
                actor_2_name, actor_2_chain,
                round_num
            )

            # Add messages from this round to the overall list
            generated_messages.extend(round_messages)

            # Check if the round failed
            if not round_success:
                conversation_successful = False
                # Use the last message from round_messages if it contains the error, or set a generic one
                final_status = generated_messages[-1]['content'] if generated_messages and generated_messages[-1]['role']=='system' else f"Conversation failed during round {round_num}."
                logging.error(f"Stopping conversation due to failure in round {round_num}.")
                break # Stop processing further rounds

            # Prepare input for the *next* round
            current_input_content = next_input
            logging.info(f"--- Successfully Finished Orchestrating Round {round_num} ---")

        # End of loop
        if conversation_successful:
            final_status = f"Moderated conversation completed after {num_rounds} rounds (Started with {starting_philosopher})."
            logging.info(final_status)
        # If loop broke early, final_status should reflect the error

        return generated_messages, final_status, conversation_successful