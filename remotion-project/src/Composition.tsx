import { Video, useCurrentFrame, AbsoluteFill, staticFile } from 'remotion';
import subtitles from './subtitles.json';

export const MyComposition = () => {
    const frame = useCurrentFrame();
    const fps = 30; // 調整が必要な場合は定数化
    const currentTime = frame / fps;

    // 現在の時間に該当する字幕を検索
    const currentSubtitle = subtitles.find(
        (s) => currentTime >= s.start && currentTime <= s.end
    );

    return (
        <AbsoluteFill style={{ backgroundColor: 'black' }}>
            {/* 動画本体 */}
            <Video src={staticFile('cut_video.mp4')} />

            {/* 字幕表示エリア */}
            {currentSubtitle && (
                <AbsoluteFill
                    style={{
                        justifyContent: 'flex-end',
                        alignItems: 'center',
                        bottom: 100,
                    }}
                >
                    <div
                        style={{
                            backgroundColor: 'rgba(0, 0, 0, 0.7)',
                            color: 'white',
                            padding: '10px 20px',
                            fontSize: '48px',
                            borderRadius: '10px',
                            fontFamily: 'sans-serif',
                            textAlign: 'center',
                        }}
                    >
                        {currentSubtitle.text}
                    </div>
                </AbsoluteFill>
            )}
        </AbsoluteFill>
    );
};
