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
