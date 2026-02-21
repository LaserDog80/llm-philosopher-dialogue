# direction.py — Conversation orchestrator (Director).

import time
import logging
from typing import List, Tuple, Dict, Any, Optional

from core.persona import create_chain
from core.utils import extract_and_clean

# --- Configuration ---
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

logger = logging.getLogger(__name__)

class Director:
    def __init__(self):
        logger.info("Director initialized (chains will be loaded per conversation mode/resume).")

    def _robust_invoke(self, chain: Any, input_dict: Dict[str, Any], actor_name: str, round_num: int) -> Tuple[Optional[str], Optional[str]]:
        """Invoke a chain with retry logic. Returns (clean_response, monologue)."""
        if chain is None:
            logger.error(f"Round {round_num}: Cannot invoke {actor_name}, chain is None.")
            return None, None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.info(f"Round {round_num}: Requesting {actor_name} (Attempt {attempt}/{MAX_RETRIES})")
                start_time = time.time()
                raw_response_obj = chain.invoke(input_dict)
                raw_response = str(raw_response_obj) if raw_response_obj is not None else None
                elapsed = time.time() - start_time
                logger.info(f"Round {round_num}: {actor_name} responded in {elapsed:.2f}s.")
                if raw_response is not None and raw_response.strip():
                    return extract_and_clean(raw_response)
                elif raw_response == "":
                    return "", None
                else:
                    raise ValueError(f"Empty response from {actor_name}: '{raw_response}'")
            except Exception as e:
                logger.error(f"Round {round_num}: {actor_name} failed (Attempt {attempt}): {e}", exc_info=True)
                if attempt == MAX_RETRIES:
                    logger.error(f"Round {round_num}: {actor_name} failed permanently.")
                    return None, None
                logger.info(f"Retrying in {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)
        return None, None

    def _invoke_moderator_text(self, moderator_chain: Any, previous_speaker_name: str, previous_response: str, target_speaker_name: str, round_num: int) -> Tuple[Optional[str], str, Optional[str]]:
        """Invokes the moderator, parses plain text SUMMARY/GUIDANCE output. Returns (summary, guidance, raw_output)."""
        if moderator_chain is None:
             logger.error(f"Round {round_num}: Cannot invoke Moderator, chain is None for this mode/run.")
             return None, "Error: Moderator chain not available for this mode.", None

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
            return None, "Error: Moderator failed to generate response.", None

        summary_str: Optional[str] = None; guidance_str: str = ""
        try:
            lines = [line.strip() for line in moderator_raw_output.strip().splitlines() if line.strip()]
            found_summary = False; found_guidance = False
            for line in lines:
                 line_upper = line.upper()
                 if line_upper.lstrip().startswith("SUMMARY:"): parts = line.split(":", 1); summary_str = parts[1].strip() if len(parts) > 1 else ""; found_summary = True
                 elif line_upper.lstrip().startswith("GUIDANCE:"): parts = line.split(":", 1); guidance_str = parts[1].strip() if len(parts) > 1 else ""; found_guidance = True
            
            if not found_summary and not found_guidance: # Neither found, treat whole output as summary (best guess)
                logger.warning(f"Round {round_num}: Moderator output missing 'SUMMARY:' and 'GUIDANCE:'. Using raw output as summary. Raw:\n{moderator_raw_output}")
                summary_str = moderator_raw_output
                guidance_str = "Continue the discussion naturally." # Default guidance
            elif not found_summary: # Guidance found, but no summary
                logger.warning(f"Round {round_num}: Moderator output missing 'SUMMARY:'. Using 'N/A' as summary. Raw:\n{moderator_raw_output}")
                summary_str = "N/A" # Or perhaps an error message, or None to signal issue
            elif not found_guidance: # Summary found, but no guidance
                logger.warning(f"Round {round_num}: Moderator output missing 'GUIDANCE:'. Using default guidance. Raw:\n{moderator_raw_output}")
                guidance_str = "Continue the discussion naturally."

            logger.info(f"Round {round_num}: Moderator summary/guidance parsed for {previous_speaker_name}.")
            return summary_str, guidance_str, moderator_raw_output
        except Exception as e:
            logger.error(f"Round {round_num}: Failed to parse Moderator text output: {e}\nRaw:\n{moderator_raw_output}", exc_info=True)
            return None, "Error: Failed to parse moderator output.", moderator_raw_output

    def _load_chains_for_mode(self, mode: str, run_moderated: bool) -> Tuple[Any, Any, Any, bool]:
        """Load philosopher and moderator chains via the unified factory."""
        s_chain, c_chain, m_chain = None, None, None
        try:
            s_chain = create_chain("socrates", mode=mode)
            c_chain = create_chain("confucius", mode=mode)
            if run_moderated:
                m_chain = create_chain("moderator", mode=mode)

            if s_chain is None or c_chain is None:
                raise ImportError(f"Philosopher chain load failed for mode '{mode}'")
            if run_moderated and m_chain is None:
                raise ImportError(f"Moderator chain load failed for mode '{mode}'")
            logger.info(f"Chains loaded for mode '{mode}'.")
            return s_chain, c_chain, m_chain, True
        except Exception as e:
            logger.critical(f"Chain loading error: {e}", exc_info=True)
            return s_chain, c_chain, m_chain, False

    def run_conversation_streamlit(self,
                                  initial_input: str,
                                  num_rounds: int,
                                  starting_philosopher: str = "Socrates",
                                  run_moderated: bool = True,
                                  mode: str = 'philosophy',
                                  moderator_type: str = 'ai' # 'ai' or 'user_guidance'
                                  ) -> Tuple[List[Dict[str, Any]], str, bool, Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """
        Manages the conversation.
        If moderator_type is 'ai' or run_moderated is False, it completes all rounds.
        If moderator_type is 'user_guidance', it may pause after a moderator summary,
        returning a state to be resumed.
        Returns: (generated_messages, final_status, success, director_resume_state, data_for_user_guidance)
        """
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

        # This is the state that will be passed around and updated.
        # For 'user_guidance' mode, this entire dict might be returned to app.py
        # For 'ai' mode, this is used internally in the loop.
        current_conversation_state = {
            "messages_log": [], # Accumulates all messages for the final return
            "current_round_num": 1,
            "num_rounds_total": num_rounds,
            "actor_1_name": actor_1_name, "actor_1_chain": actor_1_chain,
            "actor_2_name": actor_2_name, "actor_2_chain": actor_2_chain,
            "moderator_chain": m_chain,
            "mode": mode,
            "run_moderated": run_moderated,
            "moderator_type": moderator_type,
            # For the very first turn of Actor 1
            "next_speaker_name": actor_1_name,
            "next_speaker_chain": actor_1_chain,
            "other_speaker_name": actor_2_name,
            "input_for_next_speaker": initial_input,
            "ai_summary_from_last_mod": None, # From AI mod (used if user types 'auto')
            "ai_guidance_from_last_mod": None, # From AI mod (used if user types 'auto')
            "user_guidance_for_current_turn": None, # Set by resume_conversation_streamlit
        }

        # If not 'user_guidance', loop through all rounds.
        # If 'user_guidance', this loop will be effectively managed by app.py via run/resume.
        if moderator_type != 'user_guidance' or not run_moderated:
            for i in range(num_rounds * 2): # Each round has 2 philosopher turns
                round_num_for_log = (i // 2) + 1
                
                # Determine current speaker based on iteration (i)
                if i % 2 == 0: # Actor 1's turn (or first turn of the pair)
                    current_speaker_name = current_conversation_state["actor_1_name"]
                    current_speaker_chain = current_conversation_state["actor_1_chain"]
                    next_direct_speaker_name = current_conversation_state["actor_2_name"] # Who the moderator will target
                    input_content_for_speaker = current_conversation_state["input_for_next_speaker"]
                else: # Actor 2's turn
                    current_speaker_name = current_conversation_state["actor_2_name"]
                    current_speaker_chain = current_conversation_state["actor_2_chain"]
                    next_direct_speaker_name = current_conversation_state["actor_1_name"]
                    input_content_for_speaker = current_conversation_state["input_for_next_speaker"]

                logger.info(f"AI/Direct Mode - Round {round_num_for_log}: {current_speaker_name}'s turn.")
                speaker_response, speaker_monologue = self._robust_invoke(
                    current_speaker_chain, {"input": input_content_for_speaker}, current_speaker_name, round_num_for_log
                )
                if speaker_response is None:
                    error_msg = f"{current_speaker_name} failed in round {round_num_for_log}."
                    current_conversation_state["messages_log"].append({"role": "system", "content": f"Error: {error_msg}", "monologue": None})
                    return current_conversation_state["messages_log"], f"Error: {current_speaker_name} failed.", False, None, None
                current_conversation_state["messages_log"].append({"role": current_speaker_name, "content": speaker_response, "monologue": speaker_monologue})

                # If this was the last turn of the last round, break
                if i == (num_rounds * 2) - 1:
                    break

                # Moderation or prepare direct input for next speaker
                if run_moderated:
                    summary, guidance, _ = self._invoke_moderator_text(
                        m_chain, current_speaker_name, speaker_response, next_direct_speaker_name, round_num_for_log
                    )
                    if summary is None: # Critical moderator failure
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
                else: # Direct dialogue
                    current_conversation_state["input_for_next_speaker"] = speaker_response
            
            # AI/Direct conversation completed all rounds
            final_status_msg = f"{run_mode_desc} conversation ('{mode}' mode) completed after {num_rounds} rounds."
            logger.info(final_status_msg)
            return current_conversation_state["messages_log"], final_status_msg, True, None, None
        
        else: # moderator_type == 'user_guidance' and run_moderated is True
            # This path is for the first segment of a user-guided conversation.
            # It will run one philosopher turn, then one AI moderator summary, then pause.
            return self._handle_user_guidance_segment(current_conversation_state)


    def resume_conversation_streamlit(self,
                                     resume_state: Dict[str, Any],
                                     user_provided_guidance: str
                                     ) -> Tuple[List[Dict[str, Any]], str, bool, Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """
        Resumes a user-guided conversation.
        resume_state is the state returned by a previous call that paused.
        user_provided_guidance is the text from user, or "auto".
        """
        logger.info(f"Director RESUMING user-guided conversation. Round {resume_state.get('current_round_num', 'N/A')}, Next Speaker: {resume_state.get('next_speaker_name', 'N/A')}")
        
        # Update resume_state with user's choice for guidance for *this specific turn*
        resume_state["user_guidance_for_current_turn"] = user_provided_guidance
        
        # The input for the philosopher was already partially prepared by the AI moderator summary.
        # Now we incorporate the user's guidance (or AI's if 'auto').
        
        guidance_to_use = resume_state["ai_guidance_from_last_mod"] # Default if user types 'auto'
        if user_provided_guidance and user_provided_guidance.strip().lower() != 'auto':
            guidance_to_use = user_provided_guidance
        
        # `last_speaker_response_before_this_guidance` was stored in `input_for_next_speaker`
        # when the moderator first summarized.
        # No, this is simpler: `ai_summary_from_last_mod` has the summary.
        # `last_speaker_response` in the resume_state is the actual text of the philosopher *before* the current user guidance.
        
        # The input_for_next_speaker should be the response of the philosopher *whose turn it is now*.
        # This means we need the previous philosopher's response from the state.
        # `previous_philosopher_actual_response` should be part of the resume_state.
        
        # Let's reconstruct the input for the philosopher who is about to speak:
        input_for_current_philosopher = (
            f"{resume_state['previous_philosopher_actual_response']}\n\n" # This needs to be in resume_state
            f"--- Moderator Context ---\n"
            f"Summary: {resume_state['ai_summary_from_last_mod'] or 'N/A'}\n"
            f"Guidance for your response: {guidance_to_use or 'Continue the discussion naturally.'}\n"
            f"--- End Context ---"
        )
        resume_state["input_for_next_speaker"] = input_for_current_philosopher
        
        # Now, proceed with this segment (philosopher speaks, AI summarizes, maybe pause again)
        return self._handle_user_guidance_segment(resume_state)


    def _handle_user_guidance_segment(self,
                                      current_sg_state: Dict[str, Any]
                                      ) -> Tuple[List[Dict[str, Any]], str, bool, Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """
        Handles one segment of a user-guided conversation:
        1. Current philosopher speaks.
        2. AI Moderator summarizes.
        3. If conversation continues, prepares to pause for next user guidance.
        Returns messages *from this segment only*, status, success, and potentially new resume_state.
        """
        messages_this_segment: List[Dict[str, Any]] = []

        current_speaker_name = current_sg_state["next_speaker_name"]
        current_speaker_chain = current_sg_state["next_speaker_chain"]
        other_speaker_name = current_sg_state["other_speaker_name"] # Who moderator targets next
        input_content = current_sg_state["input_for_next_speaker"]
        round_num_for_log = current_sg_state["current_round_num"]

        # 1. Current Philosopher's Turn
        logger.info(f"User-Guidance Mode - Round {round_num_for_log}: {current_speaker_name}'s turn.")
        speaker_response, speaker_monologue = self._robust_invoke(
            current_speaker_chain, {"input": input_content}, current_speaker_name, round_num_for_log
        )
        if speaker_response is None:
            error_msg = f"{current_speaker_name} failed in round {round_num_for_log}."
            messages_this_segment.append({"role": "system", "content": f"Error: {error_msg}", "monologue": None})
            # Add to main log as well if this is how errors are handled
            current_sg_state["messages_log"].append({"role": "system", "content": f"Error: {error_msg}", "monologue": None})
            return messages_this_segment, f"Error: {current_speaker_name} failed.", False, current_sg_state.copy(), None # Return full state on error
        
        messages_this_segment.append({"role": current_speaker_name, "content": speaker_response, "monologue": speaker_monologue})
        current_sg_state["messages_log"].append({"role": current_speaker_name, "content": speaker_response, "monologue": speaker_monologue})
        current_sg_state["previous_philosopher_actual_response"] = speaker_response # Store for next resume

        # Check if this philosopher's turn completes the required number of rounds/turns
        # A full round completes after actor 2 speaks.
        # If actor 1 just spoke, it's turn 1 of a round. If actor 2, it's turn 2.
        # This needs careful tracking of whose turn it was vs actor_1_name/actor_2_name.
        
        is_actor1_turn = (current_speaker_name == current_sg_state["actor_1_name"])
        
        # End condition check: if current speaker was actor_2 AND it's the last round
        if not is_actor1_turn and round_num_for_log >= current_sg_state["num_rounds_total"]:
            final_status_msg = f"User-guided conversation ('{current_sg_state['mode']}' mode) completed after {current_sg_state['num_rounds_total']} rounds."
            logger.info(final_status_msg)
            return messages_this_segment, final_status_msg, True, None, None # Conversation done

        # 2. AI Moderator Summarizes (for the *next* philosopher)
        ai_summary, ai_guidance, _ = self._invoke_moderator_text(
            current_sg_state["moderator_chain"], current_speaker_name, speaker_response, other_speaker_name, round_num_for_log
        )
        if ai_summary is None: # Critical moderator failure
            error_msg = f"Moderator failed after {current_speaker_name} in round {round_num_for_log}. Details: {ai_guidance}"
            messages_this_segment.append({"role": "system", "content": f"Error: {error_msg}", "monologue": None})
            current_sg_state["messages_log"].append({"role": "system", "content": f"Error: {error_msg}", "monologue": None})
            return messages_this_segment, "Error: Moderator failed.", False, current_sg_state.copy(), None

        # Log only the summary part for the user to see before they provide guidance
        mod_output_for_display = f"MODERATOR CONTEXT (AI Summary for your guidance to {other_speaker_name}):\nSUMMARY: {ai_summary or 'N/A'}"
        messages_this_segment.append({"role": "system", "content": mod_output_for_display, "monologue": None})
        current_sg_state["messages_log"].append({"role": "system", "content": mod_output_for_display, "monologue": None})

        # Prepare state for the next segment (which will be PAUSED, waiting for user guidance)
        current_sg_state["ai_summary_from_last_mod"] = ai_summary
        current_sg_state["ai_guidance_from_last_mod"] = ai_guidance # Store AI's original guidance for 'auto' option
        current_sg_state["user_guidance_for_current_turn"] = None # Clear for next turn

        # Swap speakers for the *next* turn
        current_sg_state["next_speaker_name"] = other_speaker_name
        current_sg_state["next_speaker_chain"] = current_sg_state["actor_1_chain"] if other_speaker_name == current_sg_state["actor_1_name"] else current_sg_state["actor_2_chain"]
        current_sg_state["other_speaker_name"] = current_speaker_name

        # Advance round number if Actor 2 just finished
        if not is_actor1_turn: # current_speaker was Actor 2
            current_sg_state["current_round_num"] = round_num_for_log + 1
        
        # If we are about to ask for guidance for a turn that exceeds total_rounds, then the conversation is complete.
        # This can happen if actor 1 just spoke in the final round, and we ask for guidance for actor 2,
        # OR if actor 2 just spoke in final round (already handled above).

        # If actor 1 just spoke in the final round:
        if is_actor1_turn and round_num_for_log >= current_sg_state["num_rounds_total"]:
             # We *could* ask for guidance for Actor 2's final turn.
             # The logic above for `if not is_actor1_turn and round_num_for_log >= ...` handles completion *after* Actor 2.
             # This means if it's Actor 1's turn in the last round, we *do* ask for guidance for Actor 2.
             pass # Continue to ask for guidance.

        data_for_user_guidance = {
            'ai_summary': ai_summary,
            'next_speaker_name': current_sg_state["next_speaker_name"] # This is now the 'other_speaker_name' from before swap
        }
        logger.info(f"Pausing for user guidance. Next speaker: {data_for_user_guidance['next_speaker_name']}, Upcoming Round: {current_sg_state['current_round_num']}")
        return messages_this_segment, "WAITING_FOR_USER_GUIDANCE", False, current_sg_state.copy(), data_for_user_guidance