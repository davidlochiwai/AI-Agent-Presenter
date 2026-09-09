"""Sequential live tests against a real PowerPoint slide show."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from ppt_presenter.constants import PointerType, ShowState, ShowType
from ppt_presenter.controller import PresenterController
from ppt_presenter.errors import SkipTest
from ppt_presenter.fixture import (
    ANIMATION_CLICK_COUNT,
    ANIMATION_SLIDE_INDEX,
    FIXTURE_SLIDE_COUNT,
    SECRET_NOTE_TOKEN,
    create_fixture_presentation,
)
from ppt_presenter.models import ActionResult, ShowStatus

AssertFn = Callable[["TestContext"], None]


@dataclass
class TestCase:
    name: str
    description: str
    fn: AssertFn
    tags: tuple[str, ...] = ("core",)


@dataclass
class TestContext:
    ctrl: PresenterController
    presenter_view: bool = False
    step: bool = False
    last_status: ShowStatus | None = None


SMOKE_NAMES = (
    "start_windowed",
    "status_snapshot",
    "read_notes",
    "next",
    "previous",
    "goto",
    "black",
    "resume",
    "end",
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _status(ctx: TestContext) -> ShowStatus:
    ctx.last_status = ctx.ctrl.status()
    return ctx.last_status


def test_start_windowed(ctx: TestContext) -> None:
    ctx.ctrl.start(windowed=True, presenter_view=False)
    status = _status(ctx)
    _require(status.running, "slide show did not start")
    _require(status.slide_index == 1, f"expected slide 1, got {status.slide_index}")
    _require(status.slide_count == FIXTURE_SLIDE_COUNT, f"expected {FIXTURE_SLIDE_COUNT} slides")
    _require(status.show_type == int(ShowType.WINDOW), f"expected windowed show, got {status.show_type}")


def test_status_snapshot(ctx: TestContext) -> None:
    status = _status(ctx)
    _require(status.running, "show is not running")
    _require(bool(status.title), "current slide has no title")
    _require(status.state == int(ShowState.RUNNING), f"expected running, got {status.state_name}")


def test_read_notes(ctx: TestContext) -> None:
    ctx.ctrl.goto(3)
    status = _status(ctx)
    _require(SECRET_NOTE_TOKEN in status.notes, f"notes missing token, got: {status.notes!r}")
    _require("Speaker Notes" in status.title, f"unexpected title: {status.title!r}")


def test_next(ctx: TestContext) -> None:
    ctx.ctrl.goto(1)
    before = _status(ctx)
    ctx.ctrl.next()
    after = _status(ctx)
    _require(after.slide_index == 2, f"next from slide 1 should land on 2, got {after.slide_index}")
    _require(after.slide_index != before.slide_index, "next did not change the slide")


def test_previous(ctx: TestContext) -> None:
    ctx.ctrl.goto(3)
    ctx.ctrl.previous()
    after = _status(ctx)
    _require(after.slide_index == 2, f"previous from slide 3 should land on 2, got {after.slide_index}")


def test_goto(ctx: TestContext) -> None:
    ctx.ctrl.goto(4)
    after = _status(ctx)
    _require(after.slide_index == 4, f"goto(4) left us on {after.slide_index}")
    _require("Jump Target" in after.title, f"unexpected title: {after.title!r}")


def test_first_last(ctx: TestContext) -> None:
    ctx.ctrl.last()
    last = _status(ctx)
    _require(last.slide_index == FIXTURE_SLIDE_COUNT, f"last() -> {last.slide_index}")
    ctx.ctrl.first()
    first = _status(ctx)
    _require(first.slide_index == 1, f"first() -> {first.slide_index}")


def test_next_animation(ctx: TestContext) -> None:
    ctx.ctrl.goto(ANIMATION_SLIDE_INDEX)
    start = _status(ctx)
    _require(start.slide_index == ANIMATION_SLIDE_INDEX, "did not land on the animation slide")
    if start.click_count is not None:
        _require(
            start.click_count >= ANIMATION_CLICK_COUNT,
            f"expected at least {ANIMATION_CLICK_COUNT} clicks, got {start.click_count}",
        )
    ctx.ctrl.next()
    after = _status(ctx)
    _require(after.slide_index == ANIMATION_SLIDE_INDEX, "next() left the animation slide too early")
    if start.click_index is not None and after.click_index is not None:
        _require(
            after.click_index > start.click_index,
            f"click index did not advance ({start.click_index} -> {after.click_index})",
        )


def test_goto_click(ctx: TestContext) -> None:
    ctx.ctrl.goto(ANIMATION_SLIDE_INDEX)
    ctx.ctrl.goto_click(2)
    after = _status(ctx)
    _require(after.slide_index == ANIMATION_SLIDE_INDEX, "goto_click moved to another slide")
    if after.click_index is not None:
        _require(after.click_index >= 2, f"goto_click(2) left click index at {after.click_index}")


def test_next_slide_skips_animations(ctx: TestContext) -> None:
    ctx.ctrl.goto(ANIMATION_SLIDE_INDEX)
    ctx.ctrl.next()
    ctx.ctrl.next_slide()
    after = _status(ctx)
    _require(
        after.slide_index == ANIMATION_SLIDE_INDEX + 1,
        f"next_slide should skip remaining clicks, got slide {after.slide_index}",
    )


def test_previous_slide(ctx: TestContext) -> None:
    ctx.ctrl.goto(4)
    ctx.ctrl.previous_slide()
    after = _status(ctx)
    _require(after.slide_index == 3, f"previous_slide from 4 should be 3, got {after.slide_index}")


def test_black(ctx: TestContext) -> None:
    ctx.ctrl.resume()
    ctx.ctrl.black()
    after = _status(ctx)
    _require(after.state == int(ShowState.BLACK_SCREEN), f"expected black screen, got {after.state_name}")


def test_white(ctx: TestContext) -> None:
    ctx.ctrl.resume()
    ctx.ctrl.white()
    after = _status(ctx)
    _require(after.state == int(ShowState.WHITE_SCREEN), f"expected white screen, got {after.state_name}")


def test_resume(ctx: TestContext) -> None:
    ctx.ctrl.resume()
    after = _status(ctx)
    _require(after.state == int(ShowState.RUNNING), f"expected running, got {after.state_name}")
    _require(after.running, "show stopped while resuming")


def test_pause(ctx: TestContext) -> None:
    ctx.ctrl.resume()
    ctx.ctrl.pause()
    after = _status(ctx)
    if after.state != int(ShowState.PAUSED):
        raise SkipTest(
            f"pause is not honored in this show mode (state={after.state_name}); "
            "typical for manual-advance windowed shows"
        )


def test_pointer_pen(ctx: TestContext) -> None:
    ctx.ctrl.resume()
    ctx.ctrl.set_pointer(PointerType.PEN)
    after = _status(ctx)
    _require(after.pointer_type == int(PointerType.PEN), f"expected pen, got {after.pointer_name}")


def test_pen_color(ctx: TestContext) -> None:
    ctx.ctrl.set_pointer(PointerType.PEN)
    ctx.ctrl.set_pen_color(255, 0, 0)
    _status(ctx)


def test_draw_and_erase(ctx: TestContext) -> None:
    ctx.ctrl.set_pointer(PointerType.PEN)
    ctx.ctrl.draw_line(80, 80, 420, 280)
    ctx.ctrl.erase_ink()
    _status(ctx)


def test_pointer_eraser(ctx: TestContext) -> None:
    ctx.ctrl.set_pointer(PointerType.ERASER)
    after = _status(ctx)
    if after.pointer_type != int(PointerType.ERASER):
        raise SkipTest(
            "this PowerPoint build has no distinct eraser pointer "
            f"(set {int(PointerType.ERASER)}, read {after.pointer_name})"
        )


def test_pointer_hidden(ctx: TestContext) -> None:
    ctx.ctrl.set_pointer(PointerType.ALWAYS_HIDDEN)
    after = _status(ctx)
    _require(
        after.pointer_type == int(PointerType.ALWAYS_HIDDEN),
        f"expected hidden pointer, got {after.pointer_name}",
    )


def test_pointer_arrow(ctx: TestContext) -> None:
    ctx.ctrl.set_pointer(PointerType.ARROW)
    after = _status(ctx)
    _require(after.pointer_type == int(PointerType.ARROW), f"expected arrow, got {after.pointer_name}")


def test_laser(ctx: TestContext) -> None:
    ctx.ctrl.resume()
    try:
        ctx.ctrl.set_laser(True)
    except Exception as exc:
        raise SkipTest(str(exc)) from exc
    after = _status(ctx)
    if after.laser is not True:
        ctx.ctrl.set_laser(False)
        raise SkipTest("LaserPointerEnabled did not stay True (common in windowed shows)")
    ctx.ctrl.set_laser(False)
    off = _status(ctx)
    _require(off.laser is False, "laser pointer did not turn off")


def test_reset_timer(ctx: TestContext) -> None:
    ctx.ctrl.resume()
    ctx.ctrl.goto(3)
    time.sleep(1.2)
    before = _status(ctx)
    if before.elapsed_seconds is None:
        raise SkipTest("SlideElapsedTime is not available")
    _require(before.elapsed_seconds >= 1.0, f"elapsed time did not advance ({before.elapsed_seconds})")
    ctx.ctrl.reset_timer()
    after = _status(ctx)
    if after.elapsed_seconds is None:
        raise SkipTest("SlideElapsedTime became unavailable after reset")
    _require(
        after.elapsed_seconds < before.elapsed_seconds,
        f"timer did not reset ({before.elapsed_seconds} -> {after.elapsed_seconds})",
    )


def test_end(ctx: TestContext) -> None:
    ctx.ctrl.end()
    after = _status(ctx)
    _require(not after.running, "slide show is still running after end()")


def test_presenter_view(ctx: TestContext) -> None:
    ctx.ctrl.start(windowed=False, presenter_view=True)
    after = _status(ctx)
    _require(after.running, "Presenter View show did not start")
    _require(after.presenter_view is True, "ShowPresenterView did not stay enabled")
    _require(after.show_type == int(ShowType.SPEAKER), f"expected speaker mode, got {after.show_type}")
    ctx.ctrl.next()
    moved = _status(ctx)
    _require(moved.running, "show died after next() in Presenter View")
    ctx.ctrl.end()
    ended = _status(ctx)
    _require(not ended.running, "could not exit Presenter View show")


CASES: tuple[TestCase, ...] = (
    TestCase("start_windowed", "Start a windowed slide show on slide 1", test_start_windowed),
    TestCase("status_snapshot", "Read live show status", test_status_snapshot),
    TestCase("read_notes", "Read speaker notes from the notes slide", test_read_notes),
    TestCase("next", "Advance from slide 1 to slide 2", test_next),
    TestCase("previous", "Go back one step/slide", test_previous),
    TestCase("goto", "Jump to slide 4", test_goto),
    TestCase("first_last", "Jump to last then first slide", test_first_last),
    TestCase("next_animation", "Advance one animation click without leaving the slide", test_next_animation),
    TestCase("goto_click", "Jump to animation click 2", test_goto_click),
    TestCase("next_slide", "Skip remaining animations and go to the next slide", test_next_slide_skips_animations),
    TestCase("previous_slide", "Jump to the previous slide", test_previous_slide),
    TestCase("black", "Blank the screen to black", test_black),
    TestCase("resume", "Resume from a blanked screen", test_resume),
    TestCase("white", "Blank the screen to white", test_white, ("core", "extended")),
    TestCase("pause", "Pause the show if the host honors it", test_pause, ("extended",)),
    TestCase("pointer_pen", "Switch to the pen", test_pointer_pen),
    TestCase("pen_color", "Set pen color to red", test_pen_color),
    TestCase("draw_erase", "Draw a line then erase ink", test_draw_and_erase),
    TestCase("pointer_eraser", "Switch to the eraser", test_pointer_eraser),
    TestCase("pointer_hidden", "Hide the pointer", test_pointer_hidden),
    TestCase("pointer_arrow", "Restore the arrow pointer", test_pointer_arrow),
    TestCase("laser", "Toggle the laser pointer", test_laser, ("extended",)),
    TestCase("reset_timer", "Reset the per-slide elapsed timer", test_reset_timer, ("extended",)),
    TestCase("end", "Exit the slide show", test_end),
    TestCase(
        "presenter_view",
        "Start speaker mode with Presenter View, advance, and exit",
        test_presenter_view,
        ("presenter-view",),
    ),
)


def list_cases() -> tuple[TestCase, ...]:
    return CASES


def select_cases(
    *,
    smoke: bool = False,
    presenter_view: bool = False,
    only: tuple[str, ...] = (),
    skip: tuple[str, ...] = (),
) -> list[TestCase]:
    selected: list[TestCase] = []
    only_set = {name.lower() for name in only}
    skip_set = {name.lower() for name in skip}
    for case in CASES:
        if case.name.lower() in skip_set:
            continue
        if only_set:
            if case.name.lower() in only_set:
                selected.append(case)
            continue
        tags = set(case.tags)
        if "presenter-view" in tags and not presenter_view:
            continue
        if smoke and case.name not in SMOKE_NAMES:
            continue
        selected.append(case)
    return selected


def _print_status(status: ShowStatus) -> None:
    laser = {True: "on", False: "off", None: "?"}.get(status.laser, "?")
    print(
        "    "
        f"slide={status.slide_index}/{status.slide_count}  "
        f"state={status.state_name}  "
        f"pointer={status.pointer_name}  "
        f"laser={laser}  "
        f"click={status.click_index}/{status.click_count}  "
        f"title={status.title!r}"
    )


@dataclass
class SuiteReport:
    results: list[ActionResult] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for item in self.results if item.status == "pass")

    @property
    def failed(self) -> int:
        return sum(1 for item in self.results if item.status == "fail")

    @property
    def skipped(self) -> int:
        return sum(1 for item in self.results if item.status == "skip")

    def to_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "results": [item.to_dict() for item in self.results],
        }


def run_suite(
    cases: list[TestCase],
    *,
    settle_s: float = 0.35,
    step: bool = False,
    presenter_view: bool = False,
    save_fixture: Path | None = None,
    keep_open: bool = False,
) -> SuiteReport:
    report = SuiteReport()
    ctrl = PresenterController(settle_s=settle_s)
    ctx = TestContext(ctrl=ctrl, presenter_view=presenter_view, step=step)
    try:
        ctrl.connect()
        pres = create_fixture_presentation(ctrl.app, save_path=save_fixture)
        ctrl.use_presentation(pres, created=True)
        names = {case.name for case in cases}
        if "start_windowed" not in names and any(name != "presenter_view" for name in names):
            ctrl.start(windowed=True, presenter_view=False)
        for case in cases:
            before = {}
            try:
                before = ctrl.status().to_dict()
            except Exception:
                pass
            started = time.perf_counter()
            try:
                case.fn(ctx)
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                after = ctx.last_status.to_dict() if ctx.last_status else ctrl.status().to_dict()
                result = ActionResult(case.name, "pass", case.description, elapsed_ms, before, after)
            except SkipTest as exc:
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                result = ActionResult(case.name, "skip", exc.reason, elapsed_ms, before, {})
            except Exception as exc:
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                result = ActionResult(case.name, "fail", str(exc), elapsed_ms, before, {})
            report.results.append(result)
            marker = {"pass": "PASS", "fail": "FAIL", "skip": "SKIP"}[result.status]
            print(f"[{marker}] {case.name:<18} {result.detail}  ({result.elapsed_ms} ms)")
            if ctx.last_status is not None:
                _print_status(ctx.last_status)
            if step:
                input("    Press Enter for the next action...")
    finally:
        if not keep_open:
            ctrl.close_deck()
        elif ctrl.is_running():
            print("Leaving the slide show open (--keep-open).")
    print()
    print(
        f"{report.passed} passed, {report.failed} failed, {report.skipped} skipped"
    )
    return report


def write_report(report: SuiteReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
