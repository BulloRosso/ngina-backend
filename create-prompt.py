#!/usr/bin/env python3

import json
from datetime import datetime
from pathlib import Path
import re

def read_file_content(file_path: str) -> str:
    """Read a file and return its content wrapped in triple backticks."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            print(f"Processing {file_path}\n")
            content = f.read().strip()  # Remove leading/trailing whitespace
            return f"```\n{content}\n```"
    except FileNotFoundError:
        print(f"Warning: File not found: {file_path}")
        return f"[Content for {file_path} not found]"

def get_file_contents(file_paths: list[str]) -> str:
    """Read multiple files and concatenate their contents."""
    contents = []
    for file_path in file_paths:
        # Remove leading slash if present to make it relative to current directory
        cleaned_path = file_path.lstrip('/')
        # Add filename as a header before the content
        content = f"\n### {cleaned_path}\n" + read_file_content(cleaned_path)
        contents.append(content)
    return '\n'.join(contents)

def process_template(template_path: str, mappings_path: str) -> str:
    """Process the template file using the mappings from the JSON file."""
    # Read the template
    with open(template_path, 'r', encoding='utf-8') as f:
        template_content = f.read()

    # Read the JSON mappings
    with open(mappings_path, 'r', encoding='utf-8') as f:
        mappings = json.load(f)

    # First, load all file contents
    replacements = {}
    for var_name, file_paths in mappings.items():
        content = get_file_contents(file_paths)
        replacements[var_name] = content

    # Process the template looking for top-level variables only
    final_result = ''
    last_pos = 0

    # Use regex to find all variables in the template
    pattern = re.compile(r'\{(\w+)\}')

    for match in pattern.finditer(template_content):
        var_name = match.group(1)
        start_pos = match.start()
        end_pos = match.end()

        # Add everything since the last match
        final_result += template_content[last_pos:start_pos]

        # If this is a known variable, replace it
        if var_name in replacements:
            final_result += replacements[var_name]
        else:
            print(f"Warning: Variable '{var_name}' not found in mappings file - leaving unchanged")
            final_result += match.group(0)  # Keep the original {variable}

        last_pos = end_pos

    # Add any remaining content after the last match
    final_result += template_content[last_pos:]

    return final_result

def main():
    # Input files
    template_file = "project-prompt-template.md"
    mappings_file = "files-to-include.json"

    # Generate output filename with current date
    current_date = datetime.now()
    output_file = f"project-prompt-{current_date.day}_{current_date.month}_{current_date.year}.md"

    try:
        # Process the template
        result = process_template(template_file, mappings_file)

        # Write the output
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(result)

        print(f"Successfully created {output_file}")

    except Exception as e:
        print(f"Error: {str(e)}")
        exit(1)

if __name__ == "__main__":
    main()