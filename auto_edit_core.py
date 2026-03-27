import os
import sys
import json
import subprocess
import re
import whisper
import budoux
import shutil

# Mac等ではシステムにインストールされたffmpegを使用します。
# 存在しない場合はデフォルトの "ffmpeg" を使用します。
FFMPEG_PATH = shutil.which("ffmpeg") or "ffmpeg"

# Whisperが内部でffmpegを呼べるようにPATHを追加（絶対パスの場合のみ）
if os.path.isabs(FFMPEG_PATH):
    FFMPEG_DIR = os.path.dirname(FFMPEG_PATH)
    if FFMPEG_DIR not in os.environ["PATH"]:
        os.environ["PATH"] = FFMPEG_DIR + os.pathsep + os.environ["PATH"]

def execute_command_list(args):
    if args[0] == "ffmpeg":
        args[0] = FFMPEG_PATH
    
    # デバッグ用にコマンドを表示
    # print(f"Executing: {' '.join(args)}")
    result = subprocess.run(args, capture_output=True, text=True, encoding='utf-8')
    return True, result.stderr

def split_text_by_length(text, max_len=17):
    parser = budoux.load_default_japanese_parser()
    chunks = parser.parse(text)
    lines = []
    current_line = ""
    for chunk in chunks:
        if len(current_line + chunk) <= max_len:
            current_line += chunk
        else:
            if current_line:
                lines.append(current_line)
            while len(chunk) > max_len:
                lines.append(chunk[:max_len])
                chunk = chunk[max_len:]
            current_line = chunk
    if current_line:
        lines.append(current_line)
    return lines

def get_speech_segments_via_ffmpeg(input_path):
    print("--- 無音検知中 (FFmpeg silencedetect) ---")
    cmd_args = ["ffmpeg", "-i", input_path, "-af", "silencedetect=n=-30dB:d=0.5", "-f", "null", "-"]
    success, stderr = execute_command_list(cmd_args)
    
    silence_starts = [float(m) for m in re.findall(r"silence_start: ([\d\.]+)", stderr)]
    silence_ends = [float(m) for m in re.findall(r"silence_end: ([\d\.]+)", stderr)]
    
    cmd_dur = ["ffmpeg", "-i", input_path, "-f", "null", "-"]
    success_dur, stderr_dur = execute_command_list(cmd_dur)
    duration_match = re.search(r"Duration: (\d+):(\d+):([\d\.]+)", stderr_dur)
    if duration_match:
        h, m, s = duration_match.groups()
        total_duration = int(h) * 3600 + int(m) * 60 + float(s)
    else:
        total_duration = 0.0
        
    speech_segments = []
    current_start = 0.0
    for start, end in zip(silence_starts, silence_ends):
        if start > current_start + 0.1:
            speech_segments.append((current_start, start))
        current_start = end
    if total_duration > current_start + 0.1:
        speech_segments.append((current_start, total_duration))
    return speech_segments

def process_video(input_path, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    cut_video = os.path.join(output_dir, "cut_video.mp4")
    subtitles_json = os.path.join(output_dir, "subtitles.json")

    speech_segments = get_speech_segments_via_ffmpeg(input_path)
    if not speech_segments:
        print("音声が検出されませんでした。")
        return

    print(f"--- 無音部分をカットして連結中 ({len(speech_segments)} セグメント) ---")
    select_parts = []
    for start, end in speech_segments:
        select_parts.append(f"between(t,{start},{end})")
    
    select_filter = "+".join(select_parts)
    filter_cmd_args = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", f"select='{select_filter}',setpts=N/FRAME_RATE/TB",
        "-af", f"aselect='{select_filter}',asetpts=N/SR/TB",
        cut_video
    ]
    execute_command_list(filter_cmd_args)

    print("--- 文字起こし中 (Whisper small) ---")
    # Whisper内部でffmpegを呼ぶため、PATH設定が重要
    whisper_model = whisper.load_model("small")
    result = whisper_model.transcribe(cut_video, language="ja", verbose=False)

    print("--- 字幕を整形中 (17文字制限) ---")
    formatted_subtitles = []
    for segment in result["segments"]:
        text = segment["text"].strip()
        lines = split_text_by_length(text, max_len=17)
        duration = segment["end"] - segment["start"]
        line_duration = duration / len(lines) if lines else 0
        for i, line in enumerate(lines):
            formatted_subtitles.append({
                "start": segment["start"] + (i * line_duration),
                "end": segment["start"] + ((i + 1) * line_duration),
                "text": line
            })

    with open(subtitles_json, "w", encoding="utf-8") as f:
        json.dump(formatted_subtitles, f, ensure_ascii=False, indent=2)

    print(f"\n--- 完了 ---")
    print(f"カット済み動画: {cut_video}")
    print(f"字幕データ: {subtitles_json}")

if __name__ == "__main__":
    # 動画ファイルを自動検出
    video_files = []
    if os.path.exists("input"):
        video_files = [os.path.join("input", f) for f in os.listdir("input") if f.lower().endswith(('.mp4', '.mov', '.m4v'))]
    input_file = video_files[0] if video_files else os.path.join("input", "test.mp4")
    output_folder = "output"
    
    print(f"対象の動画: {input_file}")
    if os.path.exists(input_file):
        process_video(input_file, output_folder)
    else:
        print(f"動画ファイルが見つかりません: {input_file}")
