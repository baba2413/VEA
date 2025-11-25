#!/usr/bin/env python3
"""Generate feedback template file for incorrect predictions"""

import json
import re

def extract_prediction(result_text: str, criteria: str):
    # Try standard format
    pattern = rf'{criteria}\s*:\s*(0|1)'
    match = re.search(pattern, result_text)
    if match:
        return int(match.group(1))
    # Try JSON format
    json_pattern = rf'"{criteria}"\s*:\s*(0|1)'
    match = re.search(json_pattern, result_text)
    if match:
        return int(match.group(1))
    return None

# Load data
with open('experiment_results/initial_5crit_results_20251125_152732.json') as f:
    data = json.load(f)

with open('ground_truth_template.json') as f:
    gt = json.load(f)
    gt.pop('_README', None)

trial = data['all_trials'][0]

# Collect incorrect results
text_incorrect = []
video_incorrect = []

for result in trial['text_based']:
    if result.get('success'):
        video = result['video']
        criteria = result['criteria']

        if video in gt and criteria in gt[video]:
            gt_value = gt[video][criteria]
            if gt_value is not None:
                pred = extract_prediction(result['result'], criteria)
                if pred is not None and pred != gt_value:
                    error_type = 'False Positive' if pred == 1 else 'False Negative'
                    text_incorrect.append({
                        'video': video,
                        'criteria': criteria,
                        'predicted': pred,
                        'actual': gt_value,
                        'error_type': error_type
                    })

for result in trial['video_based']:
    if result.get('success'):
        video = result['video']
        criteria = result['criteria']

        if video in gt and criteria in gt[video]:
            gt_value = gt[video][criteria]
            if gt_value is not None:
                pred = extract_prediction(result['result'], criteria)
                if pred is not None and pred != gt_value:
                    error_type = 'False Positive' if pred == 1 else 'False Negative'
                    video_incorrect.append({
                        'video': video,
                        'criteria': criteria,
                        'predicted': pred,
                        'actual': gt_value,
                        'error_type': error_type
                    })

# Write to file
with open('incorrect_results_for_feedback.txt', 'w', encoding='utf-8') as f:
    f.write('='*70 + '\n')
    f.write('INCORRECT RESULTS - FEEDBACK TEMPLATE\n')
    f.write('='*70 + '\n')
    f.write('\n')
    f.write('This file contains all incorrect predictions from the initial analysis.\n')
    f.write('Please provide feedback for each case to improve the system.\n')
    f.write('\n')
    f.write(f'Total incorrect results:\n')
    f.write(f'  - Text-based: {len(text_incorrect)} errors\n')
    f.write(f'  - Video-based: {len(video_incorrect)} errors\n')
    f.write('\n')
    f.write('='*70 + '\n')
    f.write('TEXT-BASED INCORRECT RESULTS ({} cases)\n'.format(len(text_incorrect)))
    f.write('='*70 + '\n')
    f.write('\n')

    for i, item in enumerate(text_incorrect, 1):
        f.write(f'[{i}] {item["error_type"]}\n')
        f.write(f'Video: {item["video"]}\n')
        f.write(f'Criteria: {item["criteria"]}\n')
        f.write(f'Predicted: {item["predicted"]} (should be {item["actual"]})\n')
        f.write(f'Feedback: \n')
        f.write('\n')

    f.write('\n')
    f.write('='*70 + '\n')
    f.write('VIDEO-BASED INCORRECT RESULTS ({} cases)\n'.format(len(video_incorrect)))
    f.write('='*70 + '\n')
    f.write('\n')

    for i, item in enumerate(video_incorrect, 1):
        f.write(f'[{i}] {item["error_type"]}\n')
        f.write(f'Video: {item["video"]}\n')
        f.write(f'Criteria: {item["criteria"]}\n')
        f.write(f'Predicted: {item["predicted"]} (should be {item["actual"]})\n')
        f.write(f'Feedback: \n')
        f.write('\n')

print(f'✓ Created incorrect_results_for_feedback.txt')
print(f'\nSummary:')
print(f'  Text-based errors: {len(text_incorrect)}')
for item in text_incorrect:
    print(f'    - {item["video"][:50]}... | {item["criteria"]} | {item["error_type"]}')
print(f'\n  Video-based errors: {len(video_incorrect)}')
for item in video_incorrect:
    print(f'    - {item["video"][:50]}... | {item["criteria"]} | {item["error_type"]}')
