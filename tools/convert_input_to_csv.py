#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Convert input.json to CSV file for easy viewing and analysis.
"""

import json
import csv
from pathlib import Path


def convert_json_to_csv(json_path: Path, csv_path: Path):
    """
    Convert input.json to CSV format.

    Args:
        json_path: Path to input JSON file
        csv_path: Path to output CSV file
    """
    # Load JSON data
    # Handle NaN values in JSON
    import math

    with open(json_path, 'r', encoding='utf-8') as f:
        content = f.read()
        # Replace NaN with null for proper JSON parsing
        content = content.replace('NaN', 'null')
        data = json.loads(content)

    # Define CSV headers
    headers = ['name', 'tag', 'url', 'remarks', 'human_comments']

    # Write to CSV
    with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()

        for item in data:
            # Handle None values (convert to empty string)
            row = {
                'name': item.get('name', '') or '',
                'tag': item.get('tag', '') or '',
                'url': item.get('url', '') or '',
                'remarks': item.get('remarks') or '',
                'human_comments': item.get('human_comments') or ''
            }
            writer.writerow(row)

    print(f"✓ CSV file created: {csv_path}")
    print(f"  Total videos: {len(data)}")


if __name__ == "__main__":
    script_dir = Path(__file__).parent
    input_json = script_dir / "input.json"
    output_csv = script_dir / "input.csv"

    convert_json_to_csv(input_json, output_csv)
