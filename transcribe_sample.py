import whisper
import json
import os
import sys

def transcribe_video(input_path, output_json="subtitles.json"):
    if not os.path.exists(input_path):
        print(f"Error: {input_path} が見つかりません。")
        return

    print(f"モデルをロード中 (large-v3)...")
    model = whisper.load_model("large-v3")

    print(f"文字起こし実行中: {input_path}")
    # verbose=Falseで進捗表示をスッキリさせる
    result = model.transcribe(input_path, language="ja", verbose=False)

    # Remotionで扱いやすい形式に整形して保存
    segments = []
    for s in result["segments"]:
        segments.append({
            "start": s["start"],
            "end": s["end"],
            "text": s["text"].strip()
        })

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(segments, f, ensure_ascii=False, indent=2)

    print(f"成功: {output_json} に保存されました。")

if __name__ == "__main__":
    # デフォルトの入力パス
    input_file = r"C:\Users\darumaya\Documents\video-edit\input\test.mp4"
    
    # 引数があればそれを使用
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    
    transcribe_video(input_file)
