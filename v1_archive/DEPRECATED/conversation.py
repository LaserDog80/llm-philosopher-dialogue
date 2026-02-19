import os
import datetime
import langchain

# Import the chain objects directly from the persona modules
# The loading/creation logic inside them runs automatically upon import
try:
    import socrates
    import confucius
except ImportError as e:
    print(f"Error importing persona modules: {e}")
    print("Ensure socrates.py, confucius.py, and llm_loader.py are present.")
    exit()


# Uncomment the next line for detailed Langchain debugging output
# langchain.debug = True

# --- Configuration ---
NUM_ROUNDS = 3 # Number of back-and-forth exchanges
LOG_DIR = "logs"
OUTPUT_FILENAME = os.path.join(LOG_DIR, "conversation_log.txt")

# --- Validate Chains ---
# Check if the chains were successfully created in the imported modules
if not hasattr(socrates, 'socrates_chain') or socrates.socrates_chain is None:
    print("Fatal Error: Socrates chain failed to initialize during import.")
    exit()
if not hasattr(confucius, 'confucius_chain') or confucius.confucius_chain is None:
    print("Fatal Error: Confucius chain failed to initialize during import.")
    exit()

# Access the chains
socrates_chain = socrates.socrates_chain
confucius_chain = confucius.confucius_chain

print("\nAll persona chains loaded successfully.")


# --- Start Conversation ---
if __name__ == "__main__":
    print("\n=====================================")
    print("    Philosopher Dialogue Manager")
    print("=====================================")
    print(f"Running for {NUM_ROUNDS} rounds.")
    print(f"Output will be saved to: {OUTPUT_FILENAME}")

    initial_input = input("\nEnter the initial question or statement for Socrates: ")

    # Open the output file
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(OUTPUT_FILENAME, 'w', encoding='utf-8') as f:
            # Log header information
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"Conversation Log - {timestamp}\n")
            f.write(f"Rounds: {NUM_ROUNDS}\n")
            f.write("=====================================\n\n")

            # Print and log initial input
            initiator_line = f"YOU (Initiator): {initial_input}\n"
            print("\n-------------------------------------")
            print(initiator_line.strip())
            print("-------------------------------------\n")
            f.write(initiator_line)
            f.write("-------------------------------------\n\n")

            current_turn_input = initial_input

            # --- Conversation Loop ---
            for i in range(NUM_ROUNDS):
                round_header = f"--- ROUND {i+1} ---\n"
                print(round_header.strip())
                f.write(round_header)

                # Socrates' Turn
                try:
                    print("SOCRATES: Thinking...")
                    socrates_response = socrates_chain.invoke({"input": current_turn_input})
                    socrates_line = f"SOCRATES:\n{socrates_response}\n"
                    print(f"\n{socrates_line.strip()}")
                    print("-------------------------------------")
                    f.write(socrates_line)
                    f.write("-------------------------------------\n\n")
                    current_turn_input = socrates_response # Output becomes input for the next

                except Exception as e:
                    error_line = f"\nError during Socrates' turn (Round {i+1}): {e}\n"
                    print(error_line.strip())
                    f.write(error_line)
                    print("Stopping conversation.")
                    break # Exit loop on error

                # Confucius' Turn
                try:
                    print("\nCONFUCIUS: Contemplating...")
                    confucius_response = confucius_chain.invoke({"input": current_turn_input})
                    confucius_line = f"CONFUCIUS:\n{confucius_response}\n"
                    print(f"\n{confucius_line.strip()}")
                    print("-------------------------------------")
                    f.write(confucius_line)
                    f.write("-------------------------------------\n\n")
                    current_turn_input = confucius_response # Output becomes input for the next round

                except Exception as e:
                    error_line = f"\nError during Confucius' turn (Round {i+1}): {e}\n"
                    print(error_line.strip())
                    f.write(error_line)
                    print("Stopping conversation.")
                    break # Exit loop on error

            end_line = f"\n--- Conversation ended after {i+1} round(s) ---\n"
            print(end_line.strip())
            f.write(end_line)

        print(f"\nConversation saved to {OUTPUT_FILENAME}")

    except IOError as e:
        print(f"\nError writing to file {OUTPUT_FILENAME}: {e}")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")


# --- Required: .env, llm_config.json, llm_loader.py, socrates.py, confucius.py ---