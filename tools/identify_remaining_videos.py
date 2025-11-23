#!/usr/bin/env python3
"""Identify remaining videos to test (exclude already tested and API-blocked)"""

import json
import os

# Get all videos in yt_shorts directory (our 20 selected videos)
yt_shorts_dir = 'yt_shorts'
all_video_files = [f for f in os.listdir(yt_shorts_dir) if f.endswith('.mp4')]

# Load analysis results to check validity
with open('../api/analysis_results.json', 'r') as f:
    all_results = json.load(f)

# Already tested videos
tested_videos = [
    '#shorts #담배-qR2K__FCLb0.mp4',
    "''its okay'' WYM YOU JUST MADE ME JUMP #ethanwinters #residentevil7-pxNvqepEYOY.mp4",
    'BOOTED by Gordon Ramsay？! #shorts #gordonramsay #fyp-gT-ZPJW1j1c.mp4',
    'Do you like leather bikinis？ 🖤 #beach #beachvibes #short #shorts #shortvideo #shortsfeed-WUGUXTcEUfo.mp4',
    "HEISENBERG'S FIRST DEAL!🤑｜ Breaking Bad #shorts-Ix3XLxar5Uo.mp4"
]

# API-blocked videos
blocked_videos = [
    'Most Disturbing Anime Moment #creepyanime #disturbing #trending-Mjx-2vXagSs.mp4',
    "역사상 가장 '소름' 끼치는 영상？-SH04s_kOKzg.mp4"
]

# Get all valid videos (not blocked, not already tested)
remaining_videos = []
for video_name in all_video_files:
    # Skip if already tested
    if video_name in tested_videos:
        continue
    # Skip if API-blocked
    if video_name in blocked_videos:
        continue
    # Check if it's a valid analysis (not error) in results
    if video_name in all_results and all_results[video_name]['ox']['violence'] != -1:
        remaining_videos.append(video_name)

print(f'Remaining videos to test: {len(remaining_videos)}')
print()
for i, v in enumerate(remaining_videos, 1):
    print(f'{i}. {v}')

# Save to a file for the experiment
with open('remaining_videos.json', 'w', encoding='utf-8') as f:
    json.dump(remaining_videos, f, indent=2, ensure_ascii=False)

print(f'\n✓ Saved to remaining_videos.json')
