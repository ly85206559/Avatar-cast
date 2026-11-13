import React from 'react';
import {AbsoluteFill, Composition, Img, Loop, OffthreadVideo, Sequence,
  interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';

type Caption = {text: string; startMs: number; endMs: number; timestampMs: number | null; confidence: number | null};
type Word = {word: string; start: number; end: number; conf: number};
type Scene = {src: string; type: string; sourceFrames: number; at: number; until: number};
type Props = {duration: number; title: string; captions: Caption[]; words: Word[]; emphasis: Word[]; scenes: Scene[]; timing: string};

const ProductDemo: React.FC<Props> = ({title, captions, emphasis, scenes, timing}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const seconds = frame / fps;
  const scene = scenes.find(item => seconds >= item.at && seconds < item.until);
  const caption = captions.find(item => seconds * 1000 >= item.startMs && seconds * 1000 < item.endMs);
  const word = emphasis.find(item => seconds >= item.start && seconds < Math.max(item.end, item.start + 0.65));
  const wordEntry = spring({frame: word ? frame - word.start * fps : 0, fps, config: {damping: 18}});
  const cueAge = caption ? frame - caption.startMs / 1000 * fps : 0;
  const entry = spring({frame: Math.max(0, cueAge), fps, config: {damping: 18}});
  return <AbsoluteFill style={{backgroundColor: '#101c2c', color: 'white',
    fontFamily: '"Microsoft YaHei", "Noto Sans CJK SC", sans-serif'}}>
    {scenes.map((item, index) => <Sequence key={index} from={Math.round(item.at * fps)}
      durationInFrames={Math.max(1, Math.round(item.until * fps) - Math.round(item.at * fps))} premountFor={fps}>
      <div style={{position: 'absolute', left: 28, top: 230, width: 664, height: 560,
        backgroundColor: '#15283a', borderRadius: 24, overflow: 'hidden', border: '1px solid #31536a'}}>
        {item.type === 'image' ? <Img src={staticFile(item.src)} style={{width: '100%', height: '100%', objectFit: 'contain'}} /> :
          <Loop durationInFrames={item.sourceFrames}>
            <OffthreadVideo src={staticFile(item.src)} muted style={{width: '100%', height: '100%', objectFit: 'contain'}} />
          </Loop>}
      </div>
    </Sequence>)}
    <OffthreadVideo src={staticFile('host.mp4')} muted style={scene ? {
      position: 'absolute', left: 486, top: 805, width: 206, height: 318, objectFit: 'cover',
      borderRadius: 24, border: '3px solid #f3f1ec', boxSizing: 'border-box'} : {
      position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'contain'}} />
    <div style={{position: 'absolute', top: 28, left: 28, fontSize: 24, backgroundColor: '#101c2ccc',
      padding: '8px 16px', borderRadius: 12}}>AI 数字人演绎</div>
    {timing === 'estimated' && <div style={{position: 'absolute', top: 30, right: 28, fontSize: 21,
      backgroundColor: '#101c2ccc', padding: '8px 12px', borderRadius: 12}}>字幕时间待复核</div>}
    {title && <div style={{position: 'absolute', top: 110, left: 28, right: 28, fontSize: 40,
      fontWeight: 800, padding: '18px 24px', backgroundColor: '#101c2ce8', borderLeft: '6px solid #7ce2d1',
      borderRadius: 16, overflowWrap: 'anywhere'}}>{title}</div>}
    {caption && <div style={{position: 'absolute', left: 28, right: 28, bottom: 55, textAlign: 'center',
      fontSize: 38, lineHeight: 1.4, fontWeight: 700, padding: '16px 20px', borderRadius: 20,
      backgroundColor: '#101c2ce8', scale: interpolate(entry, [0, 1], [0.96, 1]), overflowWrap: 'anywhere'}}>
      {caption.text}
    </div>}
    {word && word.word.replace(/[^\p{L}\p{N}]/gu, '').length >= 2 &&
      <div style={{position: 'absolute', left: 36, top: 900, maxWidth: scene ? 400 : 640,
        color: '#7ce2d1', backgroundColor: '#101c2ce8', padding: '14px 22px', fontSize: 56,
        fontWeight: 900, borderRadius: 16, scale: interpolate(wordEntry, [0, 1], [0.92, 1]),
        overflowWrap: 'anywhere'}}>{word.word.replace(/[，。！？,.!?]/g, '')}</div>}
  </AbsoluteFill>;
};

export const RemotionRoot = () => <Composition id="ProductDemo" component={ProductDemo} width={720} height={1280}
  fps={30} durationInFrames={300} defaultProps={{duration: 10, title: '演示种草', captions: [], words: [], emphasis: [], scenes: [], timing: 'estimated'}}
  calculateMetadata={({props}) => ({durationInFrames: Math.max(1, Math.ceil(props.duration * 30))})} />;
