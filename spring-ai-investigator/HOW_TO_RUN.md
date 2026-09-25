# How to run this — every step

Written for someone who has never run a Java project. Follow it top to bottom. Nothing here
requires you to understand Java.

Everything runs on your own machine. No API keys, no accounts, no cost.

---

## Step 1: Check you have Java 21

Open **PowerShell** (press Start, type `powershell`, press Enter) and run:

```powershell
java -version
```

You want a version starting with `21` or higher. If you see something like
`openjdk version "21.0.12"`, you are fine — skip to Step 2.

If it says the command is not recognised, install **Temurin JDK 21** from
<https://adoptium.net>, accept the defaults, then close and reopen PowerShell and try again.

---

## Step 2: Check you have Maven

Maven is the tool that builds Java projects.

```powershell
mvn -version
```

If it prints a version, skip to Step 3.

If not, install it with:

```powershell
winget install Apache.Maven
```

Then **close and reopen PowerShell** so it picks up the change.

---

## Step 3: Install Ollama and the three models

Ollama runs the AI models locally.

1. Download and install from <https://ollama.com/download>.
2. After installing, open PowerShell and download the three models:

```powershell
ollama pull qwen3:14b
ollama pull qwen3:8b
ollama pull qwen3-embedding:0.6b
```

This downloads roughly 15 GB in total and takes a while. You only do it once.

Check they arrived:

```powershell
ollama list
```

You should see all three names in the list.

> **What each one does:** `qwen3:14b` is the main reasoning model. `qwen3:8b` is a smaller,
> faster one used when you tick "Fast mode". `qwen3-embedding:0.6b` turns the documentation into
> numbers so it can be searched by meaning.

---

## Step 4: Make sure Ollama is running

```powershell
ollama serve
```

If it says the address is already in use, that is good news — it is already running. Leave it be.

Otherwise **leave that window open** and open a second PowerShell window for the next steps.

---

## Step 5: Go to the project folder

```powershell
cd d:\AI\Projects\langchain-langgraph\spring-ai-investigator
```

---

## Step 6: Start the application

```powershell
mvn spring-boot:run
```

The first time, Maven downloads its dependencies, which takes a couple of minutes. Later runs
start in about ten seconds.

Wait until you see a line containing:

```
Started InvestigatorApplication
```

**Leave this window open.** Closing it stops the application.

> On Windows you can skip Steps 5 and 6 by double-clicking **`start-demo.bat`**, which does the
> same thing and opens your browser for you.

---

## Step 7: Open it in your browser

Go to <http://localhost:8080>.

You should see a dark page titled **AI Production Issue Investigator** with five scenario buttons.

---

## Step 8: Check everything works before you demo

Click **Run system checks** at the top, or go to <http://localhost:8080/health/checks>.

All five checks should say **PASS**. If any says FAIL, the detail text tells you what to fix. The
usual cause is that Ollama is not running — go back to Step 4.

---

## Step 9: Try it

Click **Stuck shipment**. After a few seconds you will see:

- **What the agent understood** — the type of question and a one-line summary.
- **Workflow trace** — each step it took, in order, including which model it used.
- **Evidence** — three expandable panels showing the exact documentation, log lines and database
  row it read. Open the Database one: `trailer_id: NULL` is the actual cause.
- **Root cause analysis** — the conclusion, its supporting evidence, and a confidence bar.

Now click **Request a fix**. This time it stops and asks for your approval, because the action
would change production data. Nothing has been applied. Click **Approve**, **Reject**, or type a
different action and click **Modify**.

---

## What to show someone

In this order, it tells a complete story in about two minutes:

1. **Stuck shipment** — it reads three sources and finds a specific cause.
2. **Dispatch rules** — a documentation question skips the whole investigation and answers directly,
   so it is not blindly running the same pipeline every time.
3. **Trailer in maintenance** — a *different* shipment with a *different* cause. This is the one
   that proves it is reading evidence rather than repeating a memorised answer.
4. **Request a fix** — it stops and waits for a human before changing anything.

---

## Two things that will bite you in a live demo

1. **The very first question is slow** (30 seconds or more) while Ollama loads the model into
   memory. Ask one throwaway question before your audience is watching.
2. **Do not toggle "Fast mode" back and forth.** Switching between the two models makes Ollama
   unload one and load the other, which turns a 3-second answer into a 15-second one. Pick one
   setting at the start and leave it alone.

---

## Stopping it

Click on the PowerShell window running the app and press **Ctrl + C**.

---

## If something goes wrong

**"Could not reach Ollama at localhost:11434"**
Ollama is not running. Open a new PowerShell window and run `ollama serve`.

**The page will not load at all**
Check the PowerShell window for the line `Started InvestigatorApplication`. If instead you see
`Port 8080 was already in use`, something else is on that port. Run it on another port:

```powershell
mvn spring-boot:run "-Dspring-boot.run.arguments=--server.port=8081"
```

Then use <http://localhost:8081>.

**"No investigation is awaiting approval for thread ..."**
The application was restarted between asking and approving. Approvals are held in memory, so they
do not survive a restart. Just ask the question again.

**A health check fails on the database**
Delete the `data\shipping.db` file and restart. It rebuilds itself from scratch.

**Answers look wrong or truncated**
Confirm all three models are present with `ollama list`. A missing embedding model in particular
causes odd results, because the documentation search silently returns nothing useful.

---

## Running the tests (optional)

```powershell
mvn test
```

29 tests. Ollama needs to be running for most of them. Takes about a minute.
