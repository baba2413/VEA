import json

# Load results
with open('experiment_results/feedback_experiment_20251125_210404.json', 'r') as f:
    feedback = json.load(f)

with open('ground_truth_template.json', 'r') as f:
    gt = json.load(f)

# Count errors
text_results = feedback['text_input']['results']
video_results = feedback['video_input']['results']

print('='*70)
print('ERROR BREAKDOWN')
print('='*70)
print()

text_errors = []
video_errors = []
text_nulls = 0
video_nulls = 0

for video, criteria_results in text_results.items():
    gt_video = gt.get(video, {})
    for criteria, result in criteria_results.items():
        if result is None:
            print(f'⚠️  TEXT NULL: {video[:40]}... | {criteria}')
            text_nulls += 1
            continue
        gt_val = gt_video.get(criteria)
        if gt_val is not None and result != gt_val:
            text_errors.append((video, criteria, result, gt_val))

for video, criteria_results in video_results.items():
    gt_video = gt.get(video, {})
    for criteria, result in criteria_results.items():
        if result is None:
            print(f'⚠️  VIDEO NULL: {video[:40]}... | {criteria}')
            video_nulls += 1
            continue
        gt_val = gt_video.get(criteria)
        if gt_val is not None and result != gt_val:
            video_errors.append((video, criteria, result, gt_val))

print()
print(f'TEXT-INPUT ERRORS ({len(text_errors)} total):')
for video, criteria, result, gt_val in text_errors:
    print(f'  {video[:45]}... | {criteria}: predicted {result}, truth {gt_val}')

print()
print(f'VIDEO-INPUT ERRORS ({len(video_errors)} total):')
for video, criteria, result, gt_val in video_errors:
    print(f'  {video[:45]}... | {criteria}: predicted {result}, truth {gt_val}')

print()
print('='*70)
print('CURRENT STATE')
print('='*70)
print(f'Text: {feedback["text_input"]["accuracy"]["correct"]}/{feedback["text_input"]["accuracy"]["total_samples"]} = {feedback["text_input"]["accuracy"]["accuracy"]*100:.1f}%')
print(f'  Errors: {len(text_errors)}, Nulls: {text_nulls}')
print(f'Video: {feedback["video_input"]["accuracy"]["correct"]}/{feedback["video_input"]["accuracy"]["total_samples"]} = {feedback["video_input"]["accuracy"]["accuracy"]*100:.1f}%')
print(f'  Errors: {len(video_errors)}, Nulls: {video_nulls}')

print()
print('='*70)
print('SCENARIOS')
print('='*70)
print()
print('Scenario 1: Add missing video (5 samples), assume all CORRECT')
text_if_all_correct = (92 + 5) / 100
video_if_all_correct = (91 + 5) / 100
print(f'  Text: (92+5)/100 = {text_if_all_correct*100:.1f}%')
print(f'  Video: (91+5)/100 = {video_if_all_correct*100:.1f}%')

print()
print('Scenario 2: Add missing video, AND fix the null result')
print(f'  Text currently has {text_nulls} null result')
print(f'  If that null was correct: (92+1+5)/100 = 98.0%')
print(f'  If that null was wrong: (92+0+5)/100 = 97.0%')

print()
print('Scenario 3: YOUR CALCULATION (Text 99%, Video 97%)')
print('  For text to be 99%: need 99/100 correct')
print(f'    Current correct: 92')
print(f'    Need: +7 more correct')
print(f'    = Fix {len(text_errors)} current errors + {text_nulls} null + add 5 missing (all correct) + fix {7-3-1-5} other')
print()
print('  For video to be 97%: need 97/100 correct')
print(f'    Current correct: 91')
print(f'    Need: +6 more correct')
print(f'    = Fix 2 of {len(video_errors)} current errors + add 5 missing (all correct) + fix {6-2-5} other')

print()
print('='*70)
print('QUESTION FOR USER')
print('='*70)
print('Which specific "failure in video analysis" are you referring to?')
print('  (a) The missing video file (5 missing samples)')
print('  (b) The text-input null result for drugs (1 sample)')
print('  (c) Some other failure?')
