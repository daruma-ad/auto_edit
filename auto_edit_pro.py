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
FFMPEG_PATH = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE_PATH = shutil.which("ffprobe") or "ffprobe"
TEMP_DIR = "temp"
OUTPUT_DIR = "output"
REMOTION_DIR = os.path.join(os.getcwd(), "remotion-project")
VAD_MODEL_PATH = "silero_vad.onnx"
AUTO_RENDER = False  # Trueにすると自動でMP4までレンダリングを出力します
AUTO_FONT_SIZE = False   # 文字数に応じてフォントサイズを自動調整するか
REMOVE_PUNCTUATION = True # 「、」「。」をテロップから除去するか
SKIP_CUT = True          # Trueならカットをスキップ（テロップのみ）

# テロップ設定
MAX_CHARS_PER_LINE = 18      # 1行の最大文字数
MAX_CHARS_PER_SUBTITLE = 30  # 1つのテロップの合計最大文字数
FONT_SIZE_BASE = 72          # 基本のフォントサイズ
# AUTO_FONT_SIZE = False       # Trueなら文字数に合わせてサイズ調整、Falseなら一律固定

# 動画ファイルを自動検出
video_files = []
if os.path.exists("input"):
    video_files = [os.path.join("input", f) for f in os.listdir("input") if f.lower().endswith(('.mp4', '.mov', '.m4v'))]
INPUT_VIDEO = video_files[0] if video_files else os.path.join("input", "test.mp4")

if os.path.isabs(FFMPEG_PATH):
    os.environ["PATH"] = os.path.dirname(FFMPEG_PATH) + os.pathsep + os.environ["PATH"]

def execute_command_list(args):
    executable = args[0]
    if executable == "ffmpeg": executable = FFMPEG_PATH
    if executable == "ffprobe": executable = FFPROBE_PATH
    tmp_args = list(args)
    tmp_args[0] = executable
    print(f"Executing: {' '.join(tmp_args)}")
    if "ffprobe" in tmp_args[0]:
        result = subprocess.run(tmp_args, capture_output=True, text=True, encoding='utf-8')
        return result.returncode == 0, result.stderr, result.stdout
    else:
        result = subprocess.run(tmp_args, stdout=subprocess.DEVNULL, stderr=None)
        if result.returncode != 0:
            raise Exception(f"Command failed with exit code {result.returncode}: {' '.join(tmp_args)}")
        return result.returncode == 0, "", ""

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

def split_text_pro(text):
    """
    Budouxと文字数制限（MAX_CHARS_PER_LINE, MAX_CHARS_PER_SUBTITLE）を考慮して
    テキストを適切なテロップ単位（linesとfontSizeのリスト）に分割する。
    """
    if REMOVE_PUNCTUATION:
        text = text.replace("、", "").replace("。", "")
    
    # グローバル設定を使用
    max_total = MAX_CHARS_PER_SUBTITLE
    line_limit = MAX_CHARS_PER_LINE
    
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
                if not first: first = sub_p[:len(first or len(sub_p)//2)]
                second = sub_p[len(first):]
                lines = [first, second]
            
            # フォントサイズ
            if AUTO_FONT_SIZE:
                # 文字数に合わせて縮小（Baseを基準に調整）
                max_l = max(len(l) for l in lines)
                size_ratio = 1.0 if max_l <= 8 else 0.85 if max_l <= 12 else 0.75 if max_l <= 18 else 0.6 if max_l <= 24 else 0.5
                font_size = int(FONT_SIZE_BASE * size_ratio)
            else:
                # 一律固定
                font_size = FONT_SIZE_BASE
            
            results.append({"lines": lines, "fontSize": font_size})
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
    # デフォルト設定で実行
    process_video()

def process_video(
    input_video=None,
    skip_cut=SKIP_CUT,
    max_chars_per_line=MAX_CHARS_PER_LINE,
    max_chars_per_subtitle=MAX_CHARS_PER_SUBTITLE,
    font_size_base=FONT_SIZE_BASE,
    auto_font_size=AUTO_FONT_SIZE,
    subtitle_bottom=40,
    remove_punctuation=REMOVE_PUNCTUATION
):
    # グローバル設定を一時的に上書きするための仕組み（関数内ローカル変数として扱う）
    global MAX_CHARS_PER_LINE, MAX_CHARS_PER_SUBTITLE, FONT_SIZE_BASE, AUTO_FONT_SIZE, INPUT_VIDEO, REMOVE_PUNCTUATION
    
    # 引数があれば上書き
    local_max_line = max_chars_per_line
    local_max_sub = max_chars_per_subtitle
    local_font_base = font_size_base
    local_auto_size = auto_font_size
    
    # 既存のロジックがグローバル変数を参照しているためのパッチ
    # 本来は引数を順次渡すべきだが、最小限の修正に留める
    orig_max_line = MAX_CHARS_PER_LINE
    orig_max_sub = MAX_CHARS_PER_SUBTITLE
    orig_font_base = FONT_SIZE_BASE
    orig_remove_punc = REMOVE_PUNCTUATION

    MAX_CHARS_PER_LINE = local_max_line
    MAX_CHARS_PER_SUBTITLE = local_max_sub
    FONT_SIZE_BASE = local_font_base
    AUTO_FONT_SIZE = local_auto_size
    REMOVE_PUNCTUATION = remove_punctuation
    orig_auto_size = AUTO_FONT_SIZE
    
    MAX_CHARS_PER_LINE = local_max_line
    MAX_CHARS_PER_SUBTITLE = local_max_sub
    FONT_SIZE_BASE = local_font_base
    AUTO_FONT_SIZE = local_auto_size

    target_video = input_video if input_video else INPUT_VIDEO

    os.makedirs(TEMP_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print("--- Step 1: Audio Extraction ---")
    execute_command_list(["ffmpeg", "-y", "-i", target_video, "-ar", "16000", "-ac", "1", "temp/audio_16k.wav"])

    print("--- Step 2: Whisper Transcription (small) ---")
    model = whisper.load_model("small")
    whisper_result = model.transcribe("temp/audio_16k.wav", language="ja", word_timestamps=True)
    segments = whisper_result["segments"]
    if not segments:
        print("ERROR: No speech segments found.")
        return

    print(f"    Found {len(segments)} speech segments.")

    if skip_cut:
        print("--- Step 3: Skip Cut (Copy Original) ---")
        shutil.copy(target_video, "temp/cut_video.mp4")
    else:
        print("--- Step 3: Cut Video (trim+concat) ---")
        n = len(segments)
        filter_parts = []
        for i, seg in enumerate(segments):
            filter_parts.append(f"[0:v]trim=start={seg['start']}:end={seg['end']},setpts=PTS-STARTPTS[v{i}]")
            filter_parts.append(f"[0:a]atrim=start={seg['start']}:end={seg['end']},asetpts=PTS-STARTPTS[a{i}]")
        concat_inputs = "".join(f"[v{i}][a{i}]" for i in range(n))
        filter_parts.append(f"{concat_inputs}concat=n={n}:v=1:a=1[outv][outa]")
        filter_complex = ";".join(filter_parts)
        
        filter_file = os.path.abspath("temp/filter_complex.txt")
        with open(filter_file, "w") as f:
            f.write(filter_complex)
        
        cmd = [FFMPEG_PATH, "-y", "-i", target_video, "-filter_complex_script", filter_file, "-map", "[outv]", "-map", "[outa]", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30", "-preset", "fast", "temp/cut_video.mp4"]
        r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=None)
        if r.returncode != 0:
            raise Exception(f"FFmpeg cut failed: {r.returncode}")

    print("--- Step 4: Audio Resync ---")
    execute_command_list(["ffmpeg", "-y", "-i", "temp/cut_video.mp4", "-ar", "44100", "-ac", "1", "temp/voice_audio.wav"])

    print("--- Step 5: Generate Subtitles ---")
    if skip_cut:
        final_subs = []
        for seg in segments:
            sub_items = split_text_pro(seg["text"].strip())
            orig_dur = seg["end"] - seg["start"]
            total_chars = sum(len("".join(s["lines"])) for s in sub_items)
            curr = seg["start"]
            for s in sub_items:
                s_dur = (len("".join(s["lines"])) / total_chars) * orig_dur if total_chars > 0 else orig_dur
                final_subs.append({"start": curr, "end": curr + s_dur, "lines": s["lines"], "fontSize": s["fontSize"], "bottom": subtitle_bottom})
                curr += s_dur
    else:
        cut_offset = 0.0
        seg_map = []
        for seg in segments:
            seg_map.append((seg["start"], seg["end"], cut_offset))
            cut_offset += seg["end"] - seg["start"]

        def remap_time(orig_t):
            for orig_s, orig_e, cut_s in seg_map:
                if orig_s <= orig_t <= orig_e:
                    return cut_s + (orig_t - orig_s)
            best = 0.0
            for orig_s, orig_e, cut_s in seg_map:
                if orig_t < orig_s: return cut_s
                best = cut_s + (orig_e - orig_s)
            return best

        final_subs = []
        for seg in segments:
            sub_items = split_text_pro(seg["text"].strip())
            orig_dur = seg["end"] - seg["start"]
            total_chars = sum(len("".join(s["lines"])) for s in sub_items)
            cut_start = remap_time(seg["start"])
            curr = cut_start
            for s in sub_items:
                s_dur = (len("".join(s["lines"])) / total_chars) * orig_dur if total_chars > 0 else orig_dur
                final_subs.append({"start": curr, "end": curr + s_dur, "lines": s["lines"], "fontSize": s["fontSize"], "bottom": subtitle_bottom})
                curr += s_dur

    with open("temp/subtitles.json", "w", encoding="utf-8") as f: json.dump(final_subs, f, ensure_ascii=False, indent=2)

    print("--- Step 6: Metadata & Conversion ---")
    execute_command_list(["ffmpeg", "-y", "-i", "temp/cut_video.mp4", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30", "-preset", "fast", "-crf", "18", "temp/cut_video_final.mp4"])
    _, _, probe_out = execute_command_list(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "json", "temp/cut_video_final.mp4"])
    w, h = json.loads(probe_out)["streams"][0]["width"], json.loads(probe_out)["streams"][0]["height"]

    print("--- Step 7: Premiere Pro Export ---")
    whisper_ts = [{"start": int(seg["start"] * 16000), "end": int(seg["end"] * 16000)} for seg in segments]
    generate_srt(final_subs, "output/subtitles.srt")
    generate_xml(whisper_ts, target_video, "output/premiere_sequence.xml", w, h)

    print("--- Step 7-10: Remotion & Render ---")
    os.makedirs(os.path.join(REMOTION_DIR, "public"), exist_ok=True)
    shutil.copy("temp/cut_video_final.mp4", os.path.join(REMOTION_DIR, "public", "cut_video.mp4"))
    shutil.copy("temp/voice_audio.wav", os.path.join(REMOTION_DIR, "public", "voice_audio.wav"))
    shutil.copy("temp/subtitles.json", os.path.join(REMOTION_DIR, "public", "subtitles.json"))
    
    total_frames = int(final_subs[-1]["end"] * 30) + 30
    root_tsx = f'import "./index.css";\nimport {{ Composition }} from "remotion";\nimport {{ MainVideo }} from "./MainVideo";\n\nexport const RemotionRoot: React.FC = () => {{\n  return (<Composition id="MainVideo" component={{MainVideo}} durationInFrames={{{total_frames}}} fps={{30}} width={{{w}}} height={{{h}}} />);\n}};\n'
    with open(os.path.join(REMOTION_DIR, "src", "Root.tsx"), "w", encoding="utf-8") as f: f.write(root_tsx)

    # 設定を元に戻す
    MAX_CHARS_PER_LINE = orig_max_line
    MAX_CHARS_PER_SUBTITLE = orig_max_sub
    FONT_SIZE_BASE = orig_font_base
    AUTO_FONT_SIZE = orig_auto_size

    print("\n--- 処理完了 ---")
    return True

if __name__ == "__main__":
    main()
