# 使い方ガイド

この環境を使用して、自動で動画に字幕を付ける基本的な流れを説明します。

## 1. 動画の文字起こし (Python + Whisper)

まず、動画ファイルから音声を取り出し、文字起こしデータ（JSON）を作成します。

### 手順
1. 字幕を付けたい動画（例: `test.mp4`）を `C:\Users\darumaya\Documents\video-edit\input\` に置きます。
2. 以下のPythonコード（例: `transcribe.py`）を実行して、文字起こしJSONを生成します。

```python
import whisper
import json
import os

# 設定
input_video = r"C:\Users\darumaya\Documents\video-edit\input\test.mp4"
output_json = "subtitles.json"

# モデルの読み込み (large-v3)
model = whisper.load_model("large-v3")

# 文字起こし実行 (日本語指定)
print("文字起こしを開始します...")
result = model.transcribe(input_video, language="ja")

# 結果をJSONとして保存
with open(output_json, "w", encoding="utf-8") as f:
    json.dump(result["segments"], f, ensure_ascii=False, indent=2)

print(f"完了しました！ {output_json} が生成されました。")
```

実行コマンド例:
`.\venv\Scripts\python.exe transcribe.py`

---

## 2. 動画のプレビュー・レンダリング (Remotion)

次に、生成した `subtitles.json` を Remotion に読み込ませて動画を表示します。

### 手順
1. `remotion-project/src/subtitles.json` に先ほどのファイルをコピーします。
2. Remotion Studioを起動して確認します。

```bash
cd remotion-project
npm run dev
```

ブラウザが開き、タイムライン上で字幕が表示されるのを確認できます。

### MP4として出力する場合
```bash
npx remotion render MyComp out.mp4
```

---

## 3. 高度な使い方

- **Budoux**: 字幕が長すぎる場合、`budoux` を使って読みやすい位置で改行を入れるロジックを `transcribe.py` に追加できます。
- **デザイン変更**: `remotion-project/src/Composition.tsx` を編集することで、字幕のフォント、色、アニメーションを自由に変更できます。
