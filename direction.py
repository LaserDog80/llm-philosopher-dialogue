# direction.py — Conversation orchestrator (Director).

import time
import logging
from typing import List, Tuple, Dict, Any, Optional

from core.persona import create_chain
from core.utils import extract_and_clean
from core.memory import ConversationMemory
from core.registry import get_philosopher_ids, get_philosopher

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

    def _invoke_moderator_text(self, moderator_chain: Any, previous_speaker_name: str,
                               previous_response: str, target_speaker_name: str,
                               round_num: int, conversation_context: str = ""
                               ) -> Tuple[Optional[str], str, Optional[str]]:
        """Invokes the moderator, parses plain text SUMMARY/GUIDANCE output.
        Returns (summary, guidance, raw_output)."""
        if moderator_chain is None:
            logger.error(f"Round {round_num}: Cannot invoke Moderator, chain is None for this mode/run.")
            return None, "Error: Moderator chain not available for this mode.", None

        context_section = ""
        if conversation_context:
            context_section = f"Conversation context (recent turns):\n{conversation_context}\n\n"

        moderator_user_input = (
            f"{context_section}"
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

        summary_str: Optional[str] = None
        guidance_str: str = ""
        try:
            lines = [line.strip() for line in moderator_raw_output.strip().splitlines() if line.strip()]
            found_summary = False
            found_guidance = False
            for line in lines:
                line_upper = line.upper()
                if line_upper.lstrip().startswith("SUMMARY:"):
                    parts = line.split(":", 1)
                    summary_str = parts[1].strip() if len(parts) > 1 else ""
                    found_summary = True
                elif line_upper.lstrip().startswith("GUIDANCE:"):
                    parts = line.split(":", 1)
                    guidance_str = parts[1].strip() if len(parts) > 1 else ""
                    found_guidance = True

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
            return summary_str, guidance_str, moderator_raw_output
        except Exception as e:
            logger.error(f"Round {round_num}: Failed to parse Moderator text output: {e}\nRaw:\n{moderator_raw_output}", exc_info=True)
            return None, "Error: Failed to parse moderator output.", moderator_raw_output

    def _load_chains_for_mode(self, mode: str, run_moderated: bool) -> Tuple[Dict[str, Any], Any, bool]:
        """Load philosopher and moderator chains via the registry + factory.

        Returns (philosopher_chains_dict, moderator_chain, success).
        ``philosopher_chains_dict`` maps philosopher id -> chain.
        """
        phil_chains: Dict[str, Any] = {}
        m_chain = None
        try:
            for pid in get_philosopher_ids():
                chain = create_chain(pid, mode=mode)
                if chain is None:
                    raise ImportError(f"Chain load failed for philosopher '{pid}' in mode '{mode}'")
                phil_chains[pid] = chain

            if run_moderated:
                m_chain = create_chain("moderator", mode=mode)
                if m_chain is None:
                    raise ImportError(f"Moderator chain load failed for mode '{mode}'")

            logger.info(f"Chains loaded for mode '{mode}': {list(phil_chains.keys())}.")
            return phil_chains, m_chain, True
        except Exception as e:
            logger.critical(f"Chain loading error: {e}", exc_info=True)
            return phil_chains, m_chain, False

    def run_conversation_streamlit(self,
                                   initial_input: str,
                                   num_rounds: int,
                                   starting_philosopher: str = "Socrates",
                                   run_moderated: bool = True,
                                   mode: str = 'philosophy',
                                   moderator_type: str = 'ai'
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

        phil_chains, m_chain, chains_loaded_ok = self._load_chains_for_mode(mode, run_moderated)
        if not chains_loaded_ok:
            error_msg = f"Error: Failed to load necessary models/chains for '{mode}' mode."
            return [], error_msg, False, None, None

        # Map display names to chains via the registry
        phil_ids = get_philosopher_ids()
        id_to_name = {}
        for pid in phil_ids:
            pcfg = get_philosopher(pid)
            if pcfg:
                id_to_name[pid] = pcfg.display_name

        # Determine actor order based on starting_philosopher
        starter_id = None
        for pid, dname in id_to_name.items():
            if dname == starting_philosopher:
                starter_id = pid
                break
        if starter_id is None:
            starter_id = phil_ids[0]

        other_id = [pid for pid in phil_ids if pid != starter_id][0]
        actor_1_name = id_to_name[starter_id]
        actor_1_chain = phil_chains[starter_id]
        actor_2_name = id_to_name[other_id]
        actor_2_chain = phil_chains[other_id]

        # Create conversation memory
        memory = ConversationMemory()
        # Record the user's initial prompt in memory
        memory.add_turn("User", initial_input, 0)

        # Internal state dict — chain objects stay here (never serialized)
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
            "memory": memory,
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

                logger.info(f"AI/Direct Mode - Round {round_num_for_log}: {current_speaker_name}'s turn.")

                # Build input with conversation memory
                history = memory.get_history_for_chain()
                speaker_response, speaker_monologue = self._robust_invoke(
                    current_speaker_chain,
                    {"input": input_content_for_speaker, "chat_history": history},
                    current_speaker_name, round_num_for_log
                )
                if speaker_response is None:
                    error_msg = f"{current_speaker_name} failed in round {round_num_for_log}."
                    current_conversation_state["messages_log"].append({"role": "system", "content": f"Error: {error_msg}", "monologue": None})
                    return current_conversation_state["messages_log"], f"Error: {current_speaker_name} failed.", False, None, None

                current_conversation_state["messages_log"].append({"role": current_speaker_name, "content": speaker_response, "monologue": speaker_monologue})
                # Record in memory
                memory.add_turn(current_speaker_name, speaker_response, round_num_for_log)

                if i == (num_rounds * 2) - 1:
                    break

                if run_moderated:
                    conversation_context = memory.get_context_string()
                    summary, guidance, _ = self._invoke_moderator_text(
                        m_chain, current_speaker_name, speaker_response,
                        next_direct_speaker_name, round_num_for_log,
                        conversation_context=conversation_context
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
            return current_conversation_state["messages_log"], final_status_msg, True, None, None

        else:
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

        # Recreate chains if missing (they are not serialized)
        if resume_state.get("actor_1_chain") is None:
            mode = resume_state.get("mode", "philosophy")
            run_moderated = resume_state.get("run_moderated", True)
            phil_chains, m_chain, ok = self._load_chains_for_mode(mode, run_moderated)
            if not ok:
                return [], "Error: Failed to reload chains on resume.", False, None, None

            # Map actor names back to chain IDs
            for pid, chain in phil_chains.items():
                pcfg = get_philosopher(pid)
                if pcfg and pcfg.display_name == resume_state["actor_1_name"]:
                    resume_state["actor_1_chain"] = chain
                elif pcfg and pcfg.display_name == resume_state["actor_2_name"]:
                    resume_state["actor_2_chain"] = chain
            resume_state["moderator_chain"] = m_chain
            # Restore correct next_speaker_chain
            if resume_state["next_speaker_name"] == resume_state["actor_1_name"]:
                resume_state["next_speaker_chain"] = resume_state["actor_1_chain"]
            else:
                resume_state["next_speaker_chain"] = resume_state["actor_2_chain"]

        # Restore memory if serialized
        if "memory" not in resume_state and "memory_turns" in resume_state:
            from core.memory import ConversationMemory
            resume_state["memory"] = ConversationMemory.from_list(resume_state["memory_turns"])

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
        """
        Handles one segment of a user-guided conversation:
        1. Current philosopher speaks.
        2. AI Moderator summarizes.
        3. If conversation continues, prepares to pause for next user guidance.
        Returns messages *from this segment only*, status, success, and potentially new resume_state.
        """
        messages_this_segment: List[Dict[str, Any]] = []
        memory: ConversationMemory = current_sg_state["memory"]

        current_speaker_name = current_sg_state["next_speaker_name"]
        current_speaker_chain = current_sg_state["next_speaker_chain"]
        other_speaker_name = current_sg_state["other_speaker_name"]
        input_content = current_sg_state["input_for_next_speaker"]
        round_num_for_log = current_sg_state["current_round_num"]

        # 1. Current Philosopher's Turn
        logger.info(f"User-Guidance Mode - Round {round_num_for_log}: {current_speaker_name}'s turn.")
        history = memory.get_history_for_chain()
        speaker_response, speaker_monologue = self._robust_invoke(
            current_speaker_chain,
            {"input": input_content, "chat_history": history},
            current_speaker_name, round_num_for_log
        )
        if speaker_response is None:
            error_msg = f"{current_speaker_name} failed in round {round_num_for_log}."
            messages_this_segment.append({"role": "system", "content": f"Error: {error_msg}", "monologue": None})
            current_sg_state["messages_log"].append({"role": "system", "content": f"Error: {error_msg}", "monologue": None})
            return messages_this_segment, f"Error: {current_speaker_name} failed.", False, self._serialize_state(current_sg_state), None

        messages_this_segment.append({"role": current_speaker_name, "content": speaker_response, "monologue": speaker_monologue})
        current_sg_state["messages_log"].append({"role": current_speaker_name, "content": speaker_response, "monologue": speaker_monologue})
        current_sg_state["previous_philosopher_actual_response"] = speaker_response
        memory.add_turn(current_speaker_name, speaker_response, round_num_for_log)

        is_actor1_turn = (current_speaker_name == current_sg_state["actor_1_name"])

        if not is_actor1_turn and round_num_for_log >= current_sg_state["num_rounds_total"]:
            final_status_msg = f"User-guided conversation ('{current_sg_state['mode']}' mode) completed after {current_sg_state['num_rounds_total']} rounds."
            logger.info(final_status_msg)
            return messages_this_segment, final_status_msg, True, None, None

        # 2. AI Moderator Summarizes (for the *next* philosopher)
        conversation_context = memory.get_context_string()
        ai_summary, ai_guidance, _ = self._invoke_moderator_text(
            current_sg_state["moderator_chain"], current_speaker_name, speaker_response,
            other_speaker_name, round_num_for_log,
            conversation_context=conversation_context
        )
        if ai_summary is None:
            error_msg = f"Moderator failed after {current_speaker_name} in round {round_num_for_log}. Details: {ai_guidance}"
            messages_this_segment.append({"role": "system", "content": f"Error: {error_msg}", "monologue": None})
            current_sg_state["messages_log"].append({"role": "system", "content": f"Error: {error_msg}", "monologue": None})
            return messages_this_segment, "Error: Moderator failed.", False, self._serialize_state(current_sg_state), None

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
            pass  # Continue to ask for guidance for Actor 2's final turn.

        data_for_user_guidance = {
            'ai_summary': ai_summary,
            'next_speaker_name': current_sg_state["next_speaker_name"]
        }
        logger.info(f"Pausing for user guidance. Next speaker: {data_for_user_guidance['next_speaker_name']}, Upcoming Round: {current_sg_state['current_round_num']}")
        return messages_this_segment, "WAITING_FOR_USER_GUIDANCE", False, self._serialize_state(current_sg_state), data_for_user_guidance

    def _serialize_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Create a copy of state safe for session storage.
        Strips chain objects and serializes memory."""
        serialized = {}
        for key, value in state.items():
            # Skip chain objects and memory (serialize memory separately)
            if key in ("actor_1_chain", "actor_2_chain", "moderator_chain", "next_speaker_chain"):
                continue
            if key == "memory":
                serialized["memory_turns"] = value.to_list()
                continue
            serialized[key] = value
        return serialized
