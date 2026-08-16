# -*- coding: utf-8 -*-
"""Pipeline CLI。

用法：
    python -m src.pipeline.cli run --config configs/pipeline.toml --method equal
    python -m src.pipeline.cli runs
    python -m src.pipeline.cli show --run-id <run_id>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.pipeline.config import PipelineConfig
from src.pipeline.orchestrator import PipelineRunner


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pipeline", description="多源数据自动化 Pipeline CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="执行完整自动化 Pipeline")
    run.add_argument("--config", type=str, default="configs/pipeline.toml")
    run.add_argument("--method", choices=["equal", "entropy"], default=None, help="覆盖配置文件中的权重方案")

    sub.add_parser("runs", help="查看最近运行记录")

    show = sub.add_parser("show", help="查看单次运行详情")
    show.add_argument("--run-id", required=True)
    return parser


def _load_config(path: str, method: str | None) -> PipelineConfig:
    cfg = PipelineConfig.from_toml(path)
    if method:
        cfg.method = method
    return cfg


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "run":
        cfg = _load_config(args.config, args.method)
        result = PipelineRunner(cfg).run()
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0 if result.status == "succeeded" else 1

    if args.command in ("runs", "show"):
        from src.storage.run_store import RunStore

        store = RunStore(Path("data/platform.db"))
        store.initialize()
        if args.command == "runs":
            for run in store.list_runs():
                print(
                    f"{run['run_id'][:12]}  {run['status']:<10}  {run['method']:<8}  "
                    f"{run.get('started_at') or ''}  {run.get('duration_ms', '')}ms"
                )
        else:
            run = store.get_run(args.run_id)
            if run is None:
                print(f"run_id 不存在: {args.run_id}", file=sys.stderr)
                return 1
            print(json.dumps(run, ensure_ascii=False, indent=2))
        store.close()
        return 0

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
