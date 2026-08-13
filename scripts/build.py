#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Route a content build to only the requested output channels.

Examples:
    python3 scripts/build.py --channel wechat
    python3 scripts/build.py --channel xhs
    python3 scripts/build.py --channel all

The router validates once, builds the WeChat source frames when needed, and
only invokes the channel-specific renderers selected by the user.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def run(script: str, *args: str, content_path: str | None = None) -> None:
    env = os.environ.copy()
    if content_path:
        env["VIDEO_TO_SOCIAL_CONTENT"] = content_path
    subprocess.run(
        [sys.executable, str(SCRIPTS / script), *args], cwd=ROOT, env=env, check=True
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build selected video-to-social outputs")
    parser.add_argument("--channel", choices=("wechat", "xhs", "all"), default="all")
    parser.add_argument("--content", help="content.py path; defaults to project root")
    args = parser.parse_args()
    content_arg = ["--content", args.content] if args.content else []

    try:
        run("validate_content.py", *content_arg, "--channel", args.channel, content_path=args.content)
        if args.channel in {"wechat", "all"}:
            run("build_wechat.py", content_path=args.content)
            run("make_covers.py", content_path=args.content)
        if args.channel in {"xhs", "all"}:
            # XHS cards reuse the numbered source frames from the WeChat build.
            if args.channel == "xhs":
                run("build_wechat.py", "--frames-only", content_path=args.content)
            run("build_xhs.py", content_path=args.content)
        run("audit_outputs.py", *content_arg, "--channel", args.channel, content_path=args.content)
    except subprocess.CalledProcessError as exc:
        script_name = Path(exc.cmd[1]).name if exc.cmd and len(exc.cmd) > 1 else "unknown"
        print(f"构建失败：{script_name}", file=sys.stderr)
        return exc.returncode or 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
