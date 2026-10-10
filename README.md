# AccessLens AI – Accessibility That Adapts to You

A small full-stack web app built for the **"Invisible AI"** hackathon theme. It makes difficult text easier to read and quietly remembers each person's accessibility settings, so the interface adapts the moment it opens.

> **Honest note:** AccessLens uses **rule-based text processing** (word lists, sentence splitting and regular expressions written in Python). It is **not a trained AI model** and does not call any external AI service. Always double-check important text yourself.

## Features

- **Text simplifier** – replaces complex words/phrases with plainer ones and splits very long sentences.
- **Readability measurement** – Flesch Reading Ease and average sentence length, before vs. after.
- **Important text highlighter** – dates, numbers, deadlines, warnings and key terms (colour *and* underline style).
- **Accessibility settings** – font size, line spacing, dark mode, high-contrast mode.
- **Automatic personalisation** – settings are stored in SQLite and applied before the page paints.
- **Reading mode** – full-screen, distraction-free view (Esc to close).
- **History** – every processed text is saved; view or delete it later.
- **Dashboard** – all statistics are calculated from the database; nothing is hard-coded.

## Tech stack

| Layer    | Technology                          |
|----------|-------------------------------------|
| Frontend | HTML, CSS, vanilla JavaScript (`fetch`) |
| Backend  | Python 3 + Flask                    |
| Database | SQLite (created automatically)      |

No API keys, paid services, Docker or MySQL are needed.

## Run on Windows (VS Code)

Open a terminal in the project folder (Terminal → New Terminal, choose **Command Prompt**) and run:

```cmd
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Then open **http://127.0.0.1:5000** in your browser.

Shortcut: double-click **`run.bat`**. It does all of the above and opens the browser.

Requirements: Python 3.9 or newer (tick "Add Python to PATH" when installing).
If `python` is not recognised, try `py` instead (for example `py -m venv venv`).

## Project structure

```
accesslens-ai/
├── app.py              Flask app and REST API routes
├── models.py           SQLite database code (preferences, history, stats)
├── text_processor.py   Rule-based simplifier, readability score, highlighter
├── requirements.txt
├── run.bat             One-click Windows launcher
├── templates/index.html
└── static/
    ├── css/style.css
    └── js/app.js
```

`accesslens.db` appears next to `app.py` the first time you run the app. Delete it to start fresh.

## API endpoints

| Method | Route                      | Purpose                             |
|--------|----------------------------|-------------------------------------|
| GET    | `/api/preferences`         | Read saved settings                 |
| PUT    | `/api/preferences`         | Validate and save settings          |
| POST   | `/api/preferences/reset`   | Restore default settings            |
| POST   | `/api/process`             | Simplify + highlight text, save it  |
| GET    | `/api/history`             | List saved texts (newest first)     |
| GET    | `/api/history/<id>`        | Load one saved text                 |
| DELETE | `/api/history/<id>`        | Delete one saved text               |
| DELETE | `/api/history`             | Clear all history                   |
| GET    | `/api/stats`               | Dashboard numbers from the database |

## Hackathon demo script (about 2 minutes)

1. Open the app and point out the status message: settings were applied automatically.
2. Click **Load sample text**, then **Simplify & highlight**.
3. Show the before/after readability numbers and the colour-coded highlights.
4. Increase font size, raise line spacing, switch on dark and high-contrast mode.
5. Refresh the page: your settings are still there (loaded from SQLite).
6. Open **reading mode**, then close it with Esc.
7. Show the history list and how the dashboard numbers changed.

## Known limitations

- The dictionary is small, so only some words are replaced.
- Sentence splitting is basic and can mis-split after abbreviations such as "Dr.".
- English only. The readability score uses a rough syllable estimate.
- One shared set of preferences (there are no user accounts).
