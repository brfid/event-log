#!/usr/bin/env python3
"""
openai_parser.py

Provides a function to send a raw text string (e.g., a fitness, nutrition, or exercise entry)
to an OpenAI model and receive a structured JSON object in return.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from openai import APIError, OpenAI
from ruamel.yaml import YAML

load_dotenv()

OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o")


def _load_system_prompt(path):
    """Loads the system prompt text from a specified YAML file using ruamel.yaml."""
    if not path.is_file():
        raise FileNotFoundError(f"Prompt file not found at: {path}")

    yaml = YAML()
    try:
        with open(path, "r", encoding="utf-8") as f:
            prompt_data = yaml.load(f)
            if not isinstance(prompt_data, dict):
                raise ValueError(f"YAML content in {path} is not a dictionary.")

            prompt = prompt_data.get("system_prompt")
            if not prompt:
                raise ValueError(f"'system_prompt' key not found in {path}")
            return str(prompt)
    except Exception as e:
        raise ValueError(f"Error loading or parsing prompt file: {e}") from e


def get_structured_log_entry(text, prompt_file):
    """
    Uses an OpenAI model to parse a raw log entry (nutrition, exercise, or journal) into structured data.
    Injects the current UTC time into the prompt for relative time parsing.

    The expected output is a JSON object with a top-level 'parsed' key. The value of 'parsed' is one of:
      - {"kcals": int} for nutrition
      - {"exercises": [ ... ]} for exercise
      - {"journal": true} for journal entries
      - {} for unrecognized input
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found in .env file.")

    try:
        # Load the base prompt from the provided path
        system_prompt_template = _load_system_prompt(prompt_file)

        # Get current time and safely replace the placeholder
        now_utc = datetime.now(timezone.utc).isoformat()
        system_prompt = system_prompt_template.replace("{current_utc_time}", now_utc)

    except (FileNotFoundError, ValueError) as e:
        # Re-raise the exception to be caught by the main script
        raise e

    client = OpenAI(api_key=api_key)

    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
            temperature=0.1,
        )
        # The response should contain a 'parsed' key, which may include 'kcals', 'exercises', or 'journal'.
        return json.loads(response.choices[0].message.content)
    except APIError as e:
        print(f"An OpenAI API error occurred: {e}", file=sys.stderr)
    except Exception as e:
        print(
            f"An unexpected error occurred while calling OpenAI: {e}", file=sys.stderr
        )

    return {"parsed": {}}


if __name__ == "__main__":
    if len(sys.argv) > 2:
        input_text = sys.argv[1]
        prompt_path = Path(sys.argv[2])
        try:
            result = get_structured_log_entry(input_text, prompt_path)
            print(json.dumps(result, indent=2))
        except ValueError as e:
            print(f"Configuration error: {e}", file=sys.stderr)
        except Exception as e:
            print(f"Unexpected error: {e}", file=sys.stderr)
    else:
        print(
            'Usage: python openai_parser.py "your log entry text" /path/to/prompt.yml',
            file=sys.stderr,
        )
