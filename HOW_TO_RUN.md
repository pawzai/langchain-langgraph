# How to Run the Demo — Complete Beginner's Guide

Written for someone who has never used Python. Every step is spelled out. Nothing here assumes
you remember anything from yesterday.

Your project folder is:

```
D:\AI\Projects\langchain-langgraph
```

---

## The 30-second version

1. Open the folder `D:\AI\Projects\langchain-langgraph` in File Explorer.
2. Double-click **`start-demo.bat`**.
3. Wait for a browser tab to open at **http://localhost:8501**.
4. Leave the black window open while you demo.

If that worked, skip to [What to click in the demo](#what-to-click-in-the-demo). If anything went
wrong, read on — the long version explains each step and what to do when it misbehaves.

---

## Before you start: is Ollama running?

Ollama is the program that runs the AI models on your own computer. **Nothing works without it.**
It normally starts by itself when Windows starts, and shows a small llama icon in your system
tray (bottom-right of the screen, sometimes hidden behind the `^` arrow).

To be sure:

1. Click the Windows **Start** button.
2. Type `Ollama`.
3. Press **Enter**.
4. Wait about 10 seconds.

Starting it twice does no harm — if it was already running, nothing happens. You do not need to
keep any window open for Ollama; it runs in the background.

---

## The long version, step by step

### Step 1 — Open PowerShell in the right folder

This is the single most common thing beginners get wrong. Commands only work if the terminal is
"pointing at" your project folder.

1. Open **File Explorer**.
2. Navigate to `D:\AI\Projects\langchain-langgraph`.
3. Click once in the **address bar** at the top (where the folder path is shown).
4. Type `powershell` and press **Enter**.

A dark blue window opens. The text at the left of the blinking cursor — the *prompt* — should end
with your project folder:

```
PS D:\AI\Projects\langchain-langgraph>
```

If it shows something else, such as `PS C:\Users\Admin>`, you are in the wrong place. Type this
and press Enter:

```powershell
cd D:\AI\Projects\langchain-langgraph
```

> **What is PowerShell?** A window where you type commands instead of clicking buttons. You type
> one line, press Enter, and it does something. That is all.

### Step 2 — Understand the one weird-looking command

You will type commands that start with `.\.venv\Scripts\python.exe`. That looks strange, so here
is what it means:

- `.venv` is a folder inside your project holding a **private copy of Python** with exactly the
  right add-on packages for this project. It keeps this project separate from anything else on
  your computer.
- `.\.venv\Scripts\python.exe` means "use *that* private Python, not some other Python".
- The `.\` at the start just means "starting from the folder I am currently in".

You may see tutorials online tell you to "activate the environment" first. You do not need to.
Typing the full path every time achieves the same thing and is impossible to forget.

### Step 3 — Check that everything is healthy

Type this and press Enter:

```powershell
.\.venv\Scripts\python.exe scripts\verify_setup.py
```

Wait a few seconds. You want **seven lines that all say PASS**:

```
  [PASS] Ollama runtime and models  7 models available, all required models present
  [PASS] SQLite sample database     SHP-1007 present with NULL trailer_id
  [PASS] SQL safety validation      5 writes rejected, comment injection neutralised
  [PASS] Log search tool            5 lines matched, ERROR line present
  [PASS] Chroma knowledge index     22 chunks indexed, retrieval returned numbered dispatch rules
  [PASS] Retrieval pipeline         dense 20 -> sparse 20 -> fused 22 -> reranked -> final 4
  [PASS] Multi-format ingestion     markdown, pdf and code chunks are all retrievable

All checks passed - ready to demo.
```

If you see any `FAIL`, jump to [Troubleshooting](#troubleshooting) and find that exact line. Do
not continue until all seven pass — a failure here always becomes a worse failure later.

### Step 4 — Start the app

Type this and press Enter:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app/ui.py
```

After a few seconds you will see:

```
  You can now view your Streamlit app in your browser.

  Local URL: http://localhost:8501
```

A browser tab usually opens on its own. If it does not, open your browser and go to:

```
http://localhost:8501
```

**Three things to know about this window:**

- **Leave it open.** This window *is* the running app. Closing it stops the demo.
- It will look frozen. That is normal — it is waiting and printing nothing.
- The number after the last colon is the **port**, `8501`. If you ever see a different number in
  the window, use that number in your browser instead.

### Step 5 — Stop the app when you are done

Click on the PowerShell window and press **Ctrl** + **C** together. You get your prompt back.
Closing the window works too.

---

## What to click in the demo

The page has a **sidebar on the left** with buttons for each prepared scenario. Click a button to
load its question into the box, then click the blue **Investigate** button.

Run them in this order — the story builds up:

### 1. Click "Scenario 1 — knowledge question"

Asks: *What conditions are required for READY_FOR_DISPATCH?*

The AI reads only the documentation and answers with the three rules. It does **not** touch logs
or the database, which you can see in the "Sources used" row.

Scroll to the **Sources** panel underneath the answer. Every sentence in the answer ends with a
little number like `[2]`, and that number matches one of the passages listed there. Click a
passage open to see the exact text the AI was given.

**The point:** the AI answers from your documents, not from guesswork — and you can check each
sentence against the paragraph it came from.

### 2. Click "Scenario 2 — root-cause investigation"

Asks: *Why is shipment SHP-1007 stuck in CREATED?*

Now all three sources light up. Expand **Workflow trace** to narrate the steps out loud, then
scroll to the evidence tabs to show the actual log line and database row it read.

Expected conclusion: no trailer is assigned, about 90% confidence.

**The point:** it combines a business rule, a log error and a database value into one answer, and
shows its evidence.

### 3. Click "Scenario 3 — human approval"

Asks: *Suggest how to fix shipment SHP-1007.*

This time the app **stops** and shows "Human review required" with Approve and Reject buttons.
Nothing happens until you click one.

**The point — say this part out loud:** the AI proposed an action that would change production,
so the workflow paused. A human decides. This is the answer to "what if the AI does something
stupid".

### 4. Optional — prove it is really thinking

Click **"Trailer in maintenance"** and then **"Inbound-only facility"**. These two shipments look
broken in the same way as SHP-1007, but the causes are different — a trailer under maintenance,
and a depot that only accepts incoming deliveries. The AI finds the right cause for each.

**The point:** it is reading evidence, not repeating one memorised answer.

### 5. Optional — it reads PDFs and source code too

Click **"Escalation policy (PDF source)"**. The answer comes from a PDF document, and the Sources
panel says which page it came from.

Then click **"Source code question"**. That answer comes from a Java file. The knowledge base is
not just a folder of notes; it can hold policy documents and real code side by side.

### 6. Optional — show how the search actually works

Open the **Retrieval pipeline** panel below the answer. It shows three columns:

- **Dense** — results from *meaning* search. Good at understanding a question worded differently
  from the document.
- **BM25** — results from *exact word* search. Good at finding a specific code like `SHP-1007` or
  `MISSING_TRAILER`, which meaning-search often misses.
- **Reranked** — the final shortlist, after a second, more careful AI model re-reads each
  candidate alongside the question and re-sorts them.

The sidebar has switches for **Hybrid search** and **Cross-encoder rerank**. Turn one off, ask
the same question again, and watch the shortlist get worse.

**The point:** the quality of a RAG system is decided before the AI writes a single word. If the
wrong paragraph is retrieved, no amount of clever wording can rescue the answer.

---

## How long things take

The first question you ask is always the slowest, because the AI model has to be loaded into
memory. After that it stays loaded and everything speeds up.

| | First question | Later questions |
| --- | --- | --- |
| Normal mode (`qwen3:14b`) | about 35 seconds | about 15 seconds |
| Fast mode (`qwen3:8b`) | about 16 seconds | about 8 seconds |

While it works, the page shows a spinner. **It is not stuck — let it finish.**

The sidebar has a **Fast mode** switch that uses a smaller, quicker, slightly less polished
model. One catch: flipping the switch forces the computer to swap models, so the very next
question after flipping is slow again. Pick one mode and stay in it.

> **Tip for a live demo:** run Scenario 2 once a few minutes before your audience arrives. That
> loads the model, so your real demo starts fast.

---

## Troubleshooting

Find the message you actually saw in the left column.

| What you see | What it means | What to do |
| --- | --- | --- |
| `... is not recognized as the name of a cmdlet` | You are in the wrong folder, or mistyped | Run `cd D:\AI\Projects\langchain-langgraph` and try again |
| `[X] Ollama is not running` | The AI engine is off | Start menu → type `Ollama` → Enter → wait 10 seconds → retry |
| `[FAIL] Ollama runtime and models` | Same as above, or a model is missing | Start Ollama. If it persists, run `ollama pull qwen3:14b` |
| `[FAIL] Chroma knowledge index` | The searchable copy of the documents is missing | Run `.\.venv\Scripts\python.exe scripts\bootstrap.py` |
| `The knowledge index is empty` | Same as above | Same as above |
| `Port 8501 is already in use` | The app is already running | Just open http://localhost:8501 |
| Browser says "can't reach this page" | App not started, or wrong port | Check the PowerShell window is still open and use the exact URL it printed |
| Page loads but Investigate does nothing | Ollama stopped after the page opened | Start Ollama, then refresh the browser |
| Everything is very slow | Normal on the first question | Wait. See the timing table above |
| Red error box mentioning `connection refused` | Ollama is not reachable | Start Ollama and click Investigate again |
| The Sources panel is empty | The question did not need documents (logs or database only) | Normal. Try Scenario 1 |
| An orange "Grounding warning" appears | The AI cited a source it was not given | Worth mentioning out loud: the system caught it rather than hiding it |
| Something about downloading a model from `huggingface` | The reranker is fetching itself, once | Wait, or turn off **Cross-encoder rerank** in the sidebar |

### The universal fix

If things are in a strange state, reset cleanly:

1. Click the PowerShell window, press **Ctrl** + **C**.
2. Close the window.
3. Make sure Ollama is running (Start menu → `Ollama` → Enter).
4. Start again from [Step 1](#step-1--open-powershell-in-the-right-folder).

You cannot break anything by doing this. The demo data is rebuilt from files in the project and
no real system is connected.

---

## One-time setup (already done — for a different computer)

You do **not** need this tomorrow. It is here in case you set the project up on another machine.

```powershell
# 1. Download the AI models (about 15 GB, takes a while)
ollama pull qwen3:14b
ollama pull qwen3:8b
ollama pull qwen3-embedding:0.6b

# 2. Create the private Python environment
cd D:\AI\Projects\langchain-langgraph
python -m venv .venv

# 3. Install the project's add-on packages
#    The first line grabs the small CPU-only version of torch; without it pip downloads
#    about 2 GB of graphics-card support this project never uses.
.\.venv\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 4. Build the sample database and the searchable document index
.\.venv\Scripts\python.exe scripts\bootstrap.py

# 5. Confirm it all works
.\.venv\Scripts\python.exe scripts\verify_setup.py
```

Requires Python 3.12 or newer and [Ollama](https://ollama.com) installed.

---

## Other ways to run it

You will not need these for a normal demo.

**Run the scenarios as plain text, no browser.** Useful if the browser misbehaves mid-demo:

```powershell
.\.venv\Scripts\python.exe scripts\run_scenarios.py            # the 3 main scenarios
.\.venv\Scripts\python.exe scripts\run_scenarios.py 2          # just scenario 2
.\.venv\Scripts\python.exe scripts\run_scenarios.py 4 5        # the 2 extra cases
.\.venv\Scripts\python.exe scripts\run_scenarios.py 6 7        # the PDF and source-code cases
.\.venv\Scripts\python.exe scripts\run_scenarios.py 2 --fast   # scenario 2, faster model
```

**Score the document search.** Runs 18 test questions where the correct document is already
known, and prints how often the search found it:

```powershell
.\.venv\Scripts\python.exe eval\run_eval.py
```

This is the answer to "how do you know the AI is finding the right information?" — it is
measured, not assumed.

**Start the REST API** for a developer audience who wants to see the endpoints:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.api:app --reload
```

Then open http://localhost:8000/docs for clickable API documentation.

---

## Words you will hear, in plain English

| Term | Plain meaning |
| --- | --- |
| **Ollama** | The program that runs AI models on your own computer, so nothing goes to the internet |
| **Model** | The AI brain itself. `qwen3:14b` is the bigger, smarter one; `qwen3:8b` is smaller and faster |
| **LangChain** | The toolkit connecting the AI to your documents, logs and database |
| **LangGraph** | The traffic controller deciding the order of steps, and where to pause for a human |
| **RAG** | Letting the AI search your documents before answering, instead of guessing |
| **Embedding** | A document turned into a list of numbers, so the computer can find text with a similar *meaning* rather than matching words |
| **Vector database** | Where those number-lists are stored and searched. This project uses Chroma |
| **Chunk** | One small slice of a document. Documents are cut up so the AI receives only the relevant paragraphs |
| **BM25** | Old-fashioned exact-word search. Kept alongside meaning-search because each catches what the other misses |
| **Reranking** | A second, more careful model that re-reads the shortlist and reorders it before the AI sees it |
| **Citation** | The `[2]` markers in the answer, each pointing at the exact passage that claim came from |
| **Grounding** | Checking the AI only cited passages it was really given, rather than inventing a source |
| **Port** | A numbered door on your computer. The app uses door `8501` |
| **localhost** | "This computer." `http://localhost:8501` means "the app running right here" |
| **Terminal / PowerShell** | The window where you type commands |
| **venv** | The project's private Python setup, kept in the `.venv` folder |
| **Checkpoint** | A saved snapshot of the workflow, which is how it can pause for approval and resume later |

---

## The one-sentence summary for your leads

> LangChain provides the AI building blocks, LangGraph arranges them into a controlled business
> process with a human approval gate, and a locally hosted model provides the intelligence — so
> no operational data ever leaves the machine.
