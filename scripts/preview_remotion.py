"""Repackage the existing relaxation pilot using local Whisper and Remotion."""

import argparse
import json
from pathlib import Path
import subprocess

from dhp import content_templates, make, native_assembly


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job-dir', required=True)
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--asr-model', required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    source = Path(args.job_dir).resolve()
    output = Path(args.output_dir).resolve()
    if output.exists():
        raise ValueError('Choose a new output directory.')
    brief = json.loads((root / 'templates/product-demo/example-relax.json').read_text(encoding='utf-8'))
    job = json.loads((source / 'job.json').read_text(encoding='utf-8'))
    if job.get('spec', {}).get('text') != content_templates.narration(brief, content_templates.resolve('product-demo')):
        raise ValueError('Use the documented relaxation pilot; cards quote its actual dialogue.')
    assets = output / 'assets'
    assets.mkdir(parents=True)
    ffmpeg = native_assembly._find_ffmpeg(None)
    def run(*arguments):
        subprocess.run([ffmpeg, '-nostdin', '-v', 'error', *map(str, arguments)], check=True, capture_output=True)
    card = root / 'examples/showcase/relax-card.png'
    first, second = assets / 'relax-steps.png', assets / 'relax-music.png'
    run('-i', card, '-vf', 'crop=680:300:20:400', '-frames:v', '1', first)
    run('-i', card, '-vf', 'crop=680:160:20:690', '-frames:v', '1', second)
    cut = output / 'cut'
    status = make.main(['restyle', '--job-dir', str(source), '--template', 'product-demo', '--renderer', 'remotion',
               '--asset', str(first), '--asset', str(second), '--asr-model', args.asr_model,
               '--title', '下班放松的三个方法', '--output-dir', str(cut)])
    if status != 0:
        raise RuntimeError('Local Remotion restyling failed; inspect the reported error.')
    qa = json.loads((cut / 'qa.json').read_text(encoding='utf-8'))
    edit = json.loads((cut / 'remotion.json').read_text(encoding='utf-8'))
    preview = output / 'preview'
    preview.mkdir()
    middle = (edit['scenes'][0]['at'] + edit['scenes'][0]['until']) / 2
    run('-ss', middle, '-i', cut / 'final.mp4', '-frames:v', '1', '-q:v', '3', preview / 'product-demo-remotion.jpg')
    run('-i', cut / 'final.mp4', '-an', '-filter_complex',
        'fps=8,scale=216:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96[p];[b][p]paletteuse=dither=bayer',
        '-loop', '0', preview / 'product-demo-remotion.gif')
    def audio_hash(path):
        return subprocess.check_output([ffmpeg, '-v', 'error', '-i', str(path), '-map', '0:a:0',
                                        '-c', 'copy', '-f', 'hash', '-']).decode().strip()
    hashes = [audio_hash(cut / name) for name in ('original.mp4', 'final.mp4')]
    assert hashes[0] == hashes[1], 'Narration changed during packaging.'
    proof = {'generation_requests': qa['generation_requests'], 'renderer': qa['renderer'],
             'source_sha256': qa['segments'][0]['sha256'], 'video_sha256': qa['video_sha256'],
             'audio_hash': hashes[0], 'audio_preserved': True, 'alignment_status': qa['alignment']['status'],
             'recognized_word_count': len(edit['words']), 'emphasis': edit['emphasis'], 'scenes': edit['scenes'],
             'warnings': qa['warnings'], 'notice': 'Existing relaxation narration and cropped illustrative cards. Playback review required.'}
    (output / 'proof.json').write_text(json.dumps(proof, ensure_ascii=False, indent=2), encoding='utf-8')
    (output / 'index.html').write_text('''<!doctype html><meta charset="utf-8"><title>Whisper 与 Remotion 对照</title>
<style>body{font:18px system-ui;background:#101c2c;color:white;margin:32px}main{display:flex;gap:28px;flex-wrap:wrap}video{width:300px;max-width:90vw}p{max-width:820px;line-height:1.6}a{color:#7ce2d1}</style>
<h1>同一条原片，本地动态包装</h1><p>沿用「下班放松」对白与示意卡，展示花字、多素材和主播小窗。字幕及素材切换采用估时，花字使用局部可靠匹配词的识别时间。新增生成请求为 0。</p>
<main><section><h2>原片</h2><video controls src="cut/original.mp4"></video></section>
<section><h2>Remotion 包装</h2><video controls src="cut/final.mp4"></video></section></main>
<p><a href="proof.json">查看本地验证记录</a></p>''', encoding='utf-8')
    print(json.dumps({'video': str(cut / 'final.mp4'), 'comparison': str(output / 'index.html'),
                      'proof': str(output / 'proof.json')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
