from __future__ import annotations

import argparse
import json
from pathlib import Path

from .candidate import run_improvement_loop, decide_promotion
from . import safety
from . import core


def _defaults() -> tuple[Path, Path, Path]:
    root = Path.cwd()
    return root, root / "challenge_data" / "core" / "manifest.json", root / ".cache"


def build_parser() -> argparse.ArgumentParser:
    root, manifest, cache = _defaults()
    parser = argparse.ArgumentParser(prog="replay-challenge")
    parser.add_argument("--root", type=Path, default=root)
    parser.add_argument("--manifest", type=Path, default=manifest)
    parser.add_argument("--cache", type=Path, default=cache)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser(
        "prepare", help="materialize pinned scenarios and trace corpus"
    )
    subparsers.add_parser(
        "check", help="validate prepared inputs and print an inventory"
    )
    gate = subparsers.add_parser(
        "safety-check", help="test your promotion gate independently of learning"
    )
    gate.add_argument("--output", type=Path, required=True)

    smoke = subparsers.add_parser(
        "smoke", help="execute and independently verify the frozen ARE baseline"
    )
    smoke.add_argument("--all", action="store_true")
    smoke.add_argument("--output", type=Path, default=Path("artifacts/smoke"))

    run = subparsers.add_parser("run", help="candidate implementation entrypoint")
    run.add_argument("--corpus", type=Path, required=True)
    run.add_argument("--scenarios", type=Path, required=True)
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--seeds", default="7,19,41")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "safety-check":
        result = safety.run(decide_promotion, args.output)
        print(json.dumps(result, indent=2))
        return 0 if result["passed"] else 1
    if args.command == "run":
        seeds = tuple(int(value) for value in args.seeds.split(",") if value)
        if len(seeds) < 3 or len(seeds) != len(set(seeds)):
            raise SystemExit(
                "run requires at least three distinct seeds, without duplicates"
            )
        return run_improvement_loop(
            corpus_dir=args.corpus,
            scenario_manifest=args.scenarios,
            output_dir=args.output,
            seeds=seeds,
        )
    raw = json.loads(args.manifest.read_text())
    if raw.get("contract") == "tenor-ARE-core-v1" and args.command != "run":
        if args.command == "prepare":
            result = core.prepare(args.manifest, args.cache)
        elif args.command == "check":
            result = core.check(args.manifest, args.cache)
        else:
            result = core.smoke(args.manifest, args.output)
        print(json.dumps(result, indent=2))
        return 0
    if args.command != "run":
        raise SystemExit(
            "unsupported world contract; use challenge_data/core/manifest.json"
        )


if __name__ == "__main__":
    raise SystemExit(main())
