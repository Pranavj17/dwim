import os
import subprocess
import pytest

BIN = os.path.join(os.path.dirname(__file__), "..", "bin", "dwim-git")


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "r"
    r.mkdir()
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    run = lambda *a: subprocess.run(["git", "-C", str(r), *a], env=env,
                                    capture_output=True, text=True)
    run("init", "-b", "main")
    (r / "f.txt").write_text("hi")
    run("add", "."); run("commit", "-m", "one")
    run("branch", "feature")
    return r


def dg(repo, *args):
    return subprocess.run([BIN, str(repo), *args], capture_output=True, text=True)


def branches(repo):
    return subprocess.run(["git", "-C", str(repo), "branch", "--format=%(refname:short)"],
                          capture_output=True, text=True).stdout.split()


# --- allowed read-only calls run and succeed -----------------------------
def test_status_runs(repo):
    assert dg(repo, "status", "--short", "--branch").returncode == 0

def test_branch_merged_runs(repo):
    r = dg(repo, "branch", "--merged", "main")
    assert r.returncode == 0 and "feature" in r.stdout

def test_worktree_list_runs(repo):
    r = dg(repo, "worktree", "list")
    assert r.returncode == 0 and str(repo) in r.stdout

def test_log_runs(repo):
    assert dg(repo, "log", "--oneline").returncode == 0


# --- adversarial: every mutating attempt is rejected, nothing changes -----
def test_rejects_branch_delete(repo):
    before = branches(repo)
    r = dg(repo, "branch", "-D", "feature")
    assert r.returncode != 0 and branches(repo) == before   # feature still there

def test_rejects_branch_create(repo):
    before = branches(repo)
    r = dg(repo, "branch", "sneaky")
    assert r.returncode != 0 and branches(repo) == before

def test_rejects_worktree_remove(repo):
    assert dg(repo, "worktree", "remove", "x").returncode != 0

def test_rejects_checkout(repo):
    assert dg(repo, "checkout", "feature").returncode != 0

def test_rejects_unknown_subcommand(repo):
    assert dg(repo, "push").returncode != 0

def test_rejects_flaglike_path(repo):
    assert subprocess.run([BIN, "-C", "status"], capture_output=True, text=True).returncode != 0

def test_rejects_output_flag(repo):
    assert dg(repo, "log", "--output=/tmp/x").returncode != 0

def test_rejects_missing_dir(tmp_path):
    assert subprocess.run([BIN, str(tmp_path / "nope"), "status"],
                          capture_output=True, text=True).returncode != 0
