"""Plan and run a small native-video project without repeating paid submissions."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from PIL import Image

from . import native
from .grok_gateway import GatewayClient, GatewayError
from . import presentation as packaging


def split_script(text: str, limit: int = 48) -> list[str]:
    """Split at nearby punctuation, keeping all words; length is only an estimate."""
    remaining = " ".join(text.split())
    if not remaining:
        raise ValueError("Script text is empty.")
    segments = []
    while len(remaining) > limit:
        cuts = [i + 1 for i, c in enumerate(remaining[:limit])
                if i >= limit // 2 and c in "。！？!?；;，, "]
        cut = cuts[-1] if cuts else limit
        # Keep an English word intact even when it is longer than the limit.
        if not cuts and remaining[cut - 1].isascii() and remaining[cut - 1].isalnum():
            while cut < len(remaining) and remaining[cut].isascii() and remaining[cut].isalnum():
                cut += 1
        segments.append(remaining[:cut].strip())
        remaining = remaining[cut:].strip()
    if remaining:
        segments.append(remaining)
    return segments


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"Cannot read valid JSON: {path.name}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path.name}.")
    return value


def _write_new_json(path: Path, value: dict) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as target:
        json.dump(value, target, ensure_ascii=False, indent=2)
        target.write("\n")


def _new_output(parent: Path = Path("outputs")) -> str:
    return str(parent / (datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid4().hex[:6]))


def create_plan(image: str, text: str, output_dir: str | None = None, duration: int = 10,
                *, presentation: dict | None = None, request: str | None = None) -> dict:
    """Write a reviewable plan locally. No gateway is contacted or media uploaded."""
    root = Path(output_dir or _new_output()).expanduser().resolve()
    if root.exists():
        raise ValueError("Choose a project directory that does not already exist.")
    segments = split_script(text)
    presentation = packaging.prepare(**(presentation or {}))
    spec = native.plan(image, segments[0], "select-at-run", str(root / "segment-001"), duration)
    with Image.open(spec["image"]) as presenter:
        if presenter.format not in ("JPEG", "PNG", "WEBP"):
            raise ValueError("Presenter image must be JPEG, PNG, or WebP.")
    plan = {
        "version": 1, "provider": "grok-native", "image": spec["image"],
        "image_sha256": spec["image_sha256"], "duration_sec_per_segment": duration,
        "language": "Mandarin", "aspect_ratio": spec["aspect_ratio"], "resolution": spec["resolution"],
        "segments": segments, "estimated_total_duration_sec": duration * len(segments),
        "presentation": presentation,
        **({"request": request} if request else {}),
        "billing": {
            "mode": "existing_allowance", "estimated_cost": None, "quota_consumption": None,
            "notice": "Check the actual subscription, remaining allowance and on-demand settings "
                      "before approval. This program cannot enforce provider billing settings.",
        },
        "notice": "Splitting and duration are estimates. Review every segment before approval. "
                  "The generated audio is native, not a supplied recording.",
    }
    root.mkdir(parents=True, exist_ok=False)
    _write_new_json(root / "plan.json", plan)
    return {**plan, "status": "plan_only", "project": str(root),
            "plan_sha256": native._sha256(root / "plan.json")}


def create_brief_plan(image: str, brief: dict, output_dir: str | None = None, duration: int = 10) -> dict:
    """The host assistant writes the narration; this command never calls an LLM."""
    if (not isinstance(brief.get("request"), str) or not brief["request"].strip()
            or not isinstance(brief.get("script"), str) or not brief["script"].strip()):
        raise ValueError("Brief needs the user's request and an assistant-drafted script.")
    presentation = packaging.prepare(brief.get("style", "auto"), brief.get("title", ""), brief["request"])
    return create_plan(image, brief["script"], output_dir, duration,
                       presentation=presentation, request=brief["request"])


def _chinese_font_status() -> str:
    if sys.platform == "win32":
        fonts = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
        return "available" if any((fonts / name).is_file() for name in
                                  ("msyh.ttc", "simhei.ttf", "simsun.ttc")) else "unknown"
    if sys.platform == "darwin":
        return "available" if Path("/System/Library/Fonts/PingFang.ttc").is_file() else "unknown"
    fc_list = shutil.which("fc-list")
    if not fc_list:
        return "unknown"
    try:
        result = subprocess.run([fc_list, ":lang=zh", "--format", "%{file}\n"], capture_output=True,
                                text=True, encoding="utf-8", errors="replace", check=False, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    if result.returncode != 0:
        return "unknown"
    return "available" if result.stdout.strip() else "missing"


def _gateway_recovery(error: GatewayError) -> dict:
    return {
        "reason": "possibly_sleeping_or_stale_gateway" if error.status_code == 417 else "connection_unavailable",
        "steps": ["在 Grok Bot 桌面确认已登录，并唤醒已有电脑；不要创建新电脑或更改计费设置。",
                  "电脑开始启动后运行连接导入脚本；脚本最多等待 30 秒就绪，不会替你唤醒电脑。",
                  "重新运行 make doctor --online。对已提交的任务只恢复原项目，不删除回执或重复生成。"],
        "setup_command": ("pwsh -NoProfile -File scripts/setup_grok_bot_windows.ps1" if sys.platform == "win32"
                          else "python scripts/setup_grok_bot_unix.py"),
        "check_command": "python -m dhp.cli make doctor --online",
        "resume_existing_only": True,
    }


def doctor(online: bool = False, gateway_config: str | None = None) -> dict:
    """Check local prerequisites; online mode only lists bots and never generates."""
    executable = native._find_ffmpeg()
    checks = {"available": bool(executable), "subtitles": False, "libx264": False}
    if executable:
        for option, name in (("-filters", "subtitles"), ("-encoders", "libx264")):
            result = subprocess.run([executable, "-hide_banner", option], capture_output=True,
                                    text=True, encoding="utf-8", errors="replace", check=False)
            checks[name] = result.returncode == 0 and bool(re.search(rf"\b{name}\b", result.stdout))
    config = Path(gateway_config).expanduser() if gateway_config else Path.home() / ".gbm" / "config.json"
    gateway = {"configured": config.is_file(), "connection": "not_checked"}
    if online:
        try:
            agents = GatewayClient.from_config(gateway_config).list_agents()
            gateway.update(connection="ok", bots=[{k: a[k] for k in ("id", "name", "isRunningTurn")
                                                    if k in a} for a in agents if isinstance(a, dict)])
        except GatewayError as exc:
            gateway.update(connection="unavailable", message=str(exc), recovery=_gateway_recovery(exc))
    return {
        "python": sys.version.split()[0], "ffmpeg": checks,
        "chinese_font": _chinese_font_status(), "grok_bot": gateway,
        "billing": "not_checked: check the provider account; allowance mode does not prevent charges",
        "routes": [
            {"name": "grok-native", "status": "available_experimental", "make_supported": True},
            {"name": "wavespeed-audio", "status": "separate_single_clip_not_live_verified", "make_supported": False},
        ],
        "notice": "Online checks are read-only. A sleeping Grok Bot computer must be woken in the app.",
    }


@contextmanager
def _project_lock(root: Path):
    """OS-held lock avoids concurrent submissions and is released on process exit."""
    with (root / ".run.lock").open("a+b") as lock:
        if os.name == "nt":
            import msvcrt

            if lock.tell() == 0:
                lock.write(b"0")
                lock.flush()
            lock.seek(0)
            try:
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise ValueError("Another process is already running this project.") from exc
        else:
            import fcntl

            try:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise ValueError("Another process is already running this project.") from exc
        try:
            yield
        finally:
            if os.name == "nt":
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _load_plan(root: Path) -> tuple[dict, str]:
    path = root / "plan.json"
    try:
        raw = path.read_bytes()
        plan = json.loads(raw.decode("utf-8"))
    except (OSError, ValueError, UnicodeError) as exc:
        raise ValueError("Cannot read valid JSON: plan.json") from exc
    if not isinstance(plan, dict):
        raise ValueError("Expected a JSON object in plan.json.")
    if (plan.get("version") != 1 or plan.get("provider") != "grok-native"
            or plan.get("language") != "Mandarin" or plan.get("aspect_ratio") != "9:16"
            or plan.get("resolution") != "720p"
            or not isinstance(plan.get("image"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", str(plan.get("image_sha256", "")))
            or not isinstance(plan.get("segments"), list) or not plan["segments"]
            or any(not isinstance(s, str) or not s.strip() for s in plan["segments"])
            or isinstance(plan.get("duration_sec_per_segment"), bool)
            or not isinstance(plan.get("duration_sec_per_segment"), int)
            or not 1 <= plan["duration_sec_per_segment"] <= 15):
        raise ValueError("The project plan is invalid.")
    if "presentation" in plan:
        value = plan["presentation"]
        if (not isinstance(value, dict) or set(value) != {"style", "title"}
                or packaging.prepare(value["style"], value["title"]) != value):
            raise ValueError("The presentation in the project plan is invalid.")
    return plan, hashlib.sha256(raw).hexdigest()


def _select_bot(client: GatewayClient, selected: str | None) -> str:
    agents = [a for a in client.list_agents() if isinstance(a, dict) and a.get("id")]
    if not agents:
        raise ValueError("No Grok Bot found; create or open a bot in the app first.")
    if selected:
        matches = [a for a in agents if a["id"] == selected]
    else:
        matches = agents if len(agents) == 1 else []
    if len(matches) != 1:
        raise ValueError("Select one bot with --agent-id; use 'dhp native bots' to list IDs.")
    if matches[0].get("isRunningTurn") or matches[0].get("awaitingUserResponse"):
        raise ValueError("The selected Grok Bot is busy or awaiting a response.")
    return matches[0]["id"]


def run_project(project: str, *, confirm: bool = False, plan_sha256: str | None = None,
                agent_id: str | None = None, gateway_config: str | None = None,
                wait_seconds: float = 120) -> dict:
    """Continue only previously approved segments, never resend an uncertain job."""
    root = Path(project).expanduser().resolve()
    if not root.is_dir():
        raise ValueError("Project directory does not exist; create a plan first.")
    if wait_seconds < 0 or not math.isfinite(wait_seconds):
        raise ValueError("wait-seconds must be a non-negative finite number.")
    with _project_lock(root):
        plan, digest = _load_plan(root)
        image_path = Path(plan["image"])
        if not image_path.is_file() or native._sha256(image_path) != plan["image_sha256"]:
            raise ValueError("Presenter image changed since planning; create a new plan.")
        auth_path = root / "approval.json"
        if not auth_path.exists() and not confirm:
            raise ValueError("Review plan.json and billing, then run with --confirm-allowance.")
        if not auth_path.exists() and plan_sha256 != digest:
            raise ValueError("Plan does not match the reviewed SHA-256; show and review the plan again.")
        health = doctor()
        if not all(health["ffmpeg"].values()):
            raise ValueError("FFmpeg with subtitles and libx264 is required; run 'dhp make doctor'.")
        if health.get("chinese_font") == "missing":
            raise ValueError("No Chinese font found for subtitles; install one and run 'dhp make doctor'.")
        if auth_path.exists():
            approval = _read_json(auth_path)
            if approval.get("plan_sha256") != digest or not isinstance(approval.get("agent_id"), str):
                raise ValueError("The approved plan changed; create a new project for new inputs.")
            if agent_id and agent_id != approval["agent_id"]:
                raise ValueError("The approved project uses a different Grok Bot.")
        else:
            client = GatewayClient.from_config(gateway_config)
            chosen = _select_bot(client, agent_id)
            approval = {"plan_sha256": digest, "agent_id": chosen, "billing": "existing_allowance",
                        "approved_at": datetime.now(timezone.utc).isoformat(),
                        "notice": "Account billing was not verified by this program."}
            _write_new_json(auth_path, approval)
        client = None
        jobs = []
        for index, text in enumerate(plan["segments"], 1):
            job_dir = root / f"segment-{index:03}"
            jobs.append(str(job_dir))
            if not job_dir.exists():
                client = client or GatewayClient.from_config(gateway_config)
                spec = native.plan(plan["image"], text, approval["agent_id"], str(job_dir),
                                   plan["duration_sec_per_segment"])
                if spec["image_sha256"] != plan["image_sha256"]:
                    raise ValueError("Presenter image changed since planning.")
                job = native.start(spec, client)
            else:
                job = _read_json(job_dir / "job.json")
                expected = job.get("spec")
                if (not isinstance(expected, dict) or expected.get("text") != text
                        or expected.get("image_sha256") != plan["image_sha256"]
                        or expected.get("agent_id") != approval["agent_id"]
                        or expected.get("duration_sec") != plan["duration_sec_per_segment"]):
                    raise ValueError(f"Segment {index} does not match the approved plan.")
            if job.get("status") == "complete":
                job = native.resume(str(job_dir))
            elif job.get("status") in ("accepted", "submitting", "submission_unknown", "result_ready", "downloaded",
                                      "awaiting_approval", "awaiting_result", "needs_attention", "media_unverified"):
                client = client or GatewayClient.from_config(gateway_config)
                job = native._wait(str(job_dir), client, wait_seconds)
            if job.get("status") != "complete":
                attention = job.get("status") in ("prepared", "upload_failed", "awaiting_approval",
                                                   "needs_attention", "media_unverified")
                return {"status": "needs_attention" if attention else "waiting", "project": str(root),
                        "segment": index, "segment_status": job.get("status"),
                        "message": "Inspect the existing job and any bot response before continuing. "
                                   "Existing submissions will not be resent." if attention else
                                   "请求已提交，正在等待最终文件回执。恢复此项目会查询原任务，不会重复提交。",
                        "last_reply": job.get("last_reply")}
        output = root / "result"
        if output.exists():
            report = _read_json(output / "qa.json")
            video = output / "final.mp4"
            segments = report.get("segments")
            if (report.get("status") != "assembled" or not video.is_file()
                    or report.get("presentation") != plan.get("presentation")
                    or native._sha256(video) != report.get("video_sha256")
                    or not isinstance(segments, list) or any(not isinstance(s, dict) for s in segments)
                    or [s.get("sha256") for s in segments]
                    != [_read_json(Path(job) / "job.json").get("expected_sha256") for job in jobs]):
                raise ValueError("Existing result is incomplete or changed; inspect it before retrying.")
        else:
            from .native_assembly import assemble

            report = assemble(jobs, str(output), presentation=plan.get("presentation"))
        return {"status": "ready_for_review", "project": str(root),
                "video": str(output / "final.mp4"), "subtitles": str(output / "subtitles.srt"),
                "qa": str(output / "qa.json"), "segment_count": len(jobs),
                "quality_verdict": report.get("quality_verdict"),
                "notice": "Review speech, lip sync, captions, identity, and voice consistency. "
                          "Subtitle timing is estimated; billing was not verified by this program."}


def restyle_project(project: str, style: str, title: str | None = None,
                    output_dir: str | None = None, *, pack: dict | None = None,
                    request: str | None = None, asr_model: str | None = None) -> dict:
    """Render completed originals locally; never connect to a generation service."""
    from .native_assembly import assemble

    root = Path(project).expanduser().resolve()
    plan, _ = _load_plan(root)
    presentation = packaging.prepare(style, title if title is not None else
                                     plan.get("presentation", {}).get("title", ""), request or plan.get("request", ""), pack)
    jobs = [root / f"segment-{index:03}" for index in range(1, len(plan["segments"]) + 1)]
    for directory, text in zip(jobs, plan["segments"]):
        job = _read_json(directory / "job.json")
        if not isinstance(job.get("spec"), dict) or job["spec"].get("text") != text:
            raise ValueError("Existing job does not match the project script.")
    output = Path(output_dir or _new_output(root / "edits")).expanduser().resolve()
    report = assemble([str(p) for p in jobs], str(output), presentation=presentation,
                      auto_request=request, asr_model=asr_model)
    return {"status": "ready_for_review", "project": str(root), "video": str(output / "final.mp4"),
            "qa": str(output / "qa.json"), "presentation": report["presentation"], "generation_requests": 0,
            "alignment_status": report.get("alignment", {}).get("status", "not_used"),
            "warnings": report.get("warnings", [])}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dhp make")
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("doctor", help="check requirements without generating")
    check.add_argument("--online", action="store_true", help="also check gateway connectivity")
    check.add_argument("--gateway-config")
    create = commands.add_parser("plan", help="prepare a local project and review its segments")
    create.add_argument("--image", required=True)
    text = create.add_mutually_exclusive_group(required=True)
    text.add_argument("--text")
    text.add_argument("--script-file")
    text.add_argument("--brief-file", help="assistant-prepared request, script, title and style")
    create.add_argument("--output-dir", help="default: a new project under outputs/")
    create.add_argument("--style", choices=["auto", *packaging.STYLES], default="auto")
    create.add_argument("--title", default="")
    create.add_argument("--duration", type=int, default=10)
    show = commands.add_parser("show", help="show the exact local plan and its review hash")
    show.add_argument("--project", required=True)
    restyle = commands.add_parser("restyle", help="change packaging locally without generating again")
    edit_source = restyle.add_mutually_exclusive_group(required=True)
    edit_source.add_argument("--project")
    edit_source.add_argument("--job-dir", help="one completed native job; no project import or generation")
    restyle.add_argument("--style", choices=["auto", *packaging.STYLES], default="auto")
    restyle.add_argument("--title")
    restyle.add_argument("--output-dir")
    restyle.add_argument("--pack-file", help="local component timeline JSON; never generates media")
    restyle.add_argument("--request", help="one-sentence local packaging request; selects recipe and tries local ASR")
    restyle.add_argument("--asr-model", help="local Vosk Chinese model directory; otherwise VOSK_MODEL_PATH")
    for name in ("run", "resume"):
        run = commands.add_parser(name, help="run the approved plan" if name == "run" else "continue the approved plan")
        run.add_argument("--project", required=True)
        run.add_argument("--agent-id")
        run.add_argument("--gateway-config")
        run.add_argument("--wait-seconds", type=float, default=120)
        if name == "run":
            run.add_argument("--confirm-allowance", action="store_true",
                             help="confirm all planned segments and the account billing conditions")
            run.add_argument("--plan-sha256", help="hash shown when the plan was reviewed")
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            result = doctor(args.online, args.gateway_config)
        elif args.command == "plan":
            if args.brief_file:
                result = create_brief_plan(args.image, _read_json(Path(args.brief_file)), args.output_dir, args.duration)
            else:
                script = Path(args.script_file).read_text(encoding="utf-8-sig") if args.script_file else args.text
                result = create_plan(args.image, script, args.output_dir, args.duration,
                                     presentation={"style": args.style, "title": args.title})
        elif args.command == "show":
            root = Path(args.project).expanduser().resolve()
            plan, digest = _load_plan(root)
            result = {**plan, "status": "plan_only", "project": str(root), "plan_sha256": digest}
        elif args.command == "restyle":
            pack = _read_json(Path(args.pack_file)) if args.pack_file else None
            if args.project:
                result = restyle_project(args.project, args.style, args.title, args.output_dir,
                                         pack=pack, request=args.request, asr_model=args.asr_model)
            else:
                from .native_assembly import assemble

                output = Path(args.output_dir or _new_output(Path(args.job_dir) / "edits")).resolve()
                report = assemble([args.job_dir], str(output), presentation=packaging.prepare(
                    args.style, args.title or "", args.request or "", pack),
                    auto_request=args.request, asr_model=args.asr_model)
                result = {"status": "ready_for_review", "video": str(output / "final.mp4"),
                          "qa": str(output / "qa.json"), "presentation": report["presentation"],
                          "alignment_status": report.get("alignment", {}).get("status", "not_used"),
                          "warnings": report.get("warnings", []), "generation_requests": 0}
        else:
            result = run_project(args.project, confirm=getattr(args, "confirm_allowance", False),
                                 plan_sha256=getattr(args, "plan_sha256", None),
                                 agent_id=args.agent_id, gateway_config=args.gateway_config,
                                 wait_seconds=args.wait_seconds)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if args.command == "doctor" and (not all(result["ffmpeg"].values())
                                          or result["chinese_font"] == "missing"
                                          or (args.online and result["grok_bot"]["connection"] != "ok")):
            return 1
        return 2 if result.get("status") in ("waiting", "needs_attention") else 0
    except GatewayError as exc:
        print(json.dumps({"status": "connection_unavailable", "message": str(exc),
                          "recovery": _gateway_recovery(exc)}, ensure_ascii=False, indent=2))
        return 1
    except (RuntimeError, ValueError, OSError, subprocess.SubprocessError) as exc:
        print(f"make: {exc}", file=sys.stderr)
        return 1
