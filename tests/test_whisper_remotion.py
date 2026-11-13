import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import wave
from types import SimpleNamespace

from PIL import Image
import pytest

from dhp import asr_whisper, auto_pack, make, native_assembly, remotion_render, showcase
from dhp.asr_whisper import WhisperASRProvider


def test_whisper_uses_only_local_cpu_model_and_keeps_observed_times(tmp_path, monkeypatch):
    wav = tmp_path / 'audio.wav'
    with wave.open(str(wav), 'wb') as target:
        target.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
        target.writeframes(b'\x00\x00' * 16000)
    monkeypatch.setattr(asr_whisper, '_convert_to_16k_mono_wav', lambda *_: str(wav))
    calls = []
    def model(path, **options):
        calls.append(options)
        def transcribe(audio, **settings):
            assert settings['word_timestamps'] is True and settings['language'] == 'zh'
            assert audio.shape == (16000,)
            word = SimpleNamespace(word=' 方法', start=1.23, end=1.81, probability=0.93)
            return iter([SimpleNamespace(words=[word])]), None
        return SimpleNamespace(transcribe=transcribe)
    monkeypatch.setitem(sys.modules, 'faster_whisper', SimpleNamespace(WhisperModel=model))
    assert WhisperASRProvider(str(tmp_path)).transcribe('local.mp4') == [
        {'word': '方法', 'start': 1.23, 'end': 1.81, 'conf': 0.93}]
    assert calls[0]['local_files_only'] is True and calls[0]['device'] == 'cpu'
    with pytest.raises(RuntimeError, match='local faster-whisper'):
        WhisperASRProvider(str(tmp_path / 'missing'))


def test_timeline_preserves_words_and_marks_caption_fallback():
    words = [{'word': '方法', 'start': 0.3, 'end': 1.1, 'conf': 0.9}]
    cues = [{'text': '方法。', 'start': 0.3, 'end': 1.1}]
    assets = [{'src': 'a.png'}, {'src': 'b.png'}]
    edit = remotion_render.timeline(4, {'status': 'matched', 'words': words}, cues,
                                   {'at': 1, 'until': 3, 'timing': 'estimated'}, assets, '标题')
    assert edit['words'] == words
    assert [(s['at'], s['until']) for s in edit['scenes']] == [(1, 2), (2, 3)]
    assert edit['scene_timing'] == 'estimated'
    assert edit['captions'][0]['startMs'] == 300
    fallback = remotion_render.timeline(4, {'status': 'fallback', 'words': words}, cues, None, [], '')
    assert fallback['words'] == words and fallback['emphasis'] == [] and fallback['timing'] == 'estimated'
    with pytest.raises(ValueError, match='Too many'):
        remotion_render.timeline(4, {}, [], {'at': 1, 'until': 1.5}, assets, '')


def test_partial_highlights_exclude_wrong_numbers_and_uncertain_words():
    words = [{'word': text, 'start': index, 'end': index + 0.5, 'conf': confidence}
             for index, (text, confidence) in enumerate([('放松', 0.99), ('10', 0.99), ('分钟', 0.3)])]
    assert auto_pack.exact_words('放松十分钟', words) == words[:1]
    edit = remotion_render.timeline(4, {'status': 'fallback', 'words': words, 'matched_words': words[:1]},
                                    [{'text': '放松十分钟', 'start': 0, 'end': 3}], None, [], '')
    assert edit['timing'] == 'estimated' and edit['emphasis'] == words[:1]


def test_multi_asset_plan_is_reviewed_and_tampering_stops_before_gateway(tmp_path, monkeypatch):
    monkeypatch.setattr(make.GatewayClient, 'from_config', lambda *_: pytest.fail('contacted gateway'))
    paths = []
    for name in ('host', 'first', 'second'):
        path = tmp_path / (name + '.png')
        Image.new('RGB', (16, 24), 'red').save(path)
        paths.append(str(path))
    brief = {'request': '演示种草', 'template': 'product-demo', 'script': '先看产品，再看细节。',
             'renderer': 'remotion', 'asset': paths[1:]}
    plan = make.create_brief_plan(paths[0], brief, str(tmp_path / 'project'))
    assert len(plan['asset']) == 2 and plan['renderer'] == 'remotion'
    assert make._load_plan(Path(plan['project']))[1] == plan['plan_sha256']
    Image.new('RGB', (16, 24), 'blue').save(paths[2])
    with pytest.raises(ValueError, match='changed'):
        make.run_project(plan['project'], confirm=True, plan_sha256=plan['plan_sha256'])
    with pytest.raises(ValueError, match='Multiple'):
        make.create_plan(paths[0], brief['script'], str(tmp_path / 'other'),
                         template='product-demo', asset=paths[1:])
    assert isinstance(showcase.prepare_asset([paths[1]]), dict)


@pytest.mark.skipif(os.environ.get('REMOTION_RENDER_TEST') != '1', reason='optional local Remotion render')
def test_cli_renders_two_assets_pip_and_preserves_audio(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(make.GatewayClient, 'from_config', lambda *_: pytest.fail('contacted gateway'))
    ffmpeg = native_assembly._find_ffmpeg(None)
    job = tmp_path / 'job'
    job.mkdir()
    source = job / 'original.mp4'
    subprocess.run([ffmpeg, '-v', 'error', '-f', 'lavfi', '-i', 'color=green:s=180x320:r=30:d=4',
                    '-f', 'lavfi', '-i', 'sine=duration=4', '-c:v', 'libx264', '-c:a', 'aac', str(source)], check=True)
    (job / 'job.json').write_text(json.dumps({'version': 1, 'status': 'complete',
        'spec': {'mode': 'native', 'text': '先看产品，再看细节。'},
        'expected_sha256': hashlib.sha256(source.read_bytes()).hexdigest()}), encoding='utf-8')
    class LocalASR:
        def __init__(self, _):
            pass
        def transcribe(self, _):
            return [{'word': '先看产品', 'start': 0.2, 'end': 1.8, 'conf': 0.99},
                    {'word': '再看细节', 'start': 2.1, 'end': 3.8, 'conf': 0.99}]
    monkeypatch.setattr(auto_pack, 'WhisperASRProvider', LocalASR)
    images = [tmp_path / 'red.png', tmp_path / 'blue.mp4']
    Image.new('RGB', (640, 480), 'red').save(images[0])
    subprocess.run([ffmpeg, '-v', 'error', '-f', 'lavfi', '-i', 'color=blue:s=320x240:r=30:d=0.3',
                    '-f', 'lavfi', '-i', 'sine=frequency=1200:duration=0.3',
                    '-c:v', 'libx264', '-c:a', 'aac', str(images[1])], check=True)
    output = tmp_path / 'cut'
    assert make.main(['restyle', '--job-dir', str(job), '--template', 'product-demo',
                      '--renderer', 'remotion', '--asset', str(images[0]), '--asset', str(images[1]),
                      '--output-dir', str(output)]) == 0
    result = json.loads(capsys.readouterr().out)
    qa = json.loads((output / 'qa.json').read_text(encoding='utf-8'))
    assert result['generation_requests'] == 0 and qa['renderer'] == 'remotion'
    assert qa['alignment']['engine'] == 'whisper' and qa['alignment']['status'] == 'matched'
    assert qa['subtitle_timing'] == 'whisper_matched_sentence_bounds'
    edit = json.loads((output / 'remotion.json').read_text(encoding='utf-8'))
    assert len(edit['scenes']) == 2 and edit['words'][0]['start'] == 0.2
    def pixel(second, x, y):
        raw = subprocess.check_output([ffmpeg, '-v', 'error', '-ss', str(second), '-i', str(output / 'final.mp4'),
            '-vf', f'crop=2:2:{x}:{y}', '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'])
        return raw[:3]
    assert pixel(1.5, 200, 400)[0] > 200
    assert pixel(2.5, 200, 400)[2] > 200
    assert pixel(2.8, 200, 400)[2] > 200
    for second in (0.5, 1.5, 2.5, 3.5):
        value = pixel(second, 600, 1000)
        assert value[1] > value[0] + 50 and value[1] > value[2] + 50
    def audio_hash(name):
        return subprocess.check_output([ffmpeg, '-v', 'error', '-i', str(output / name),
            '-map', '0:a:0', '-c', 'copy', '-f', 'hash', '-'])
    assert audio_hash('original.mp4') == audio_hash('final.mp4')

    # An interrupted local render resumes completed jobs and then reuses its result.
    plan = make.create_plan(str(images[0]), '先看产品，再看细节。', str(tmp_path / 'project'),
                            template='product-demo', asset=[str(p) for p in images], renderer='remotion')
    project = Path(plan['project'])
    segment = project / 'segment-001'
    segment.mkdir()
    (segment / 'original.mp4').write_bytes(source.read_bytes())
    receipt = json.loads((job / 'job.json').read_text(encoding='utf-8'))
    receipt['spec'].update(image_sha256=plan['image_sha256'], agent_id='existing-bot', duration_sec=10)
    (segment / 'job.json').write_text(json.dumps(receipt), encoding='utf-8')
    (project / 'approval.json').write_text(json.dumps({'plan_sha256': plan['plan_sha256'],
                                                     'agent_id': 'existing-bot'}), encoding='utf-8')
    monkeypatch.setattr(make.native, 'resume', lambda *_: receipt)
    real_assemble = native_assembly.assemble
    def interrupted(jobs, destination, **options):
        Path(destination).mkdir()
        raise RuntimeError('local renderer interrupted')
    monkeypatch.setattr(native_assembly, 'assemble', interrupted)
    with pytest.raises(RuntimeError, match='interrupted'):
        make.run_project(str(project))
    assert not (project / 'result').exists() and (segment / 'job.json').exists()
    monkeypatch.setattr(native_assembly, 'assemble', real_assemble)
    result = make.run_project(str(project))
    assert Path(result['video']).is_file()
    monkeypatch.setattr(native_assembly, 'assemble', lambda *_a, **_k: pytest.fail('rendered twice'))
    assert make.run_project(str(project))['video'] == result['video']
