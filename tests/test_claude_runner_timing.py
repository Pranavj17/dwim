"""The @ panel used to show only the last shell command's duration (executor.py's
`run_captured`), e.g. `· 0.03s` — the several seconds the `claude -p` agent itself
spent thinking were never timed or shown. These tests pin down that `_StreamUI`
now measures its own start()->finish() wall-clock time and surfaces it in the
breadcrumb, including for a tool-less answer (zero steps)."""

import io

from dwim import claude_runner as cr


def test_streamui_breadcrumb_includes_agent_elapsed_time(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    times = iter([100.0, 103.2])
    monkeypatch.setattr(cr.time, "perf_counter", lambda: next(times))
    out = io.StringIO()
    ui = cr._StreamUI("dwim · haiku", out=out)
    ui.start()
    ui.step("git config --get user.name")
    ui.finish()
    shown = out.getvalue()
    assert "3.2s" in shown
    assert "git" in shown               # existing crumb content preserved


def test_streamui_breadcrumb_shows_elapsed_with_zero_steps(monkeypatch, tmp_path):
    # A tool-less @ answer produces no step crumbs, so _breadcrumb() used to
    # return "" and finish() printed nothing — the model's thinking time was
    # shown nowhere at all. It must now still print a minimal timing line.
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    times = iter([100.0, 101.5])
    monkeypatch.setattr(cr.time, "perf_counter", lambda: next(times))
    out = io.StringIO()
    ui = cr._StreamUI("dwim · haiku", out=out)
    ui.start()
    ui.finish()
    shown = out.getvalue()
    assert shown.strip() != ""
    assert "1.5s" in shown
