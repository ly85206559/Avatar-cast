"""Real TTS adapter: run a configurable external TTS command.

AvatarCast does not bundle a TTS model, and it does not pretend a
command-line demo is a product default. This adapter is the seam: you
plug in whatever TTS you actually run (a local engine, a vendor CLI,
a self-hosted service wrapped in a script) via a command template, and
the pipeline only ever sees the Audio it returns.

Template placeholders: {text}, {output}, {language}, {voice}.
The command must write an audio file to {output} and exit 0.

Default template (local verification only, NOT portable): the sandbox
``tts`` command, verified 2026-10-26/27 on Mandarin text with voice
avocado_v2:MAI_03. Repo users without that command must supply their
own template -- see config/tts.example.yaml (added in v0.3).
"""

from __future__ import annotations

import hashlib
import shlex
import subprocess
from pathlib import Path

from .providers import Audio
from .render import probe_duration_sec

DEFAULT_TEMPLATE = (
    "tts speak --language {language} --voice {voice} --output {output} --text {text}"
)


class CommandTTSProvider:
    def __init__(self, template: str = DEFAULT_TEMPLATE,
                 language: str = "zh", voice: str = "avocado_v2:MAI_03"):
        self.template = template
        self.language = language
        self.voice = voice

    def synthesize(self, segment: dict, output_path: str) -> Audio:
        text = segment["text"]
        cmd = self.template.format(
            text=shlex.quote(text), output=shlex.quote(output_path),
            language=self.language, voice=self.voice)
        subprocess.run(cmd, shell=True, check=True)
        data = Path(output_path).read_bytes()
        return Audio(
            path=output_path,
            duration_sec=probe_duration_sec(output_path),
            sha256=hashlib.sha256(data).hexdigest(),
            voice_id=self.voice,
        )
