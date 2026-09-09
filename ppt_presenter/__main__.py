"""CLI for the PowerPoint presenter-action tester."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ppt_presenter.catalog import format_catalog
from ppt_presenter.controller import PresenterController
from ppt_presenter.tester import list_cases, run_suite, select_cases, write_report


def _split_names(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(part.strip() for part in value.split(",") if part.strip())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m ppt_presenter",
        description=(
            "Drive Microsoft PowerPoint presenter actions over COM and verify them. "
            "This is the test harness for a future AI presenter agent."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("probe", help="Check that Python can talk to PowerPoint")
    sub.add_parser("list", help="List presenter actions and live tests")
    sub.add_parser("status", help="Print live status of an already-running slide show")

    test = sub.add_parser("test", help="Create a fixture deck and run live presenter-action tests")
    test.add_argument("--smoke", action="store_true", help="Run only the core navigation/blanking tests")
    test.add_argument(
        "--presenter-view",
        action="store_true",
        help="Also run the fullscreen Presenter View start/advance/exit test",
    )
    test.add_argument("--only", help="Comma-separated test names to run")
    test.add_argument("--skip", help="Comma-separated test names to skip")
    test.add_argument("--delay", type=float, default=0.35, help="Settle time after each COM action")
    test.add_argument("--step", action="store_true", help="Pause after each test for visual checks")
    test.add_argument("--keep-open", action="store_true", help="Leave PowerPoint/show open when finished")
    test.add_argument("--save-fixture", type=Path, help="Save the generated .pptx to this path")
    test.add_argument("--json", type=Path, help="Write a machine-readable report")
    return parser


def cmd_probe() -> int:
    with PresenterController() as ctrl:
        info = ctrl.probe()
    print("PowerPoint COM probe succeeded.")
    print(json.dumps(info, indent=2))
    return 0


def cmd_list() -> int:
    print("Presenter actions")
    print(format_catalog())
    print()
    print("Live tests")
    for case in list_cases():
        tags = ",".join(case.tags)
        print(f"  {case.name:<18} {tags:<22} {case.description}")
    return 0


def cmd_status() -> int:
    ctrl = PresenterController()
    ctrl.connect(start_if_needed=False)
    print(json.dumps(ctrl.status().to_dict(), indent=2))
    return 0


def cmd_test(args: argparse.Namespace) -> int:
    cases = select_cases(
        smoke=args.smoke,
        presenter_view=args.presenter_view,
        only=_split_names(args.only),
        skip=_split_names(args.skip),
    )
    if not cases:
        print("No tests selected.")
        return 2
    print(f"Running {len(cases)} live PowerPoint presenter tests...")
    print("A PowerPoint window will open. Do not click the show until the run finishes.")
    print()
    report = run_suite(
        cases,
        settle_s=args.delay,
        step=args.step,
        presenter_view=args.presenter_view,
        save_fixture=args.save_fixture,
        keep_open=args.keep_open,
    )
    if args.json:
        write_report(report, args.json)
        print(f"Wrote {args.json}")
    return 1 if report.failed else 0


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "probe":
            return cmd_probe()
        if args.command == "list":
            return cmd_list()
        if args.command == "status":
            return cmd_status()
        if args.command == "test":
            return cmd_test(args)
        parser.error(f"unknown command {args.command}")
    except KeyboardInterrupt:
        print("\nInterrupted.")
        return 130
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
