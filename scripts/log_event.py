#!/usr/bin/env python3
"""
log_event.py

- Receives a text string with nutrition, exercise, or other information
- Parses entries for:
    - calories
    - repetitions (exercise)
    - relative time
- Grabs the latlong field sent by a HTTP POST to GitHub Actions
- Adds to Obsidian Vault (in GitHub)
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from ruamel.yaml import YAML

from openai_parser import get_structured_log_entry


# --- Configuration ---

load_dotenv()

TIMEZONE = os.getenv("TIMEZONE") or "America/New_York"

VAULT_DIR = Path(os.getenv("VAULT_DIR", str(Path(__file__).parent.parent)))
DAILY_DIR = VAULT_DIR / "daily"
PROMPTS_DIR = VAULT_DIR / "prompts"


# --- Error Handling ---
def _handle_error(message, exit_code=1):
    """Print a message to stderr and exit."""
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(exit_code)


# --- YAML/Markdown Utilities ---
def split_frontmatter(text):
    """
    Splits a Markdown file into (yaml_str, content).
    If no frontmatter, returns ("", text).
    """
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            _, yaml_str, content = parts[0], parts[1], parts[2].lstrip("\n")
            return yaml_str, content
    return "", text


def join_frontmatter(yaml_str, content):
    """
    Joins yaml_str and content into a Markdown file with YAML frontmatter.
    """
    out = "---\n"
    out += yaml_str.rstrip("\n") + "\n"
    out += "---\n"
    if content:
        out += content.lstrip("\n")
    return out


# --- File I/O ---
def load_or_create_post(path):
    """Load an existing daily note or create an in-memory stub."""
    yaml = YAML()
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
            yaml_str, content = split_frontmatter(text)
            metadata = yaml.load(yaml_str) if yaml_str.strip() else {}
            return {"metadata": metadata, "content": content}
        except Exception as e:
            _handle_error(f"Could not parse YAML frontmatter in {path}: {e}")
    # For new files, initialize with an empty events dictionary
    return {"metadata": {"date": path.stem, "events": {}}, "content": ""}


def write_post(post, path):
    """Write the post object back to a file, creating dirs if needed."""
    yaml = YAML()
    yaml.default_flow_style = False
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        from io import StringIO

        # --- Remove summary generation and content update ---
        buf = StringIO()
        yaml.dump(post["metadata"], buf)
        yaml_str = buf.getvalue()
        out = join_frontmatter(yaml_str, post.get("content", ""))
        with open(path, "w", encoding="utf-8") as f:
            f.write(out)
        print(f"✅ Logged event to {path}.")
        print(f"[DEBUG] File contents:\n{out}")
    except Exception as e:
        _handle_error(f"Failed to write log file to {path}: {e}")


# --- Core Logic ---
def get_event_datetime(ai_response, local_tz):
    """
    Determines the event's datetime.
    1. Uses the parsed 'datetime_utc' from the AI response if available.
    2. Falls back to the current time in the local timezone.
    """
    if dt_utc_str := ai_response.get("datetime_utc"):
        try:
            # Parse the ISO string from AI and convert to local timezone
            dt_utc = datetime.fromisoformat(dt_utc_str.replace("Z", "+00:00"))
            return dt_utc.astimezone(local_tz)
        except (ValueError, TypeError):
            print(f"⚠️  Could not parse datetime '{dt_utc_str}'. Using current time.")
    return datetime.now(local_tz)


def parse_and_format_latlong(latlong):
    """Reduce latlong string to 4 decimal places per coordinate."""
    try:
        lat, lon = [float(x) for x in latlong.split(",")]
        return f"{lat:.4f},{lon:.4f}"
    except Exception:
        return ""


def parse_args_and_env(argv, environ):
    """
    Parse CLI arguments and environment for text and latlong.
    Returns (text, latlong).
    """
    if len(argv) < 2 or not (text := argv[1].strip()):
        _handle_error("Usage: python log_event.py '<entry text>' [latlong]", 2)
    latlong = ""
    if len(argv) > 2:
        latlong = parse_and_format_latlong(argv[2])
    elif environ.get("LATLONG"):
        latlong = parse_and_format_latlong(environ["LATLONG"])
    return text, latlong


def build_event_from_response(text, ai_response, event_dt, latlong=""):
    """Constructs the event category and payload from the AI response, with latlong."""
    parsed_data = ai_response.get("parsed", {})
    if not parsed_data:
        print("⚠️  AI did not return a parsable object. Nothing to log.")
        return None

    base_payload = {
        "time": event_dt.strftime("%H:%M"),
        "event": text,
    }
    # Add latlong if present
    if latlong:
        base_payload["latlong"] = latlong

    if "kcals" in parsed_data:
        category = "nutrition"
        payload = {**base_payload, "kcals": parsed_data["kcals"]}
    elif "exercises" in parsed_data:
        category = "reps"
        payload = {**base_payload, "exercises": parsed_data["exercises"]}
    else:
        category = "journal"
        payload = base_payload

    return category, payload


def append_event_to_post(post, category, payload):
    """Appends a new event to the post's metadata and sorts the category."""
    events = post["metadata"].get("events", {})
    if not isinstance(events, dict):
        events = {}  # Reset if 'events' is not a dictionary

    if not isinstance(events.get(category), list):
        events[category] = []

    events[category].append(payload)
    # Sort just the modified category by time
    events[category].sort(key=lambda x: x.get("time", "00:00"))

    post["metadata"]["events"] = events
    return post


# --- Main Orchestration ---
def process_log_event(
    text,
    latlong,
    timezone=TIMEZONE,
    vault_dir=VAULT_DIR,
    prompts_dir=PROMPTS_DIR,
):
    """Process and log the event, pure function except for I/O."""
    prompt_file_path = prompts_dir / "log_normalize.yml"
    print(
        f"[DEBUG] text={text}, latlong={latlong}, prompt_file_path={prompt_file_path}"
    )
    try:
        ai_response = get_structured_log_entry(text, prompt_file_path)
        print(f"[DEBUG] ai_response={ai_response}")
    except Exception as e:
        _handle_error(f"OpenAI parse failed: {e}")

    local_tz = ZoneInfo(timezone)
    event_dt = get_event_datetime(ai_response, local_tz)
    print(f"[DEBUG] event_dt={event_dt}")
    result = build_event_from_response(text, ai_response, event_dt, latlong)
    print(f"[DEBUG] build_event_from_response result={result}")
    if not result:
        print("[DEBUG] No event to log.")
        return
    category, payload = result

    year = event_dt.strftime("%Y")
    month = event_dt.strftime("%m")
    date_str = event_dt.strftime("%Y-%m-%d")
    md_path = vault_dir / "daily" / year / month / f"{date_str}.md"
    print(f"[DEBUG] md_path={md_path}")

    post = load_or_create_post(md_path)
    updated_post = append_event_to_post(post, category, payload)
    print(f"[DEBUG] updated_post={updated_post}")
    write_post(updated_post, md_path)


def main():
    """Thin CLI entry point."""
    text, latlong = parse_args_and_env(sys.argv, os.environ)
    process_log_event(text, latlong)
