# Event Log

An intelligent event logging system designed for iOS Shortcuts that parses natural language input for nutrition, exercise, and journal entries, then stores structured data in an Obsidian vault using AI-powered text analysis.

## Features

- **iOS Shortcuts Integration**: Native iOS/macOS Shortcuts support with automatic GPS location capture
- **Natural Language Processing**: Convert free-form text into structured data using OpenAI GPT-4o
- **Multi-Category Support**: Handles nutrition (calories), exercise (repetitions), and journal entries
- **Obsidian Integration**: Automatically organizes entries in daily markdown files with YAML frontmatter
- **GitHub Actions Workflow**: Serverless processing via GitHub repository dispatch events
- **Automatic Location Tracking**: GPS coordinates captured seamlessly via iOS location services
- **Automatic Git Sync**: Bi-directional synchronization with remote Obsidian vault
- **Time Intelligence**: Parses relative time references ("15 minutes ago", "this morning")
- **Command Line Interface**: Alternative CLI access for direct script execution

## Quick Start

### iOS/macOS Shortcuts Setup (Recommended)

**Prerequisites:**
- iOS 16+ or macOS 13+ device
- GitHub personal access token
- OpenAI API key
- Git repository for your Obsidian vault

**Setup Steps:**

1. **Create GitHub Repository**
   - Fork or create a new repository for your Obsidian vault
   - Enable GitHub Actions in repository settings
   - Note your repository URL: `https://github.com/USERNAME/REPO`

2. **Generate GitHub Personal Access Token**
   - Go to GitHub Settings → Developer settings → Personal access tokens
   - Create token with `repo` and `workflow` permissions
   - Save the token securely

3. **Set up GitHub Actions Workflow**
   - Add the Python scripts from this repository to your vault repo
   - Configure GitHub Actions workflow (see [GitHub Actions Setup](#github-actions-setup))

4. **Create iOS Shortcut**
   - Open iOS Shortcuts app
   - Create new shortcut with these actions:
     ```
     1. Get My Location (with permission)
     2. Ask for Text
     3. Get Contents of URL:
        - URL: https://api.github.com/repos/USERNAME/REPO/dispatches
        - Method: POST
        - Headers:
          - authorization: token YOUR_GITHUB_TOKEN
          - accept: application/vnd.github+json
        - Request Body (JSON):
          {
            "event_type": "log_event",
            "client_payload": {
              "text": "[Text from Step 2]",
              "latlong": "[Latitude from Step 1],[Longitude from Step 1]"
            }
          }
     ```

5. **Add to Home Screen/Widget**
   - Name your shortcut (e.g., "Log Event")
   - Add to Home Screen or Shortcuts widget for quick access

### Alternative: Command Line Interface

For development or server environments:

**Prerequisites:**
- Python 3.9+
- OpenAI API key
- Git repository for Obsidian vault

**Installation:**
```bash
# Clone and setup
git clone <repository-url>
cd event-log
pip install -r requirements.txt

# Configure environment
cp .env.example .env  # Edit with your API keys
```

**Usage:**
```bash
# Basic logging
python scripts/log_event.py "Had a sandwich and coffee for lunch"

# With location
python scripts/log_event.py "Morning jog" "40.7128,-74.0060"
```

## Project Structure

```
event-log/
├── scripts/
│   ├── log_event.py          # Main logging script
│   └── openai_parser.py      # OpenAI API integration
├── prompts/
│   └── log_normalize.yml     # AI parsing prompt configuration
├── macos/
│   ├── push_vault.py         # Git synchronization utility
│   └── com.user.sync_all.plist # macOS automation configuration
├── bruno/                    # API testing configuration
│   ├── eventlog.bru          # Bruno HTTP client tests
│   └── environments/
└── requirements.txt          # Python dependencies
```

## GitHub Actions Setup

To enable serverless processing of your iOS Shortcut requests, you'll need to set up a GitHub Actions workflow in your Obsidian vault repository.

### 1. Add Workflow File

Create `.github/workflows/log-event.yml` in your vault repository:

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
          
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
          
      - name: Install dependencies
        run: |
          pip install openai python-dotenv ruamel.yaml
          
      - name: Log event
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          OPENAI_MODEL: gpt-4o
          TIMEZONE: ${{ secrets.TIMEZONE || 'America/New_York' }}
          VAULT_DIR: ${{ github.workspace }}
        run: |
          python scripts/log_event.py "${{ github.event.client_payload.text }}" "${{ github.event.client_payload.latlong }}"
          
      - name: Commit and push changes
        run: |
          git config --local user.email "action@github.com"
          git config --local user.name "GitHub Action"
          git add .
          git diff --staged --quiet || git commit -m "Add event: ${{ github.event.client_payload.text }}"
          git push
```

### 2. Add Repository Secrets

In your vault repository settings, add these secrets:
- `OPENAI_API_KEY`: Your OpenAI API key
- `VAULT_TOKEN`: GitHub personal access token with repo permissions
- `TIMEZONE`: Your local timezone (optional, defaults to America/New_York)

### 3. Add Script Files

Copy these files from this repository to your vault repository:
- `scripts/log_event.py`
- `scripts/openai_parser.py`
- `prompts/log_normalize.yml`
- `requirements.txt`

## Configuration

### Environment Variables

| Variable | Required | Description | Default |
|----------|----------|-------------|---------|
| `OPENAI_API_KEY` | Yes | OpenAI API key for text parsing | - |
| `OPENAI_MODEL` | No | OpenAI model to use | `gpt-4o` |
| `TIMEZONE` | No | Local timezone for timestamp parsing | `America/New_York` |
| `VAULT_DIR` | No | Path to Obsidian vault directory | Parent directory of script |
| `GITHUB_URL` | No | Git repository URL for vault sync | - |
| `GITHUB_TOKEN` | No | GitHub personal access token | - |
| `BRANCH` | No | Git branch for vault sync | `main` |

### AI Prompt Customization

Edit `prompts/log_normalize.yml` to customize how the AI parses your input. The system supports:

- **Nutrition entries**: Automatically estimates calories
- **Exercise entries**: Extracts exercise types and repetition counts  
- **Journal entries**: Captures general life events and thoughts
- **Time parsing**: Converts relative time references to absolute timestamps

## Data Format

Entries are stored in daily markdown files (`YYYY-MM-DD.md`) with YAML frontmatter:

```yaml
---
date: 2024-01-15
events:
  nutrition:
    - time: "12:30"
      event: "Had a sandwich and coffee for lunch"
      kcals: 450
      latlong: "40.7128,-74.0060"
  reps:
    - time: "07:00"
      event: "Morning workout: 20 pushups, 50 situps"
      exercises:
        - exercise: "push-ups"
          reps: 20
        - exercise: "sit-ups"
          reps: 50
  journal:
    - time: "19:30"
      event: "Beautiful sunset today"
---
```

## Integration Methods

### Primary: iOS Shortcuts + GitHub Actions

**Workflow:**
1. iOS Shortcut captures GPS location and user text input
2. HTTP POST request sent to GitHub repository dispatch API
3. GitHub Actions workflow triggered automatically
4. Python scripts process the event and update Obsidian vault
5. Changes committed and pushed to repository

**Request Format:**
```json
POST https://api.github.com/repos/USERNAME/REPO/dispatches
Headers:
  authorization: token YOUR_GITHUB_TOKEN
  accept: application/vnd.github+json

Body:
{
  "event_type": "log_event",
  "client_payload": {
    "text": "Had a great workout",
    "latlong": "40.7128,-74.0060"  // optional
  }
}
```

### Alternative: Direct CLI

For local development or server environments where you can run Python directly.

## API Reference

### Core Functions

#### `log_event.py`
Main entry point for logging events.

**Usage:**
```python
from scripts.log_event import process_log_event

process_log_event(
    text="your log entry",
    latlong="40.7128,-74.0060",  # optional
    timezone="America/New_York",
    vault_dir=Path("/path/to/vault"),
    prompts_dir=Path("/path/to/prompts")
)
```

#### `openai_parser.py`
Handles AI-powered text parsing.

**Usage:**
```python
from scripts.openai_parser import get_structured_log_entry

result = get_structured_log_entry(
    "Had a protein shake",
    Path("prompts/log_normalize.yml")
)
# Returns: {"parsed": {"kcals": 200}, "datetime_utc": "2024-01-15T17:30:00Z"}
```

### Vault Synchronization

The `macos/push_vault.py` script provides automatic Git synchronization:

```bash
python macos/push_vault.py
```

Features:
- Automatic conflict resolution via file renaming
- Intelligent commit messages from diff content
- Bidirectional sync (pull before push)
- Stash/unstash of local changes

## Development

### Testing with Bruno

Use the included Bruno API collection to test GitHub Actions integration:

1. Install [Bruno](https://github.com/usebruno/bruno)
2. Open the `bruno/` directory in Bruno
3. Configure your `GITHUB_TOKEN` in the environment
4. Run the `eventlog` request to test the API

## Dependencies

- `openai`: OpenAI API client for text parsing
- `python-dotenv`: Environment variable management
- `ruamel.yaml`: YAML processing with comment preservation

## License

This project is licensed under the MIT License.
