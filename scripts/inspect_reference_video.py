"""Sample a user-supplied reference clip locally; no uploads or UI inputs."""
import json
import sys
from pathlib import Path
import cv2
from PIL import Image, ImageDraw

source = Path(sys.argv[1])
target = Path(sys.argv[2])
target.mkdir(parents=True, exist_ok=True)
capture = cv2.VideoCapture(str(source))
if not capture.isOpened():
    raise RuntimeError('Reference video could not be opened')
fps = capture.get(cv2.CAP_PROP_FPS)
frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
duration = frames / fps
samples = []
for index in range(12):
    seconds = duration * index / 12
    capture.set(cv2.CAP_PROP_POS_MSEC, seconds * 1000)
    ok, frame = capture.read()
    if not ok:
        continue
    shot = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    shot.save(target / f'frame_{index:02d}.png')
    shot.thumbnail((360, 350))
    samples.append((seconds, shot))
capture.release()
sheet = Image.new('RGB', (1440, 1140), '#10141a')
draw = ImageDraw.Draw(sheet)
for index, (seconds, shot) in enumerate(samples):
    x, y = (index % 4) * 360, (index // 4) * 380
    sheet.paste(shot, (x + (360 - shot.width) // 2, y + 25))
    draw.text((x + 10, y + 5), f'{seconds:.1f}s', fill='white')
sheet.save(target / 'contact_sheet.jpg')
report = {'duration_seconds': duration, 'fps': fps, 'frames': frames, 'samples': len(samples)}
(target / 'metadata.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report))
