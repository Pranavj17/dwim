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


def worktrees(repo):
    return subprocess.run(["git", "-C", str(repo), "worktree", "list"],
                          capture_output=True, text=True).stdout


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


# --- regression: lock in the read-only invariant against a wider attack surface ---

# 1. branch mutation flags: each must be rejected, no branch state change.
@pytest.mark.parametrize("flag", [
    ["-m", "old"],
    ["-M", "old", "new"],
    ["-c", "x"],
    ["-C", "x"],
    ["-f", "feature", "HEAD"],
    ["-u", "origin/x"],
    ["--set-upstream-to=origin/x"],
    ["--edit-description"],
    ["--create-reflog", "x"],
])
def test_rejects_branch_mutation_flags(repo, flag):
    before = branches(repo)
    r = dg(repo, "branch", *flag)
    assert r.returncode != 0
    assert branches(repo) == before


# 2. two-positional create-past-tracker: `branch --merged main evil` must NOT
# be read as "list merged into main" + create "evil". Only a single trailing
# positional (the commit-ish for --merged/--contains) is allowed.
def test_rejects_branch_merged_with_extra_positional_creates_nothing(repo):
    before = branches(repo)
    r = dg(repo, "branch", "--merged", "main", "evil")
    assert r.returncode != 0
    assert branches(repo) == before
    assert "evil" not in branches(repo)


def test_rejects_branch_contains_with_extra_positional_creates_nothing(repo):
    before = branches(repo)
    r = dg(repo, "branch", "--contains", "HEAD", "newbranch")
    assert r.returncode != 0
    assert branches(repo) == before
    assert "newbranch" not in branches(repo)


def test_allows_branch_merged_single_commit_arg(repo):
    r = dg(repo, "branch", "--merged", "main")
    assert r.returncode == 0


# 3. worktree: only bare `worktree list` is allowed; every other worktree
# form (including a flag placed before `list`) is rejected and mutates nothing.
def test_rejects_worktree_add(repo):
    before = worktrees(repo)
    r = dg(repo, "worktree", "add", "../x")
    assert r.returncode != 0
    assert worktrees(repo) == before


def test_rejects_worktree_prune(repo):
    before = worktrees(repo)
    r = dg(repo, "worktree", "prune")
    assert r.returncode != 0
    assert worktrees(repo) == before


def test_rejects_worktree_lock(repo):
    before = worktrees(repo)
    r = dg(repo, "worktree", "lock")
    assert r.returncode != 0
    assert worktrees(repo) == before


def test_rejects_worktree_flag_before_list(repo):
    before = worktrees(repo)
    r = dg(repo, "worktree", "--porcelain", "list")
    assert r.returncode != 0
    assert worktrees(repo) == before


# 4. output-flag variants: -o/--output/--output= must all be rejected on
# subcommands that would otherwise write a file, regardless of spelling.
def _no_such_file(path):
    assert not os.path.exists(path)


def test_rejects_log_output_flag_space_form(repo):
    target = "/tmp/dwimx_test_space"
    if os.path.exists(target):
        os.remove(target)
    r = dg(repo, "log", "--output", target)
    assert r.returncode != 0
    _no_such_file(target)


def test_rejects_log_o_flag(repo):
    target = "/tmp/dwimx_test_o"
    if os.path.exists(target):
        os.remove(target)
    r = dg(repo, "log", "-o", target)
    assert r.returncode != 0
    _no_such_file(target)


def test_rejects_diff_output_equals_flag(repo):
    target = "/tmp/dwimx_test_eq"
    if os.path.exists(target):
        os.remove(target)
    r = dg(repo, "diff", "--output=" + target)
    assert r.returncode != 0
    _no_such_file(target)


# 5. mutating/unlisted subcommands: none are on the allowlist, so all must
# be rejected outright.
@pytest.mark.parametrize("sub", [
    "reset", "clean", "gc", "config", "commit", "tag", "stash", "fetch",
    "restore", "switch", "for-each-ref", "update-ref",
])
def test_rejects_mutating_subcommands(repo, sub):
    assert dg(repo, sub).returncode != 0


# 6. path argument must be a directory; a file path is rejected even if it
# exists and is readable.
def test_rejects_file_as_path(repo):
    f = repo / "f.txt"
    assert f.is_file()
    r = subprocess.run([BIN, str(f), "status"], capture_output=True, text=True)
    assert r.returncode != 0


# 7. command-injection-shaped args are passed as literal argv to git (no
# shell involved) — a fake "second command" must never be executed.
def test_injection_shaped_args_are_literal_not_executed(repo):
    r = dg(repo, "status", ";", "echo", "PWNED")
    # Either git rejects the bogus pathspecs (non-zero) or treats them as
    # harmless non-matching pathspecs (zero) - either way, no shell ever
    # ran "echo PWNED", so it must never appear in stdout.
    assert "PWNED" not in r.stdout
    assert "PWNED" not in r.stderr


# --- quoted-subcommand form (agent passes "worktree list" as ONE arg) --------
def test_quoted_worktree_list_runs(repo):
    r = dg(repo, "worktree list")
    assert r.returncode == 0 and str(repo) in r.stdout

def test_quoted_branch_merged_runs(repo):
    r = dg(repo, "branch --merged main")
    assert r.returncode == 0 and "feature" in r.stdout

def test_quoted_status_with_flags_runs(repo):
    assert dg(repo, "status --short --branch").returncode == 0

def test_quoted_mutations_still_rejected(repo):
    before_b, before_w = branches(repo), worktrees(repo)
    for bad in ["worktree remove x", "branch -D feature", "branch sneaky",
                "status; rm x", "checkout feature", "worktree add ../x"]:
        assert dg(repo, bad).returncode != 0, f"{bad!r} was NOT rejected"
    assert branches(repo) == before_b and worktrees(repo) == before_w
