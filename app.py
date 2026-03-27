import streamlit as st
import os
import shutil
import sys
import json

# 自作モジュールのインポート
# 実行ディレクトリをパスに追加
sys.path.append(os.getcwd())
try:
    from auto_edit_pro import process_video
except ImportError:
    st.error("auto_edit_pro.py が見つかりません。同一ディレクトリに配置してください。")

st.set_page_config(page_title="AI-Cut Pro Dashboard", page_icon="🎬", layout="wide")

# カスタムCSSでデザインを整える
st.markdown("""
    <style>
    .main {
        background-color: #f5f7f9;
    }
    .stButton>button {
        width: 100%;
        border-radius: 10px;
        height: 3em;
        background-color: #FF4B4B;
        color: white;
        font-weight: bold;
    }
    .stStatusWidget {
        border-radius: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("🎬 AI-Cut Pro")
st.markdown("### 無音カット ＆ 自動テロップ生成ダッシュボード")

# サイドバーの設定
with st.sidebar:
    st.header("⚙️ 編集設定")
    st.markdown("---")
    
    skip_cut = st.checkbox("テロップのみモード", value=True, help="無音カットを行わず、元の動画にテロップだけを入れます。")
    
    st.subheader("📝 テロップ設定")
    max_chars_per_line = st.slider("1行の最大文字数", 5, 40, 18)
    max_chars_per_subtitle = st.slider("1つのテロップの合計最大文字数", 10, 80, 30)
    remove_punctuation = st.checkbox("句読点（、。）を除去する", value=True)
    
    st.subheader("🎨 デザイン設定")
    font_size_base = st.slider("基本フォントサイズ", 20, 150, 72)
    subtitle_bottom = st.slider("テロップの高さ (下からの距離)", 0, 500, 40, help="画面下部からのピクセル数です。")
    auto_font_size = st.checkbox("サイズ自動調整", value=False, help="文字数が多い時に自動でフォントを小さくします。")
    
    st.markdown("---")
    st.info("設定を変更してから「編集を開始する」を押してください。")

# タブの作成
tab1, tab2, tab3 = st.tabs(["🚀 編集実行", "🖋️ テロップの直接編集", "📺 リアルタイムプレビュー"])

with tab1:
    col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("1. 動画のアップロード")
    uploaded_file = st.file_uploader("動画ファイルを選択してください (.mp4, .mov, .m4v)", type=["mp4", "mov", "m4v"])
    
    if uploaded_file:
        input_path = os.path.join("input", uploaded_file.name)
        os.makedirs("input", exist_ok=True)
        with open(input_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.success(f"ファイルを読み込みました: {uploaded_file.name}")
        st.video(input_path)
    
    st.markdown("---")
    st.subheader("✨ レイアウト・シミュレーター")
    st.caption("設定変更がリアルタイムに反映されます")
    
    # シミュレーターの表示
    # 実際のリモーションのプレビューを模したHTML/CSS
    preview_html = f"""
    <div style="
        position: relative; 
        width: 100%; 
        aspect-ratio: 16/9; 
        background-color: #000; 
        border: 2px solid #555; 
        border-radius: 8px; 
        overflow: hidden;
        display: flex;
        flex-direction: column;
        align-items: center;
    ">
        <div style="
            position: absolute;
            bottom: {subtitle_bottom}px;
            left: 0;
            right: 0;
            display: flex;
            justify-content: center;
            pointer-events: none;
        ">
            <span style="
                color: #FFFFFF;
                font-size: {font_size_base}px;
                font-weight: 900;
                text-align: center;
                line-height: 1.4;
                white-space: nowrap;
                text-shadow: 
                    2px 2px 0 #6B21A8, -2px -2px 0 #6B21A8, 
                    2px -2px 0 #6B21A8, -2px 2px 0 #6B21A8, 
                    0 2px 0 #6B21A8, 0 -2px 0 #6B21A8, 
                    2px 0 0 #6B21A8, -2px 0 0 #6B21A8,
                    2px 2px 4px rgba(0,0,0,0.8);
                font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
            ">
                ここにテロップが表示されます
            </span>
        </div>
        <div style="color: #444; margin-top: auto; margin-bottom: auto; font-size: 14px;">(動画プレビューイメージ)</div>
    </div>
    """
    st.markdown(preview_html, unsafe_allow_html=True)

with col2:
    st.subheader("2. 実行と結果")
    if uploaded_file:
        if st.button("🚀 編集を開始する"):
            # プロセス実行
            log_container = st.empty()
            with st.status("AIが動画を解析中...", expanded=True) as status:
                st.write("⏳ 音声を抽出しています...")
                try:
                    # process_video を呼び出す
                    # 標準出力を取得するのは難しいので、進捗は st.write で代用
                    success = process_video(
                        input_video=os.path.join("input", uploaded_file.name),
                        skip_cut=skip_cut,
                        max_chars_per_line=max_chars_per_line,
                        max_chars_per_subtitle=max_chars_per_subtitle,
                        font_size_base=font_size_base,
                        auto_font_size=auto_font_size,
                        subtitle_bottom=subtitle_bottom,
                        remove_punctuation=remove_punctuation
                    )
                    
                    if success:
                        status.update(label="✅ 編集が完了しました！", state="complete", expanded=False)
                        st.balloons()
                        st.success("全ての処理が正常に終了しました。")
                        
                        st.markdown("### 🔗 次のステップ")
                        st.markdown(f"""
                        1. **プレビューを確認する**  
                           [プレビュー画面を開く (http://localhost:3001)](http://localhost:3001)
                        
                        2. **テロップを修正する**  
                           - 上の「テロップの直接編集」タブ、または下の「リアルタイムプレビュー」タブから画面を見ながら修正できます。
                        
                        3. **ファイルを書き出す**  
                           - [SRT字幕ファイルをダウンロード](output/subtitles.srt)  
                           - [Premiere Pro用XMLをダウンロード](output/premiere_sequence.xml)
                        """)
                except Exception as e:
                    st.error(f"エラーが発生しました: {e}")
    else:
        st.info("左側のパネルから動画をアップロードしてください。")

with tab2:
    st.subheader("🖋️ テロップの直接編集")
    subtitle_path = "remotion-project/public/subtitles.json"
    
    if os.path.exists(subtitle_path):
        with open(subtitle_path, "r", encoding="utf-8") as f:
            sub_data = json.load(f)
        
        # 編集用にフラットなリストを作成
        edit_list = []
        for i, item in enumerate(sub_data):
            edit_list.append({
                "No": i + 1,
                "開始": f"{item['start']:.2f}s",
                "内容": " / ".join(item["lines"])
            })
        
        st.write("各行をダブルクリックして編集できます。")
        edited_df = st.data_editor(
            edit_list, 
            hide_index=True, 
            column_config={
                "No": st.column_config.NumberColumn(width="small", disabled=True),
                "開始": st.column_config.TextColumn(width="small", disabled=True),
                "内容": st.column_config.TextColumn(width="large")
            },
            use_container_width=True
        )
        
        if st.button("💾 変更を保存して反映する"):
            # 保存処理
            new_sub_data = sub_data.copy()
            for i, row in enumerate(edited_df):
                # " / " で分割して配列に戻す
                new_sub_data[i]["lines"] = [line.strip() for line in row["内容"].split("/")]
            
            # JSON保存
            with open(subtitle_path, "w", encoding="utf-8") as f:
                json.dump(new_sub_data, f, ensure_ascii=False, indent=2)
            
            # SRTも更新（簡易的な変換）
            srt_path = "output/subtitles.srt"
            with open(srt_path, "w", encoding="utf-8") as f:
                for i, item in enumerate(new_sub_data):
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
            
            st.success("テロップを更新しました！「リアルタイムプレビュー」タブで確認してください。")
            st.balloons()
    else:
        st.info("まだテロップが生成されていません。先に「編集実行」タブで動画を処理してください。")

with tab3:
    st.subheader("📺 リアルタイムプレビュー")
    st.info("ここで再生を確認しながら、テロップを直接クリックして修正することが可能です。")
    
    # Remotion Studio を Iframe で埋め込み
    # port 3001 で起動していることが前提
    st.components.v1.iframe("http://localhost:3001", height=800, scrolling=True)
