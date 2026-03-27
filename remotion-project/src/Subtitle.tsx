import React from "react";
import { useCurrentFrame, interpolate } from "remotion";
import { loadFont } from "@remotion/google-fonts/NotoSansJP";

const { fontFamily } = loadFont();

interface SubtitleProps {
  index: number;
  lines: string[];
  fontSize: number;
  bottom: number;
}

export const Subtitle: React.FC<SubtitleProps> = ({ index, lines, fontSize, bottom }) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, 3], [0, 1], { extrapolateRight: "clamp" });

  const handleBlur = (e: React.FocusEvent<HTMLDivElement>) => {
    const newText = e.currentTarget.innerText;
    // 127.0.0.1:5001 にリクエスト先を変更
    fetch("http://127.0.0.1:5001/update-subtitle", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      mode: "cors",
      body: JSON.stringify({ index, text: newText }),
    })
    .then(res => res.json())
    .then(data => {
      if (data.success) {
        console.log("Subtitle updated successfully!");
        // 保存成功時に枠線を緑に光らせるフィードバック
        e.currentTarget.style.borderColor = "#22c55e";
        setTimeout(() => {
          if (e.currentTarget) e.currentTarget.style.borderColor = "transparent";
        }, 1000);
      }
    })
    .catch(err => {
      console.error("Error updating subtitle:", err);
      // エラー時に赤く光らせる
      e.currentTarget.style.borderColor = "#ef4444";
    });
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    e.stopPropagation();
    
    // Enterキー単体で確定（改行したい場合は Shift + Enter）
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      e.currentTarget.blur();
    }
  };

  return (
    <div 
      contentEditable
      suppressContentEditableWarning
      onBlur={handleBlur}
      onKeyDown={handleKeyDown}
      onKeyUp={(e) => e.stopPropagation()}
      style={{
        position: "absolute",
        bottom: bottom,
        left: 0,
        right: 0,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        pointerEvents: "auto",
        opacity,
        cursor: "text",
        zIndex: 100,
        transition: "border 0.2s",
        border: "2px solid transparent",
        borderRadius: "8px",
        padding: "4px",
      }}
      // フォーカス時に少し枠を見せる
      onFocus={(e) => {
        e.currentTarget.style.borderColor = "rgba(107, 33, 168, 0.5)";
      }}
    >
      {lines.map((line, i) => (
        <div key={i} style={{
          color: "#FFFFFF",
          fontSize,
          fontWeight: 900,
          fontFamily,
          textShadow: [
            "3px 0 0 #6B21A8", "-3px 0 0 #6B21A8",
            "0 3px 0 #6B21A8", "0 -3px 0 #6B21A8",
            "3px 3px 0 #6B21A8", "-3px -3px 0 #6B21A8",
            "3px -3px 0 #6B21A8", "-3px 3px 0 #6B21A8",
            "2px 2px 4px rgba(0,0,0,0.8)",
          ].join(", "),
          lineHeight: 1.4,
          whiteSpace: "nowrap",
          textAlign: "center",
          outline: "none",
        }}>
          {line}
        </div>
      ))}
    </div>
  );
};
