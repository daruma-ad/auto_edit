import json
import os
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app) # Remotion Studio からのリクエストを許可

SUBTITLE_JSON = "remotion-project/public/subtitles.json"
SUBTITLE_SRT = "output/subtitles.srt"

def save_srt(sub_data):
    with open(SUBTITLE_SRT, "w", encoding="utf-8") as f:
        for i, item in enumerate(sub_data):
            start_s = int(item["start"])
            start_ms = int((item["start"] - start_s) * 1000)
            end_s = int(item["end"])
            end_ms = int((item["end"] - end_s) * 1000)
            
            def fmt_time(s, ms):
                h = s // 3600
                m = (s % 3600) // 60
                sec = s % 60
                return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"
            
            f.write(f"{i+1}\n")
            f.write(f"{fmt_time(start_s, start_ms)} --> {fmt_time(end_s, end_ms)}\n")
            f.write("\n".join(item["lines"]) + "\n\n")

@app.route("/update-subtitle", methods=["POST"])
def update_subtitle():
    try:
        data = request.json
        index = data.get("index")
        new_text = data.get("text")
        
        if index is None or new_text is None:
            return jsonify({"error": "Index and text are required"}), 400
            
        if not os.path.exists(SUBTITLE_JSON):
            return jsonify({"error": "Subtitles file not found"}), 404
            
        with open(SUBTITLE_JSON, "r", encoding="utf-8") as f:
            sub_list = json.load(f)
            
        if index < 0 or index >= len(sub_list):
            return jsonify({"error": "Index out of range"}), 400
            
        # 修正の反映 (" / " または改行で分割)
        new_lines = [line.strip() for line in new_text.replace("\n", " / ").split(" / ")]
        sub_list[index]["lines"] = new_lines
        
        # 保存
        with open(SUBTITLE_JSON, "w", encoding="utf-8") as f:
            json.dump(sub_list, f, ensure_ascii=False, indent=2)
            
        save_srt(sub_list)
        
        print(f"Updated index {index}: {new_text}")
        return jsonify({"success": True})
        
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    print("AI-Cut API Server starting on http://127.0.0.1:5001")
    app.run(host="0.0.0.0", port=5001, debug=False)
