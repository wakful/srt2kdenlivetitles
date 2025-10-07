#!/usr/bin/env python3
# srt2withblanks.py — simple, style-preserving, generates padding clips for gaps

import os, re, shutil
from datetime import datetime
from xml.sax.saxutils import escape

FPS = 60.0  # change to match your project framerate
OUT_DIR = "Kden_Titles"

TIME_RE = re.compile(r"(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,\.]\d{3})")
CONTENT_RE = re.compile(r'(<content\b[^>]*>)(.*?)(</content>)', re.DOTALL|re.IGNORECASE)
DUR_RE = re.compile(r'\bduration="\d+"')
OUT_RE = re.compile(r'\bout="\d+"')

def t2s(t):
    t = t.replace(",", ".")
    dt = datetime.strptime(t, "%H:%M:%S.%f")
    return dt.hour*3600 + dt.minute*60 + dt.second + dt.microsecond/1e6

def find_first(ext):
    for f in os.listdir("."):
        if f.lower().endswith(ext):
            return f
    return None

srt_file = find_first(".srt")
tpl_file = find_first(".kdenlivetitle")
if not srt_file or not tpl_file:
    raise SystemExit("Need one .srt and one .kdenlivetitle in the same folder.")

with open(srt_file, "r", encoding="utf-8-sig") as fh:
    raw = fh.read()
with open(tpl_file, "r", encoding="utf-8") as fh:
    template = fh.read()

# parse srt
blocks = re.split(r"\n\s*\n", raw.strip())
entries = []
for block in blocks:
    lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
    if len(lines) < 2:
        continue
    time_line = None
    for i in range(min(3, len(lines))):
        if TIME_RE.search(lines[i]):
            time_line = lines[i]; break
    if not time_line:
        for ln in lines:
            if TIME_RE.search(ln):
                time_line = ln; break
    if not time_line:
        continue
    m = TIME_RE.search(time_line)
    if not m:
        continue
    start, end = t2s(m.group(1)), t2s(m.group(2))
    text = " ".join(lines[2:]) if len(lines) > 2 else ""
    entries.append((start, end, text))

if not entries:
    raise SystemExit("No subtitles parsed.")

# prepare output dir
if os.path.exists(OUT_DIR):
    shutil.rmtree(OUT_DIR)
os.makedirs(OUT_DIR)

pad = len(str(len(entries)*2))  # *2 because blanks + text
n = 1
prev_end = 0.0

def build_xml(frames, raw_text):
    xml = template
    # set duration
    if DUR_RE.search(xml):
        xml = DUR_RE.sub(f'duration="{frames}"', xml, count=1)
    else:
        xml = xml.replace("<kdenlivetitle", f'<kdenlivetitle duration="{frames}"', 1)
    # set out
    out_frame = max(0, frames - 1)
    if OUT_RE.search(xml):
        xml = OUT_RE.sub(f'out="{out_frame}"', xml, count=1)
    else:
        xml = xml.replace("<kdenlivetitle", f'<kdenlivetitle out="{out_frame}"', 1)
    # replace first content block
    esc = escape(raw_text).replace("\n", " ") if raw_text else ""
    if CONTENT_RE.search(xml):
        xml = CONTENT_RE.sub(r'\1' + esc + r'\3', xml, count=1)
    else:
        xml = xml.replace("</item>", f'    <content>{esc}</content>\n  </item>', 1)
    return xml

for start, end, text in entries:
    # blank padding before this subtitle
    blank_frames = int(round((start - prev_end) * FPS))
    if blank_frames > 0:
        fname = str(n).zfill(pad) + "_.kdenlivetitle"
        with open(os.path.join(OUT_DIR, fname), "w", encoding="utf-8") as fh:
            fh.write(build_xml(blank_frames, ""))
        print(f"Wrote {fname} blank frames={blank_frames}")
        n += 1

    # subtitle clip
    dur = max(1, int(round((end - start) * FPS)))
    fname = str(n).zfill(pad) + ".kdenlivetitle"
    with open(os.path.join(OUT_DIR, fname), "w", encoding="utf-8") as fh:
        fh.write(build_xml(dur, text))
    print(f"Wrote {fname} frames={dur} text={'(empty)' if not text else text}")
    n += 1
    prev_end = end

print("Done. Import folder Kden_Titles into Kdenlive, sort by name, drag to timeline.")
