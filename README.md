# LLM-Philosophers

A plain-language guide to installing and running the app -- no programming background required.

---

## What Is This App?

LLM-Philosophers is a web application that stages conversations between two AI-powered versions of famous philosophers -- Socrates and Confucius. You pick a topic, and the two philosophers discuss it in real time while an AI moderator keeps the conversation on track. You can also step in and guide the conversation yourself.

---

## What You Will Need

Before you begin, make sure you have the following:

1. **A computer** running Windows, macOS, or Linux.
2. **Python 3.11 or newer** installed. If you are not sure whether Python is installed, open a terminal (or Command Prompt on Windows) and type `python --version`. You should see something like `Python 3.11.x`. If not, download Python from [python.org](https://www.python.org/downloads/) and follow the installer instructions.
3. **A Nebius API key**. The philosophers are powered by large language models hosted on Nebius. You will need to sign up for an account at Nebius and obtain an API key and API base URL from their dashboard.
4. **A password** you will use to log in to the app. You get to choose this yourself during setup.

---

## Step-by-Step Installation

### 1. Download the Project

If someone sent you this project as a ZIP file, unzip it to a folder you can easily find (for example, your Desktop or Documents folder).

If you are comfortable with Git, you can clone the repository instead:

```
git clone <repository-url>
```

### 2. Open a Terminal in the Project Folder

- **Windows**: Open File Explorer, navigate to the project folder, click the address bar, type `cmd`, and press Enter.
- **macOS**: Open Terminal (search for it in Spotlight), then type `cd ` followed by the path to the folder. For example: `cd ~/Desktop/llm-philosopher-dialogue`
- **Linux**: Open your terminal and navigate to the folder: `cd ~/llm-philosopher-dialogue`

You should now be inside the folder that contains files like `app.py` and `requirements.txt`.

### 3. Create a Virtual Environment (Recommended)

A virtual environment keeps this project's software separate from the rest of your computer. This step is optional but strongly recommended.

```
python -m venv venv
```

Then activate it:

- **Windows**: `venv\Scripts\activate`
- **macOS / Linux**: `source venv/bin/activate`

You should see `(venv)` appear at the beginning of your terminal prompt.

### 4. Install the Required Software

With your terminal open in the project folder (and your virtual environment activated, if you created one), run:

```
pip install -r requirements.txt
```

This downloads and installs the four software packages the app depends on. It may take a minute or two.

### 5. Set Up Your Credentials

The app needs to know your Nebius API key and your chosen password. Create a new file in the project folder called `.env` (note the dot at the beginning). Open it in any text editor and add the following three lines, replacing the placeholder values with your real information:

```
NEBIUS_API_KEY=paste-your-nebius-api-key-here
NEBIUS_API_BASE=paste-your-nebius-api-base-url-here
APP_PASSWORD=choose-any-password-you-like
```

Save and close the file. The app reads these values automatically on startup.

> **Important:** The `.env` file contains sensitive information. Do not share it or upload it to the internet. The project is already configured to keep this file out of version control.

---

## Running the App

From your terminal (still in the project folder, with the virtual environment active), run:

```
streamlit run app.py
```

After a moment, you should see a message like:

```
You can now view your Streamlit app in your browser.
Local URL: http://localhost:8501
```

Your web browser should open automatically. If it does not, open your browser and go to **http://localhost:8501**.

### Logging In

The first screen you see is a password prompt. Enter the password you chose in your `.env` file and click **Login**.

---

## Using the App

Once you are logged in, you will see the main conversation screen with a sidebar on the left. Here is what each option does:

### Sidebar Controls

- **Conversation Mode** -- Choose between *Philosophy* (the philosophers discuss ideas and arguments) and *Bio* (they share stories from their lives and times).
- **Moderator Control** -- Choose who guides the conversation:
  - *AI Moderator*: The app automatically steers the discussion between turns.
  - *User as Moderator (Guidance)*: The conversation pauses after each turn so you can type guidance for the next philosopher.
  - *Bypass Moderator*: The philosophers talk freely with no moderation.
- **Starting Philosopher** -- Pick whether Socrates or Confucius speaks first.
- **Number of Rounds** -- How many back-and-forth exchanges the conversation should last. Each round consists of one turn from each philosopher.

### Starting a Conversation

Type a topic or question into the chat box at the bottom of the screen and press Enter. For example:

- "What is the purpose of education?"
- "Is it more important to be just or to be kind?"
- "Tell me about your most influential teacher."

The philosophers will begin their dialogue. You can watch it unfold in the chat window.

### Guiding the Conversation (User as Moderator)

If you selected *User as Moderator (Guidance)*, the conversation will pause after each philosopher's turn. You will see a summary of what was just said, and a text box where you can provide direction for the next speaker. For example, you might type:

- "Ask Socrates to challenge that point."
- "Shift the topic toward the role of virtue in governance."

If you prefer to let the AI decide, type **auto** and it will generate its own guidance.

### After the Conversation

When all rounds are complete:

- You can **download** a text log of the entire conversation using the download button.
- You can choose the **Translated Text** output style to convert the formal philosophical dialogue into casual, everyday language.

### Other Pages

The app has two additional pages accessible from the sidebar navigation:

- **Direct Chat** -- A testing page where you can talk one-on-one with a single philosopher. Useful for exploring how each persona responds.
- **Settings** -- Lets you customize the system prompts that define each philosopher's personality and instructions. Changes apply for the current session only.

---

## Stopping the App

To stop the app, go back to your terminal and press `Ctrl+C`. This shuts down the web server. You can restart it anytime by running `streamlit run app.py` again.

To deactivate your virtual environment when you are done:

```
deactivate
```

---

## Troubleshooting

| Problem | What to Try |
|---|---|
| `python: command not found` | Try `python3` instead. On some systems, Python 3 uses the `python3` command. |
| `pip: command not found` | Try `pip3` instead, or `python -m pip install -r requirements.txt`. |
| The browser shows a connection error | Make sure the terminal is still running `streamlit run app.py`. Check that you are visiting `http://localhost:8501`. |
| "Application Security Error: Password configuration is missing" | Your `.env` file is missing or does not contain `APP_PASSWORD`. Double-check the file exists in the project folder and has the right contents. |
| The philosophers' responses seem cut off or the moderator says "Continue the discussion naturally" every time | This is a known limitation of the current token budget settings. See `nextsteps.md` for planned improvements. |
| The conversation feels repetitive across rounds | Each philosopher currently only sees the most recent turn, not the full conversation history. Conversation memory is a top priority for the next update. |

---

## Quick Reference

| Action | Command |
|---|---|
| Install dependencies | `pip install -r requirements.txt` |
| Start the app | `streamlit run app.py` |
| Open in browser | `http://localhost:8501` |
| Stop the app | `Ctrl+C` in the terminal |
| Deactivate virtual environment | `deactivate` |
