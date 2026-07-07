import os
import subprocess

LOCATE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "bin", "dwim-locate")


def _run(args):
    return subprocess.run([LOCATE, *args], capture_output=True, text=True)


def test_locate_finds_by_name(tmp_path):
    (tmp_path / "the-daily-you-app").mkdir()
    (tmp_path / "other").mkdir()
    r = _run(["daily", str(tmp_path)])
    assert r.returncode == 0
    assert "the-daily-you-app" in r.stdout
    assert "other" not in r.stdout


def test_locate_excludes_git_and_node_modules(tmp_path):
    (tmp_path / "node_modules" / "daily-pkg").mkdir(parents=True)
    (tmp_path / "real-daily").mkdir()
    r = _run(["daily", str(tmp_path)])
    assert "real-daily" in r.stdout
    assert "node_modules" not in r.stdout


def test_locate_rejects_flaglike_name(tmp_path):
    before = set(os.listdir(tmp_path))
    r = _run(["-delete", str(tmp_path)])
    assert r.returncode == 2                      # refused, nothing run
    assert set(os.listdir(tmp_path)) == before    # no mutation


def test_locate_rejects_shell_metacharacters(tmp_path):
    r = _run(["x; touch " + str(tmp_path / "pwned"), str(tmp_path)])
    assert r.returncode == 2
    assert not (tmp_path / "pwned").exists()


def test_locate_empty_name_usage(tmp_path):
    r = _run([])
    assert r.returncode == 2


def test_locate_rejects_flaglike_root(tmp_path):
    (tmp_path / "-delete").mkdir()
    (tmp_path / "-delete" / "victim.txt").write_text("x")
    r = subprocess.run([LOCATE, "victim", "-delete"],
                       capture_output=True, text=True, cwd=str(tmp_path))
    assert r.returncode == 2
    assert (tmp_path / "-delete" / "victim.txt").exists()   # nothing deleted


def test_locate_root_injection_safe_without_fd(tmp_path):
    # Force the find fallback (no fd on PATH); a flag-like root must still be
    # refused before GNU find's -delete path can trigger.
    (tmp_path / "-delete").mkdir()
    (tmp_path / "-delete" / "victim.txt").write_text("x")
    env = dict(os.environ, PATH="/usr/bin:/bin")
    r = subprocess.run([LOCATE, "victim", "-delete"],
                       capture_output=True, text=True, cwd=str(tmp_path), env=env)
    assert r.returncode == 2
    assert (tmp_path / "-delete" / "victim.txt").exists()


def test_locate_many_matches_exits_zero(tmp_path):
    # >64KB of match output makes head close early → producer SIGPIPE. A
    # successful search must still exit 0 (not 1/141) and cap at 50 lines.
    for i in range(1500):
        (tmp_path / f"daily{i:04d}").mkdir()
    r = subprocess.run([LOCATE, "daily", str(tmp_path)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.returncode
    assert 0 < len(r.stdout.splitlines()) <= 50


def test_locate_permission_denied_exits_zero(tmp_path):
    # find branch (fd scrubbed) hitting an unreadable subdir is best-effort,
    # not a failure. Skip if running as root (can read anything).
    if os.geteuid() == 0:
        import pytest; pytest.skip("root bypasses permission checks")
    (tmp_path / "real-daily").mkdir()
    locked = tmp_path / "locked"; locked.mkdir()
    (locked / "inner").mkdir()
    os.chmod(locked, 0o000)
    try:
        env = dict(os.environ, PATH="/usr/bin:/bin")   # force find branch
        r = subprocess.run([LOCATE, "daily", str(tmp_path)],
                           capture_output=True, text=True, env=env)
        assert r.returncode == 0, r.returncode
        assert "real-daily" in r.stdout
    finally:
        os.chmod(locked, 0o755)      # restore so pytest can clean up tmp_path
