import os
import sys
import json
import subprocess
import re
import math
import whisper
import budoux
import onnxruntime
import numpy as np
import urllib.request
import shutil
from xml.sax.saxutils import escape

# 設定
FFMPEG_PATH = r"C:\Users\darumaya\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1-full_build\bin\ffmpeg.exe"
FFPROBE_PATH = r"C:\Users\darumaya\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1-full_build\bin\ffprobe.exe"
INPUT_VIDEO = r"C:\Users\darumaya\Documents\video-edit\input\test.mov"
TEMP_DIR = "temp"
OUTPUT_DIR = "output"
REMOTION_DIR = r"C:\Users\darumaya\antigravity\20260323auto_edit\temp_auto_edit\remotion-project"
VAD_MODEL_PATH = "silero_vad.onnx"

os.environ["PATH"] = os.path.dirname(FFMPEG_PATH) + os.pathsep + os.environ["PATH"]

def execute_command_list(args):
    executable = args[0]
    if executable == "ffmpeg": executable = FFMPEG_PATH
    if executable == "ffprobe": executable = FFPROBE_PATH
    tmp_args = list(args)
    tmp_args[0] = executable
    print(f"Executing: {' '.join(tmp_args)}")
    result = subprocess.run(tmp_args, capture_output=True, text=True, encoding='utf-8')
    return result.returncode == 0, result.stderr, result.stdout

def format_srt_time(seconds):
    td = float(seconds)
    hrs = int(td / 3600)
    mins = int((td % 3600) / 60)
    secs = int(td % 60)
    msecs = int((td * 1000) % 1000)
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{msecs:03d}"

def generate_srt(subtitles, output_path):
    with open(output_path, "w", encoding="utf-8") as f:
        for i, sub in enumerate(subtitles):
            f.write(f"{i+1}\n")
            f.write(f"{format_srt_time(sub['start'])} --> {format_srt_time(sub['end'])}\n")
            f.write(f"{' '.join(sub['lines'])}\n\n")

def generate_xml(speech_ts, input_path, output_path, w, h):
    # FCP7 XML Base
    file_uri = f"file://localhost/{os.path.abspath(input_path).replace(os.sep, '/')}"
    file_name = os.path.basename(input_path)
    fps = 30
    
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<xmeml version="4">
<sequence id="sequence-1">
    <name>AI_AUTO_CUT_TIMELINE</name>
    <duration>{int(sum(ts['end']-ts['start'] for ts in speech_ts) / 16000 * fps)}</duration>
    <rate><timebase>{fps}</timebase><ntsc>FALSE</ntsc></rate>
    <media>
        <video>
            <format><samplecharacteristics><width>{w}</width><height>{h}</height></samplecharacteristics></format>
            <track>
    """
    
    curr_frame = 0
    for i, ts in enumerate(speech_ts):
        start_f = int(ts['start'] / 16000 * fps)
        end_f = int(ts['end'] / 16000 * fps)
        dur = end_f - start_f
        if dur <= 0: continue
        
        xml += f"""
                <clipitem id="clipitem-{i}">
                    <name>{escape(file_name)}</name>
                    <duration>{dur}</duration>
                    <rate><timebase>{fps}</timebase></rate>
                    <in>{start_f}</in>
                    <out>{end_f}</out>
                    <start>{curr_frame}</start>
                    <end>{curr_frame + dur}</end>
                    <file id="file-1">
                        <name>{escape(file_name)}</name>
                        <pathurl>{file_uri}</pathurl>
                    </file>
                </clipitem>"""
        curr_frame += dur
        
    xml += """
            </track>
        </video>
    </media>
</sequence>
</xmeml>
    """
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(xml)

def split_text_pro(text, max_total=30, line_limit=18):
    parser = budoux.load_default_japanese_parser()
    temp_parts = [text] if len(text) <= max_total else []
    if len(text) > max_total:
        chunks = parser.parse(text)
        current = ""
        for c in chunks:
            if len(current + c) <= max_total: current += c
            else:
                if current: temp_parts.append(current)
                current = c
        if current: temp_parts.append(current)

    results = []
    for p in temp_parts:
        target = p
        p_list = []
        while len(target) > max_total:
            p_list.append(target[:max_total])
            target = target[max_total:]
        if target: p_list.append(target)
        for sub_p in p_list:
            lines = []
            if len(sub_p) <= line_limit: lines = [sub_p]
            else:
                chunks = parser.parse(sub_p)
                mid = len(sub_p) / 2
                first = ""
                for c in chunks:
                    if len(first + c) < mid + (len(c)/2): first += c
                    else: break
                if not first: first = sub_p[:len(sub_p)//2]
                second = sub_p[len(first):]
                lines = [first, second]
            max_l = max(len(l) for l in lines)
            results.append({"lines": lines, "fontSize": 72 if max_l <= 8 else 64 if max_l <= 12 else 56 if max_l <= 18 else 48 if max_l <= 24 else 42})
    return results

def get_speech_timestamps_onnx(wav_path):
    if not os.path.exists(VAD_MODEL_PATH):
        urllib.request.urlretrieve("https://huggingface.co/onnx-community/silero-vad/resolve/main/onnx/model.onnx", VAD_MODEL_PATH)
    session = onnxruntime.InferenceSession(VAD_MODEL_PATH)
    import soundfile as sf
    audio, sr = sf.read(wav_path)
    window_size = 512
    speech_segments = []
    active, start_sample, audio = False, 0, audio.astype(np.float32)
    state = np.zeros((2, 1, 128), dtype=np.float32)
    sr_val = np.array([16000], dtype=np.int64)
    for i in range(0, len(audio), window_size):
        chunk = audio[i:i+window_size]
        if len(chunk) < window_size: break
        ort_inputs = {'input': chunk.reshape(1, window_size), 'state': state, 'sr': sr_val}
        out, state = session.run(None, ort_inputs)
        if out[0][0] > 0.5 and not active: active, start_sample = True, i
        elif out[0][0] < 0.35 and active: active = False; speech_segments.append({'start': start_sample, 'end': i})
    if active: speech_segments.append({'start': start_sample, 'end': len(audio)})
    return speech_segments

def main():
    os.makedirs(TEMP_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print("--- Step 1: Audio Extraction ---")
    execute_command_list(["ffmpeg", "-y", "-i", INPUT_VIDEO, "-ar", "16000", "-ac", "1", "temp/audio_16k.wav"])

    print("--- Step 2: Silence Cut (Chunked) ---")
    speech_ts = get_speech_timestamps_onnx("temp/audio_16k.wav")
    if not speech_ts: return
    chunk_size = 10
    chunk_files = []
    for i in range(0, len(speech_ts), chunk_size):
        chunk = speech_ts[i:i+chunk_size]
        select_parts = [f"between(t,{ts['start']/16000},{ts['end']/16000})" for ts in chunk]
        out_chunk = f"temp/chunk_{i//chunk_size}.mp4"
        execute_command_list(["ffmpeg", "-y", "-i", INPUT_VIDEO, "-vf", f"select='{'+'.join(select_parts)}',setpts=N/FRAME_RATE/TB", "-af", f"aselect='{'+'.join(select_parts)}',asetpts=N/SR/TB", out_chunk])
        chunk_files.append(out_chunk)
    
    with open("temp/concat_list.txt", "w") as f:
        for cf in chunk_files: f.write(f"file '{os.path.abspath(cf)}'\n")
    execute_command_list(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", os.path.abspath("temp/concat_list.txt"), "-c", "copy", "temp/cut_video.mp4"])

    print("--- Step 3: Audio Resync ---")
    execute_command_list(["ffmpeg", "-y", "-i", "temp/cut_video.mp4", "-ar", "44100", "-ac", "1", "temp/voice_audio.wav"])

    print("--- Step 4-5: Whisper & Subtitles ---")
    model = whisper.load_model("large-v3")
    result = model.transcribe("temp/voice_audio.wav", language="ja", word_timestamps=True)
    final_subs = []
    for seg in result["segments"]:
        sub_items = split_text_pro(seg["text"].strip())
        dur, total_chars, curr_start = seg["end"] - seg["start"], sum(len("".join(s["lines"])) for s in sub_items), seg["start"]
        for s in sub_items:
            s_dur = (len("".join(s["lines"])) / total_chars) * dur if total_chars > 0 else dur
            final_subs.append({"start": curr_start, "end": curr_start + s_dur, "lines": s["lines"], "fontSize": s["fontSize"]})
            curr_start += s_dur

    with open("temp/subtitles.json", "w", encoding="utf-8") as f: json.dump(final_subs, f, ensure_ascii=False, indent=2)

    print("--- Step 6: Metadata & Conversion ---")
    execute_command_list(["ffmpeg", "-y", "-i", "temp/cut_video.mp4", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30", "-preset", "fast", "-crf", "18", "temp/cut_video_final.mp4"])
    _, _, probe_out = execute_command_list(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "json", "temp/cut_video_final.mp4"])
    w, h = json.loads(probe_out)["streams"][0]["width"], json.loads(probe_out)["streams"][0]["height"]

    print("--- Step 11: Premiere Pro Export ---")
    generate_srt(final_subs, "output/subtitles.srt")
    generate_xml(speech_ts, INPUT_VIDEO, "output/premiere_sequence.xml", w, h)

    print("--- Step 7-10: Remotion & Render ---")
    for f in ["cut_video_final.mp4", "voice_audio.wav", "subtitles.json"]:
        shutil.copy(f"temp/{f}", os.path.join(REMOTION_DIR, "public", f.replace("_final", "")))
    
    total_frames = int(final_subs[-1]["end"] * 30) + 30
    root_tsx = f'import "./index.css";\nimport {{ Composition }} from "remotion";\nimport {{ MainVideo }} from "./MainVideo";\n\nexport const RemotionRoot: React.FC = () => {{\n  return (<Composition id="MainVideo" component={{MainVideo}} durationInFrames={{{total_frames}}} fps={{30}} width={{{w}}} height={{{h}}} />);\n}};\n'
    with open(os.path.join(REMOTION_DIR, "src", "Root.tsx"), "w", encoding="utf-8") as f: f.write(root_tsx)

    os.chdir(REMOTION_DIR)
    subprocess.run("npx.cmd remotion render MainVideo ../../output/final.mp4 --timeout=120000", shell=True)
    print("\n--- Done ---")
    print(f"Final XML (Premiere sequence): output/premiere_sequence.xml")
    print(f"Final SRT (Premiere subtitles): output/subtitles.srt")

if __name__ == "__main__":
    main()
