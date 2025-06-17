# Filename: direction.py

import time
import re
import logging
from typing import List, Tuple, Dict, Any, Optional

# --- Local Imports ---
try:
    import socrates
    import confucius
    import moderator
except ImportError as e:
     logging.critical(f"Failed to import actor modules: {e}", exc_info=True)
     raise

# --- Configuration ---
MAX_RETRIES = 3
RETRY_DELAY = 2 # seconds

logging.basicConfig(level=logging.INFO, format='%(asctime)s - DIRECTOR - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

THINK_BLOCK_REGEX = re.compile(r"<think>(.*?)</think>", re.DOTALL | re.IGNORECASE)

class Director:
    # MODIFICATION: Added status_callback to the constructor
    def __init__(self, status_callback=None):
        self.status_callback = status_callback
        logger.info("Director initialized.")
        if self.status_callback:
            self.status_callback("Director initialized.")

    def _update_status(self, message: str):
        """Safely call the status callback if it exists."""
        if self.status_callback:
            self.status_callback(message)

    def _extract_and_clean(self, raw_response: Optional[str]) -> Tuple[str, Optional[str]]:
        if not raw_response: return "", None
        monologue: Optional[str] = None; clean_response: str = raw_response
        match = THINK_BLOCK_REGEX.search(raw_response)
        if match: monologue = match.group(1).strip(); clean_response = THINK_BLOCK_REGEX.sub('', raw_response).strip()
        if not clean_response and raw_response: logger.warning("Cleaned response was empty, original might have been entirely a think block."); return "", monologue
        elif not clean_response and not raw_response: return "", None
        return clean_response, monologue

    def _robust_invoke(self, chain: Any, input_dict: Dict[str, Any], actor_name: str, round_num: int) -> Tuple[Optional[str], Optional[str]]:
        if chain is None: logger.error(f"Round {round_num}: Cannot invoke {actor_name}, chain is None."); return None, None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                # MODIFICATION: Report status before making the request
                status_msg = f"Round {round_num}: Requesting {actor_name} (Attempt {attempt}/{MAX_RETRIES})..."
                logger.info(status_msg)
                self._update_status(status_msg)

                start_time = time.time(); raw_response_obj = chain.invoke(input_dict); raw_response = str(raw_response_obj) if raw_response_obj is not None else None; end_time = time.time()
                
                # MODIFICATION: Report status after getting a response
                response_time = end_time - start_time
                status_msg_done = f"Round {round_num}: {actor_name} responded in {response_time:.2f}s."
                logger.info(status_msg_done)
                self._update_status(status_msg_done)

                if raw_response is not None and raw_response.strip(): clean_response, monologue = self._extract_and_clean(raw_response); return clean_response, monologue
                elif raw_response == "": logger.info(f"Round {round_num}: {actor_name} returned an empty string."); return "", None
                else: raise ValueError(f"Invalid or empty raw response from {actor_name}: '{raw_response}'")
            except Exception as e:
                logger.error(f"Round {round_num}: {actor_name}'s turn failed (Attempt {attempt}): {e}", exc_info=True)
                if attempt == MAX_RETRIES:
                    self._update_status(f"Error: {actor_name} failed after {MAX_RETRIES} attempts.")
                    logger.error(f"Round {round_num}: {actor_name} failed permanently.");
                    return None, None
                
                # MODIFICATION: Report retry status
                retry_msg = f"Round {round_num}: {actor_name} failed. Retrying in {RETRY_DELAY}s..."
                self._update_status(retry_msg)
                logger.info(retry_msg)
                time.sleep(RETRY_DELAY)

        logger.error(f"Round {round_num}: _robust_invoke finished loop unexpectedly for {actor_name}."); return None, None

    def _invoke_moderator_text(self, moderator_chain: Any, previous_speaker_name: str, previous_response: str, target_speaker_name: str, round_num: int) -> Tuple[Optional[str], str, Optional[str]]:
        """Invokes the moderator, parses plain text SUMMARY/GUIDANCE output. Returns (summary, guidance, raw_output)."""
        if moderator_chain is None:
             logger.error(f"Round {round_num}: Cannot invoke Moderator, chain is None for this mode/run.")
             return None, "Error: Moderator chain not available for this mode.", None

        self._update_status(f"Round {round_num}: Moderator is evaluating {previous_speaker_name}'s response...")

        moderator_user_input = (
            f"The previous speaker was {previous_speaker_name}.\n"
            f"Their response was:\n---\n{previous_response}\n---\n"
            f"The next speaker will be {target_speaker_name}.\n\n"
            f"[Instruction Reminder: Follow the required output format precisely - two lines starting with SUMMARY: and GUIDANCE:]"
        )
        moderator_raw_output, _ = self._robust_invoke(
            moderator_chain, {"input": moderator_user_input}, "Moderator", round_num
        )
        if moderator_raw_output is None:
            logger.error(f"Round {round_num}: Moderator failed to respond evaluating {previous_speaker_name}.")
            self._update_status(f"Error: Moderator failed to respond.")
            return None, "Error: Moderator failed to generate response.", None

        summary_str: Optional[str] = None; guidance_str: str = ""
        try:
            lines = [line.strip() for line in moderator_raw_output.strip().splitlines() if line.strip()]
            found_summary = False; found_guidance = False
            for line in lines:
                 line_upper = line.upper()
                 if line_upper.lstrip().startswith("SUMMARY:"): parts = line.split(":", 1); summary_str = parts[1].strip() if len(parts) > 1 else ""; found_summary = True
                 elif line_upper.lstrip().startswith("GUIDANCE:"): parts = line.split(":", 1); guidance_str = parts[1].strip() if len(parts) > 1 else ""; found_guidance = True
            
            if not found_summary and not found_guidance:
                logger.warning(f"Round {round_num}: Moderator output missing 'SUMMARY:' and 'GUIDANCE:'. Using raw output as summary. Raw:\n{moderator_raw_output}")
                summary_str = moderator_raw_output
                guidance_str = "Continue the discussion naturally."
            elif not found_summary:
                logger.warning(f"Round {round_num}: Moderator output missing 'SUMMARY:'. Using 'N/A' as summary. Raw:\n{moderator_raw_output}")
                summary_str = "N/A"
            elif not found_guidance:
                logger.warning(f"Round {round_num}: Moderator output missing 'GUIDANCE:'. Using default guidance. Raw:\n{moderator_raw_output}")
                guidance_str = "Continue the discussion naturally."

            logger.info(f"Round {round_num}: Moderator summary/guidance parsed for {previous_speaker_name}.")
            self._update_status(f"Round {round_num}: Moderator evaluation complete.")
            return summary_str, guidance_str, moderator_raw_output
        except Exception as e:
            logger.error(f"Round {round_num}: Failed to parse Moderator text output: {e}\nRaw:\n{moderator_raw_output}", exc_info=True)
            self._update_status(f"Error: Failed to parse moderator output.")
            return None, "Error: Failed to parse moderator output.", moderator_raw_output

    def _load_chains_for_mode(self, mode: str, run_moderated: bool) -> Tuple[Any, Any, Any, bool]:
        self._update_status(f"Loading AI models for '{mode}' mode...")
        s_chain, c_chain, m_chain = None, None, None
        try:
            s_chain = socrates.get_chain(mode=mode)
            c_chain = confucius.get_chain(mode=mode)
            if run_moderated:
                m_chain = moderator.get_chain(mode=mode)

            if s_chain is None or c_chain is None:
                 raise ImportError(f"Failed to load philosopher chains for mode '{mode}'. Socrates: {s_chain is not None}, Confucius: {c_chain is not None}")
            if run_moderated and m_chain is None:
                 raise ImportError(f"Moderation requested but failed to load moderator chain for mode '{mode}'.")
            logger.info(f"Chains loaded successfully for mode '{mode}'.")
            self._update_status(f"AI models loaded successfully.")
            return s_chain, c_chain, m_chain, True
        except ImportError as e:
            logger.critical(f"Chain loading failed: {e}", exc_info=True)
            self._update_status(f"Error: Failed to load AI models.")
            return s_chain, c_chain, m_chain, False
        except Exception as e:
            logger.critical(f"Unexpected error during chain loading for mode '{mode}': {e}", exc_info=True)
            self._update_status(f"Error: Unexpected error during model loading.")
            return s_chain, c_chain, m_chain, False

    def run_conversation_streamlit(self,
                                  initial_input: str,
                                  num_rounds: int,
                                  starting_philosopher: str = "Socrates",
                                  run_moderated: bool = True,
                                  mode: str = 'philosophy',
                                  moderator_type: str = 'ai'
                                  ) -> Tuple[List[Dict[str, Any]], str, bool, Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        run_mode_desc = ("MODERATED" if run_moderated else "DIRECT") + (f" ({moderator_type} control)" if run_moderated else "")
        logger.info(f"Director starting NEW {run_mode_desc} conversation in '{mode}' mode: Rounds={num_rounds}, Starter='{starting_philosopher}'.")

        s_chain, c_chain, m_chain, chains_loaded_ok = self._load_chains_for_mode(mode, run_moderated)
        if not chains_loaded_ok:
            error_msg = f"Error: Failed to load necessary models/chains for '{mode}' mode."
            return [], error_msg, False, None, None

        if starting_philosopher == "Socrates":
            actor_1_name, actor_1_chain = "Socrates", s_chain
            actor_2_name, actor_2_chain = "Confucius", c_chain
        else:
            actor_1_name, actor_1_chain = "Confucius", c_chain
            actor_2_name, actor_2_chain = "Socrates", s_chain

        current_conversation_state = {
            "messages_log": [],
            "current_round_num": 1,
            "num_rounds_total": num_rounds,
            "actor_1_name": actor_1_name, "actor_1_chain": actor_1_chain,
            "actor_2_name": actor_2_name, "actor_2_chain": actor_2_chain,
            "moderator_chain": m_chain,
            "mode": mode,
            "run_moderated": run_moderated,
            "moderator_type": moderator_type,
            "next_speaker_name": actor_1_name,
            "next_speaker_chain": actor_1_chain,
            "other_speaker_name": actor_2_name,
            "input_for_next_speaker": initial_input,
            "ai_summary_from_last_mod": None,
            "ai_guidance_from_last_mod": None,
            "user_guidance_for_current_turn": None,
        }
        
        if moderator_type != 'user_guidance' or not run_moderated:
            for i in range(num_rounds * 2):
                round_num_for_log = (i // 2) + 1
                
                if i % 2 == 0:
                    current_speaker_name = current_conversation_state["actor_1_name"]
                    current_speaker_chain = current_conversation_state["actor_1_chain"]
                    next_direct_speaker_name = current_conversation_state["actor_2_name"]
                    input_content_for_speaker = current_conversation_state["input_for_next_speaker"]
                else:
                    current_speaker_name = current_conversation_state["actor_2_name"]
                    current_speaker_chain = current_conversation_state["actor_2_chain"]
                    next_direct_speaker_name = current_conversation_state["actor_1_name"]
                    input_content_for_speaker = current_conversation_state["input_for_next_speaker"]

                speaker_response, speaker_monologue = self._robust_invoke(
                    current_speaker_chain, {"input": input_content_for_speaker}, current_speaker_name, round_num_for_log
                )
                if speaker_response is None:
                    error_msg = f"{current_speaker_name} failed in round {round_num_for_log}."
                    current_conversation_state["messages_log"].append({"role": "system", "content": f"Error: {error_msg}", "monologue": None})
                    return current_conversation_state["messages_log"], f"Error: {current_speaker_name} failed.", False, None, None
                current_conversation_state["messages_log"].append({"role": current_speaker_name, "content": speaker_response, "monologue": speaker_monologue})

                if i == (num_rounds * 2) - 1:
                    break

                if run_moderated:
                    summary, guidance, _ = self._invoke_moderator_text(
                        m_chain, current_speaker_name, speaker_response, next_direct_speaker_name, round_num_for_log
                    )
                    if summary is None:
                        error_msg = f"Moderator failed after {current_speaker_name} in round {round_num_for_log}. Details: {guidance}"
                        current_conversation_state["messages_log"].append({"role": "system", "content": f"Error: {error_msg}", "monologue": None})
                        return current_conversation_state["messages_log"], "Error: Moderator failed.", False, None, None
                    
                    mod_output_text = f"MODERATOR CONTEXT (for {next_direct_speaker_name}):\nSUMMARY: {summary or 'N/A'}\nAI Guidance: {guidance or 'None'}"
                    current_conversation_state["messages_log"].append({"role": "system", "content": mod_output_text, "monologue": None})
                    
                    current_conversation_state["input_for_next_speaker"] = (
                        f"{speaker_response}\n\n"
                        f"--- Moderator Context ---\n"
                        f"Summary: {summary}\n"
                        f"Guidance for your response: {guidance or 'Continue the discussion naturally.'}\n"
                        f"--- End Context ---"
                    )
                else:
                    current_conversation_state["input_for_next_speaker"] = speaker_response
            
            final_status_msg = f"{run_mode_desc} conversation ('{mode}' mode) completed after {num_rounds} rounds."
            logger.info(final_status_msg)
            self._update_status("Conversation complete.")
            return current_conversation_state["messages_log"], final_status_msg, True, None, None
        
        else:
            return self._handle_user_guidance_segment(current_conversation_state)


    def resume_conversation_streamlit(self,
                                     resume_state: Dict[str, Any],
                                     user_provided_guidance: str
                                     ) -> Tuple[List[Dict[str, Any]], str, bool, Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        
        logger.info(f"Director RESUMING user-guided conversation. Round {resume_state.get('current_round_num', 'N/A')}, Next Speaker: {resume_state.get('next_speaker_name', 'N/A')}")
        self._update_status(f"Resuming with user guidance for {resume_state.get('next_speaker_name', 'N/A')}...")
        
        resume_state["user_guidance_for_current_turn"] = user_provided_guidance
        
        guidance_to_use = resume_state["ai_guidance_from_last_mod"]
        if user_provided_guidance and user_provided_guidance.strip().lower() != 'auto':
            guidance_to_use = user_provided_guidance
        
        input_for_current_philosopher = (
            f"{resume_state['previous_philosopher_actual_response']}\n\n"
            f"--- Moderator Context ---\n"
            f"Summary: {resume_state['ai_summary_from_last_mod'] or 'N/A'}\n"
            f"Guidance for your response: {guidance_to_use or 'Continue the discussion naturally.'}\n"
            f"--- End Context ---"
        )
        resume_state["input_for_next_speaker"] = input_for_current_philosopher
        
        return self._handle_user_guidance_segment(resume_state)


    def _handle_user_guidance_segment(self,
                                      current_sg_state: Dict[str, Any]
                                      ) -> Tuple[List[Dict[str, Any]], str, bool, Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        
        messages_this_segment: List[Dict[str, Any]] = []

        current_speaker_name = current_sg_state["next_speaker_name"]
        current_speaker_chain = current_sg_state["next_speaker_chain"]
        other_speaker_name = current_sg_state["other_speaker_name"]
        input_content = current_sg_state["input_for_next_speaker"]
        round_num_for_log = current_sg_state["current_round_num"]
        
        speaker_response, speaker_monologue = self._robust_invoke(
            current_speaker_chain, {"input": input_content}, current_speaker_name, round_num_for_log
        )
        if speaker_response is None:
            error_msg = f"{current_speaker_name} failed in round {round_num_for_log}."
            messages_this_segment.append({"role": "system", "content": f"Error: {error_msg}", "monologue": None})
            current_sg_state["messages_log"].append({"role": "system", "content": f"Error: {error_msg}", "monologue": None})
            return messages_this_segment, f"Error: {current_speaker_name} failed.", False, current_sg_state.copy(), None
        
        messages_this_segment.append({"role": current_speaker_name, "content": speaker_response, "monologue": speaker_monologue})
        current_sg_state["messages_log"].append({"role": current_speaker_name, "content": speaker_response, "monologue": speaker_monologue})
        current_sg_state["previous_philosopher_actual_response"] = speaker_response

        is_actor1_turn = (current_speaker_name == current_sg_state["actor_1_name"])
        
        if not is_actor1_turn and round_num_for_log >= current_sg_state["num_rounds_total"]:
            final_status_msg = f"User-guided conversation ('{current_sg_state['mode']}' mode) completed after {current_sg_state['num_rounds_total']} rounds."
            logger.info(final_status_msg)
            self._update_status("Conversation complete.")
            return messages_this_segment, final_status_msg, True, None, None

        ai_summary, ai_guidance, _ = self._invoke_moderator_text(
            current_sg_state["moderator_chain"], current_speaker_name, speaker_response, other_speaker_name, round_num_for_log
        )
        if ai_summary is None:
            error_msg = f"Moderator failed after {current_speaker_name} in round {round_num_for_log}. Details: {ai_guidance}"
            messages_this_segment.append({"role": "system", "content": f"Error: {error_msg}", "monologue": None})
            current_sg_state["messages_log"].append({"role": "system", "content": f"Error: {error_msg}", "monologue": None})
            return messages_this_segment, "Error: Moderator failed.", False, current_sg_state.copy(), None

        mod_output_for_display = f"MODERATOR CONTEXT (AI Summary for your guidance to {other_speaker_name}):\nSUMMARY: {ai_summary or 'N/A'}"
        messages_this_segment.append({"role": "system", "content": mod_output_for_display, "monologue": None})
        current_sg_state["messages_log"].append({"role": "system", "content": mod_output_for_display, "monologue": None})

        current_sg_state["ai_summary_from_last_mod"] = ai_summary
        current_sg_state["ai_guidance_from_last_mod"] = ai_guidance
        current_sg_state["user_guidance_for_current_turn"] = None
        current_sg_state["next_speaker_name"] = other_speaker_name
        current_sg_state["next_speaker_chain"] = current_sg_state["actor_1_chain"] if other_speaker_name == current_sg_state["actor_1_name"] else current_sg_state["actor_2_chain"]
        current_sg_state["other_speaker_name"] = current_speaker_name

        if not is_actor1_turn:
            current_sg_state["current_round_num"] = round_num_for_log + 1
        
        if is_actor1_turn and round_num_for_log >= current_sg_state["num_rounds_total"]:
             pass

        data_for_user_guidance = {
            'ai_summary': ai_summary,
            'next_speaker_name': current_sg_state["next_speaker_name"]
        }
        
        pause_msg = f"Pausing for user guidance for {data_for_user_guidance['next_speaker_name']}..."
        logger.info(pause_msg)
        self._update_status(pause_msg)
        return messages_this_segment, "WAITING_FOR_USER_GUIDANCE", False, current_sg_state.copy(), data_for_user_guidance
