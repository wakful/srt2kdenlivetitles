import os
import re
import json
from datetime import datetime
from xml.sax.saxutils import escape
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinterdnd2 import TkinterDnD, DND_FILES

FRAMES_PER_SECOND = 60.0
CONFIG_FILE_PATH = "config.json"

TIME_PATTERN = re.compile(r"(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,\.]\d{3})")
CONTENT_PATTERN = re.compile(r'(<content\b[^>]*>)(.*?)(</content>)', re.DOTALL | re.IGNORECASE)
DURATION_PATTERN = re.compile(r'\bduration="\d+"')
OUTPUT_FRAME_PATTERN = re.compile(r'\bout="\d+"')

def convert_time_to_seconds(time_string):
    time_string = time_string.replace(",", ".")
    datetime_obj = datetime.strptime(time_string, "%H:%M:%S.%f")
    return datetime_obj.hour * 3600 + datetime_obj.minute * 60 + datetime_obj.second + datetime_obj.microsecond / 1e6

def construct_xml_template(template_content, frame_count, subtitle_text):
    xml_content = template_content
    if DURATION_PATTERN.search(xml_content):
        xml_content = DURATION_PATTERN.sub(f'duration="{frame_count}"', xml_content, count=1)
    else:
        xml_content = xml_content.replace("<kdenlivetitle", f'<kdenlivetitle duration="{frame_count}"', 1)
    
    output_frame = max(0, frame_count - 1)
    if OUTPUT_FRAME_PATTERN.search(xml_content):
        xml_content = OUTPUT_FRAME_PATTERN.sub(f'out="{output_frame}"', xml_content, count=1)
    else:
        xml_content = xml_content.replace("<kdenlivetitle", f'<kdenlivetitle out="{output_frame}"', 1)
    
    escaped_text = escape(subtitle_text).replace("\n", " ") if subtitle_text else ""
    if CONTENT_PATTERN.search(xml_content):
        xml_content = CONTENT_PATTERN.sub(r'\1' + escaped_text + r'\3', xml_content, count=1)
    else:
        xml_content = xml_content.replace("</item>", f'    <content>{escaped_text}</content>\n  </item>', 1)
    
    return xml_content

def process_subtitle_files(subtitle_file_path, template_file_path):
    with open(subtitle_file_path, "r", encoding="utf-8-sig") as file:
        subtitle_content = file.read()
    with open(template_file_path, "r", encoding="utf-8") as file:
        template_content = file.read()

    subtitle_blocks = re.split(r"\n\s*\n", subtitle_content.strip())
    subtitle_entries = []
    for block in subtitle_blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) < 2:
            continue
        time_line = next((line for line in lines if TIME_PATTERN.search(line)), None)
        if not time_line:
            continue
        match = TIME_PATTERN.search(time_line)
        if not match:
            continue
        start_time, end_time = convert_time_to_seconds(match.group(1)), convert_time_to_seconds(match.group(2))
        subtitle_text = " ".join(lines[2:]) if len(lines) > 2 else ""
        subtitle_entries.append((start_time, end_time, subtitle_text))

    if not subtitle_entries:
        raise SystemExit("No subtitles parsed.")

    output_directory = filedialog.askdirectory(title="Select output folder for Kdenlive titles")
    if not output_directory:
        return

    titles_directory = os.path.join(output_directory, "kdenlive titles")
    os.makedirs(titles_directory, exist_ok=True)

    digit_padding = len(str(len(subtitle_entries) * 2))
    entry_counter = 1
    previous_end_time = 0.0

    for start_time, end_time, subtitle_text in subtitle_entries:
        blank_frame_count = int(round((start_time - previous_end_time) * FRAMES_PER_SECOND))
        if blank_frame_count > 0:
            file_name = f"{str(entry_counter).zfill(digit_padding)}_blank.kdenlivetitle"
            with open(os.path.join(titles_directory, file_name), "w", encoding="utf-8") as file:
                file.write(construct_xml_template(template_content, blank_frame_count, ""))
            entry_counter += 1
        
        duration_frames = max(1, int(round((end_time - start_time) * FRAMES_PER_SECOND)))
        file_name = f"{str(entry_counter).zfill(digit_padding)}.kdenlivetitle"
        with open(os.path.join(titles_directory, file_name), "w", encoding="utf-8") as file:
            file.write(construct_xml_template(template_content, duration_frames, subtitle_text))
        entry_counter += 1
        previous_end_time = end_time
    
    messagebox.showinfo("Success", f"Titles saved in:\n{titles_directory}")

def load_previous_template():
    if os.path.exists(CONFIG_FILE_PATH):
        with open(CONFIG_FILE_PATH, "r") as file:
            data = json.load(file)
            return data.get("template_path")
    return None

def save_template_path(path):
    with open(CONFIG_FILE_PATH, "w") as file:
        json.dump({"template_path": path}, file)

def select_template_file():
    file_path = filedialog.askopenfilename(filetypes=[("Kdenlive Title", "*.kdenlivetitle")])
    if file_path:
        template_path_var.set(file_path)
        save_template_path(file_path)

def select_subtitle_file():
    file_path = filedialog.askopenfilename(filetypes=[("Subtitle File", "*.srt")])
    if file_path:
        subtitle_path_var.set(file_path)

def handle_convert_button():
    subtitle_path, template_path = subtitle_path_var.get(), template_path_var.get()
    if not subtitle_path or not template_path:
        messagebox.showwarning("Missing file", "Please select both .srt and .kdenlivetitle files")
        return
    process_subtitle_files(subtitle_path, template_path)

# --- UI Setup ---
root = TkinterDnD.Tk()
root.title("SRT to Kdenlive Titles Converter")

subtitle_path_var = tk.StringVar()
template_path_var = tk.StringVar(value=load_previous_template() or "")

tk.Label(root, text="Subtitle File:").pack(pady=5)
subtitle_entry = tk.Entry(root, textvariable=subtitle_path_var, width=50)
subtitle_entry.pack()
tk.Button(root, text="Browse .srt", command=select_subtitle_file).pack(pady=2)

tk.Label(root, text="Template File:").pack(pady=5)
template_entry = tk.Entry(root, textvariable=template_path_var, width=50)
template_entry.pack()
tk.Button(root, text="Select Template", command=select_template_file).pack(pady=2)

tk.Button(root, text="Convert", command=handle_convert_button).pack(pady=10)

# --- Drag and Drop Handling ---
def handle_file_drop(event):
    file_path = event.data.strip("{}")
    if file_path.lower().endswith(".srt"):
        subtitle_path_var.set(file_path)
    elif file_path.lower().endswith(".kdenlivetitle"):
        template_path_var.set(file_path)
        save_template_path(file_path)

root.drop_target_register(DND_FILES)
root.dnd_bind("<<Drop>>", handle_file_drop)

root.geometry("400x250")
root.mainloop()