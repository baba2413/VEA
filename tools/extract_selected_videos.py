#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Extract URLs for selected video numbers from input.json
"""

import json
from pathlib import Path


def extract_videos(input_json: Path, video_numbers: list, output_json: Path):
    """
    Extract specific videos by number from input.json

    Args:
        input_json: Path to input.json
        video_numbers: List of video numbers to extract (1-based indexing)
        output_json: Path to output JSON file
    """
    # Load input.json with NaN handling
    with open(input_json, 'r', encoding='utf-8') as f:
        content = f.read()
        content = content.replace('NaN', 'null')
        data = json.loads(content)

    # Extract selected videos
    selected = []
    for num in video_numbers:
        # Convert to 0-based index
        idx = num - 1
        if 0 <= idx < len(data):
            video = data[idx]
            selected.append({
                'number': num,
                'name': video.get('name', ''),
                'url': video.get('url', ''),
                'tag': video.get('tag', ''),
                'remarks': video.get('remarks', '')
            })
            print(f"✓ video({num}).mp4 - {video.get('tag', 'N/A')} - {video.get('remarks', 'N/A')}")
        else:
            print(f"✗ video({num}).mp4 - Index out of range")

    # Create download list (just URLs)
    download_list = [v['url'] for v in selected if v['url']]

    # Save both formats
    # 1. Full info for reference
    info_path = output_json.parent / f"{output_json.stem}_info.json"
    with open(info_path, 'w', encoding='utf-8') as f:
        json.dump(selected, f, ensure_ascii=False, indent=2)

    # 2. Simple URL list for download_shorts.py
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(download_list, f, ensure_ascii=False, indent=2)

    print(f"\n✓ Info saved to: {info_path}")
    print(f"✓ Download list saved to: {output_json}")
    print(f"\nTotal videos to download: {len(download_list)}")

    return selected


if __name__ == "__main__":
    script_dir = Path(__file__).parent

    # Video numbers to extract
    video_numbers = [4, 31, 6, 74, 8, 23, 64, 70, 10, 38, 51, 52, 17, 20, 91, 95, 24, 32, 87, 90]

    input_json = script_dir / "input.json"
    output_json = script_dir / "selected_videos.json"

    print(f"Extracting {len(video_numbers)} videos from {input_json}...\n")
    extract_videos(input_json, video_numbers, output_json)
