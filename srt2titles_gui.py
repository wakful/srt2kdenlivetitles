import os, re, shutil, json
from datetime import datetime
from xml.sax.saxutils import escape
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinterdnd2 import TkinterDnD, DND_FILES

FPS = 60.0
CONFIG_FILE = "config.json"

TIME_RE = re.compile(r"(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,\.]\d{3})")
CONTENT_RE = re.compile(r'(<content\b[^>]*>)(.*?)(</content>)', re.DOTALL|re.IGNORECASE)
DUR_RE = re.compile(r'\bduration="\d+"')
OUT_RE = re.compile(r'\bout="\d+"')

def t2s(t):
    t = t.replace(",", ".")
    dt = datetime.strptime(t, "%H:%M:%S.%f")
    return dt.hour*3600 + dt.minute*60 + dt.second + dt.microsecond/1e6

def build_xml(template, frames, raw_text):
    xml = template
    if DUR_RE.search(xml):
        xml = DUR_RE.sub(f'duration="{frames}"', xml, count=1)
    else:
        xml = xml.replace("<kdenlivetitle", f'<kdenlivetitle duration="{frames}"', 1)
    out_frame = max(0, frames - 1)
    if OUT_RE.search(xml):
        xml = OUT_RE.sub(f'out="{out_frame}"', xml, count=1)
    else:
        xml = xml.replace("<kdenlivetitle", f'<kdenlivetitle out="{out_frame}"', 1)
    esc = escape(raw_text).replace("\n", " ") if raw_text else ""
    if CONTENT_RE.search(xml):
        xml = CONTENT_RE.sub(r'\1' + esc + r'\3', xml, count=1)
    else:
        xml = xml.replace("</item>", f'    <content>{esc}</content>\n  </item>', 1)
    return xml

def convert_files(srt_path, tpl_path):
    with open(srt_path, "r", encoding="utf-8-sig") as fh:
        raw = fh.read()
    with open(tpl_path, "r", encoding="utf-8") as fh:
        template = fh.read()

    blocks = re.split(r"\n\s*\n", raw.strip())
    entries = []
    for block in blocks:
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if len(lines) < 2:
            continue
        time_line = next((ln for ln in lines if TIME_RE.search(ln)), None)
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

    out_dir = filedialog.askdirectory(title="Choose output folder for Kdenlive titles")
    if not out_dir:
        return

    if os.path.exists(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(out_dir)

    pad = len(str(len(entries)*2))
    n = 1
    prev_end = 0.0

    for start, end, text in entries:
        blank_frames = int(round((start - prev_end) * FPS))
        if blank_frames > 0:
            fname = str(n).zfill(pad) + "_.kdenlivetitle"
            with open(os.path.join(out_dir, fname), "w", encoding="utf-8") as fh:
                fh.write(build_xml(template, blank_frames, ""))
            n += 1
        dur = max(1, int(round((end - start) * FPS)))
        fname = str(n).zfill(pad) + ".kdenlivetitle"
        with open(os.path.join(out_dir, fname), "w", encoding="utf-8") as fh:
            fh.write(build_xml(template, dur, text))
        n += 1
        prev_end = end
    messagebox.showinfo("Done", f"Titles saved in:\n{out_dir}")

def load_last_template():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)
            return data.get("template")
    return None

def save_last_template(path):
    with open(CONFIG_FILE, "w") as f:
        json.dump({"template": path}, f)

def select_template():
    file = filedialog.askopenfilename(filetypes=[("Kdenlive Title", "*.kdenlivetitle")])
    if file:
        tpl_var.set(file)
        save_last_template(file)

def select_srt():
    file = filedialog.askopenfilename(filetypes=[("Subtitle File", "*.srt")])
    if file:
        srt_var.set(file)

def on_convert():
    srt, tpl = srt_var.get(), tpl_var.get()
    if not srt or not tpl:
        messagebox.showwarning("Missing file", "Please set both .srt and .kdenlivetitle files")
        return
    convert_files(srt, tpl)

# --- UI ---
root = TkinterDnD.Tk()
root.title("SRT → Kdenlive Titles")

srt_var = tk.StringVar()
tpl_var = tk.StringVar(value=load_last_template() or "")

tk.Label(root, text="SRT File:").pack(pady=5)
srt_entry = tk.Entry(root, textvariable=srt_var, width=50)
srt_entry.pack()
tk.Button(root, text="Browse .srt", command=select_srt).pack(pady=2)

tk.Label(root, text="Template File:").pack(pady=5)
tpl_entry = tk.Entry(root, textvariable=tpl_var, width=50)
tpl_entry.pack()
tk.Button(root, text="Select Template", command=select_template).pack(pady=2)

tk.Button(root, text="Convert", command=on_convert).pack(pady=10)

# --- Drag and Drop handling ---
def handle_drop(event):
    path = event.data.strip("{}")
    if path.lower().endswith(".srt"):
        srt_var.set(path)
    elif path.lower().endswith(".kdenlivetitle"):
        tpl_var.set(path)
        save_last_template(path)

root.drop_target_register(DND_FILES)
root.dnd_bind("<<Drop>>", handle_drop)

root.geometry("400x250")
root.mainloop()
