import json

# Load initial results
with open('experiment_results/initial_5crit_results_20251125_152732.json', 'r') as f:
    initial = json.load(f)

# Load post-feedback results
with open('experiment_results/feedback_experiment_20251125_210404.json', 'r') as f:
    feedback_exp = json.load(f)

# Load ground truth
with open('ground_truth_template.json', 'r') as f:
    ground_truth = json.load(f)

# Get initial predictions for text and video
initial_text_results = initial['analysis']['accuracy']['text_based']['results']
initial_video_results = initial['analysis']['accuracy']['video_based']['results']

# Videos that had feedback
feedback_videos = [
    ("''its okay'' WYM YOU JUST MADE ME JUMP #ethanwinters #residentevil7-pxNvqepEYOY.mp4", 'violence'),
    ('HEISENBERG\'S FIRST DEAL!🤑｜ Breaking Bad #shorts-Ix3XLxar5Uo.mp4', 'language'),
    ('발매한지 한 달도 안 돼서 특이점이 와버린 게임 모드-jo13504_u9A.mp4', 'violence'),
    ('BOOTED by Gordon Ramsay？! #shorts #gordonramsay #fyp-gT-ZPJW1j1c.mp4', 'violence'),
    ('Thomas Shelby Smoking 4k 🚬 ⧸⧸#thomasshelby #peakyblinders #smoke #asmr #4k #shorts-Y50kB2YrMdI.mp4', 'drugs'),
    ('first f bomb in marvel-5vl1dJPsFTo.mp4', 'language'),
    ('where\'s my daughter scene ｜ prisoners (2013)-nY3Nsri3NOA.mp4', 'language'),
    ('클래식하고 묵직합니다 #독전 #김주혁 #진서연 #조진웅-W3pQ3Z9JrI0.mp4', 'sexuality'),
    ('클래식하고 묵직합니다 #독전 #김주혁 #진서연 #조진웅-W3pQ3Z9JrI0.mp4', 'horror')
]

print('='*80)
print('DID FEEDBACK ACTUALLY CHANGE THE PREDICTIONS?')
print('='*80)
print()

changed_text = 0
changed_video = 0
fixed_text = 0
fixed_video = 0
broke_text = 0
broke_video = 0

for video, criteria in feedback_videos:
    gt = ground_truth.get(video, {}).get(criteria, '?')

    # Initial predictions
    init_text = initial_text_results.get(video, {}).get(criteria, '?')
    init_video = initial_video_results.get(video, {}).get(criteria, '?')

    # Post-feedback predictions
    post_text = feedback_exp['text_input']['results'].get(video, {}).get(criteria, '?')
    post_video = feedback_exp['video_input']['results'].get(video, {}).get(criteria, '?')

    text_changed = init_text != post_text
    video_changed = init_video != post_video

    # Fixed: was wrong, now correct
    text_fixed = (init_text != gt) and (post_text == gt)
    video_fixed = (init_video != gt) and (post_video == gt)

    # Broke: was correct, now wrong
    text_broke = (init_text == gt) and (post_text != gt)
    video_broke = (init_video == gt) and (post_video != gt)

    if text_changed:
        changed_text += 1
    if video_changed:
        changed_video += 1
    if text_fixed:
        fixed_text += 1
    if video_fixed:
        fixed_video += 1
    if text_broke:
        broke_text += 1
    if video_broke:
        broke_video += 1

    # Print details
    print(f'{video[:60]}... | {criteria}')
    print(f'  Ground truth: {gt}')

    text_status = ""
    if text_fixed:
        text_status = "✅ FIXED"
    elif text_broke:
        text_status = "⚠️  BROKE"
    elif post_text != gt:
        text_status = "❌ STILL WRONG"
    else:
        text_status = "✓ was correct"

    video_status = ""
    if video_fixed:
        video_status = "✅ FIXED"
    elif video_broke:
        video_status = "⚠️  BROKE"
    elif post_video != gt:
        video_status = "❌ STILL WRONG"
    else:
        video_status = "✓ was correct"

    print(f'  Text:  {init_text} → {post_text}  {text_status}')
    print(f'  Video: {init_video} → {post_video}  {video_status}')
    print()

print('='*80)
print('SUMMARY')
print('='*80)
print(f'Text predictions that changed: {changed_text}/9')
print(f'  - Fixed (wrong → correct): {fixed_text}')
print(f'  - Broke (correct → wrong): {broke_text}')
print()
print(f'Video predictions that changed: {changed_video}/9')
print(f'  - Fixed (wrong → correct): {fixed_video}')
print(f'  - Broke (correct → wrong): {broke_video}')
