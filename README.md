# event-log

Voice-to-structured-data pipeline. Siri captures free-text events with GPS
coordinates, GitHub Actions runs an LLM parser, and results land as queryable
YAML frontmatter in a git-backed Obsidian vault.

No app. No database. No server.

## How it works

```
Siri shortcut
  ├─ captures text + GPS
  └─ POST → GitHub repository_dispatch
              └─ GitHub Actions
                   ├─ OpenAI parses text → structured JSON
                   ├─ Python writes YAML frontmatter to daily/<YYYY>/<MM>/<YYYY-MM-DD>.md
                   └─ git commit + push
```

The LLM classifies each entry as nutrition (with calorie estimate), exercise
(with rep counts), or journal, and resolves relative time references
("15 minutes ago") to UTC timestamps. A prompt template (`prompts/log_normalize.yml`)
controls parsing behavior.

## Data format

Daily notes use YAML frontmatter queryable by Obsidian Dataview:

```yaml
---
date: 2024-01-15
events:
  journal:
    - time: "14:30"
      event: "Freight train headed north, 47 cars"
      latlong: "40.7128,-74.0060"
  nutrition:
    - time: "12:30"
      event: "Sandwich and coffee"
      kcals: 450
      latlong: "40.7128,-74.0060"
  reps:
    - time: "07:00"
      event: "20 pushups, 50 situps"
      exercises:
        - exercise: push-ups
          reps: 20
        - exercise: sit-ups
          reps: 50
---
```

## Setup

### Prerequisites

- iOS 16+ / macOS 13+
- GitHub personal access token (`repo` + `workflow` scopes)
- OpenAI API key

### 1. Configure the vault repository

Add these files to your Obsidian vault repo:

- `scripts/log_event.py`
- `scripts/openai_parser.py`
- `prompts/log_normalize.yml`

Add repository secrets:

| Secret | Purpose |
|--------|---------|
| `OPENAI_API_KEY` | LLM parsing |
| `VAULT_TOKEN` | Git push from Actions |
| `TIMEZONE` | Local time resolution (default: `America/New_York`) |

Add `.github/workflows/log-event.yml`:

```yaml
name: Log Event
on:
  repository_dispatch:
    types: [log_event]

jobs:
  log:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          token: ${{ secrets.VAULT_TOKEN }}
      - uses: actions/setup-python@v4
        with:
          python-version: "3.11"
      - run: pip install openai python-dotenv ruamel.yaml
      - run: >
          python scripts/log_event.py
          "${{ github.event.client_payload.text }}"
          "${{ github.event.client_payload.latlong }}"
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          OPENAI_MODEL: gpt-4o
          TIMEZONE: ${{ secrets.TIMEZONE }}
          VAULT_DIR: ${{ github.workspace }}
      - run: |
          git config user.email "action@github.com"
          git config user.name "GitHub Action"
          git add .
          git diff --staged --quiet || git commit -m "log: ${{ github.event.client_payload.text }}"
          git push
```

### 2. Create the iOS shortcut

Actions:
1. **Get My Location**
2. **Ask for Text**
3. **Get Contents of URL** (POST):
   - URL: `https://api.github.com/repos/<owner>/<repo>/dispatches`
   - Headers: `authorization: token <PAT>`, `accept: application/vnd.github+json`
   - Body: `{"event_type": "log_event", "client_payload": {"text": "<input>", "latlong": "<lat>,<lon>"}}`

### CLI alternative

```bash
pip install openai python-dotenv ruamel.yaml
python scripts/log_event.py "Had a sandwich and coffee" "40.7128,-74.0060"
```

## Vault sync (macOS)

`macos/push_vault.py` handles bidirectional git sync with conflict resolution
(renames conflicted files rather than blocking). Run it on a timer via launchd
(`macos/com.user.sync_all.plist`).

## Repository structure

```
scripts/
  log_event.py          Main entry point
  openai_parser.py      OpenAI structured output client
prompts/
  log_normalize.yml     LLM prompt template and examples
macos/
  push_vault.py         Git sync with conflict resolution
  com.user.sync_all.plist  launchd timer
bruno/                  API test collection (Bruno)
```

## Environment variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `OPENAI_API_KEY` | Yes | — | LLM parsing |
| `OPENAI_MODEL` | No | `gpt-4o` | Model selection |
| `TIMEZONE` | No | `America/New_York` | Time resolution |
| `VAULT_DIR` | No | Parent of script | Vault root |
