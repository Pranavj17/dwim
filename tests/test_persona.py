"""Personas: prompt-only domain experts selected by word-1 after `@`.

Tests point XDG_CONFIG_HOME at a tmp dir so nothing touches the real
~/.config/dwim/personas.
"""

import os

import pytest

from dwim import persona
from dwim.persona import (ensure_starters, list_personas, load_persona,
                          personas_dir, resolve_persona)


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    return tmp_path


def test_personas_dir_honors_xdg_config_home(cfg):
    d = personas_dir()
    assert d.endswith(os.path.join("dwim", "personas"))
    assert str(cfg / "config") in d


def test_ensure_starters_seeds_git_k8s_sql(cfg):
    ensure_starters()
    d = personas_dir()
    for name in ("git", "k8s", "sql"):
        assert os.path.exists(os.path.join(d, f"{name}.md"))


def test_ensure_starters_is_idempotent_and_preserves_edits(cfg):
    ensure_starters()
    git_path = os.path.join(personas_dir(), "git.md")
    with open(git_path, "w") as f:
        f.write("# my edited git persona\nhands off\n")
    ensure_starters()   # must NOT overwrite an existing file
    assert "my edited git persona" in open(git_path).read()


def test_list_personas_sorted_and_seeds_on_fresh_install(cfg):
    # Fresh install: dir doesn't exist yet — list_personas seeds then lists.
    assert not os.path.exists(personas_dir())
    names = list_personas()
    assert names == sorted(names)
    assert set(names) >= {"git", "k8s", "sql"}


def test_resolve_persona_exact_match_strips_word_one(cfg):
    ensure_starters()
    name, intent = resolve_persona("git undo my last commit")
    assert name == "git"
    assert intent == "undo my last commit"


def test_resolve_persona_non_match_returns_whole_intent(cfg):
    ensure_starters()
    name, intent = resolve_persona("undo my last commit")
    assert name is None
    assert intent == "undo my last commit"


def test_resolve_persona_typo_is_plain_ask(cfg):
    ensure_starters()
    # `gti` is not a persona → the whole line is the intent, no fuzzy match.
    name, intent = resolve_persona("gti undo my last commit")
    assert name is None
    assert intent == "gti undo my last commit"


def test_resolve_persona_case_sensitive(cfg):
    ensure_starters()
    name, intent = resolve_persona("Git status please")
    assert name is None
    assert intent == "Git status please"


def test_resolve_persona_no_dir_returns_none(cfg):
    # No personas dir at all (never seeded) → detection is a pure read: no match,
    # and NO dir created as a side effect.
    assert not os.path.exists(personas_dir())
    name, intent = resolve_persona("git status")
    assert name is None and intent == "git status"
    assert not os.path.exists(personas_dir())   # detection must not create files


def test_resolve_persona_empty_intent(cfg):
    ensure_starters()
    assert resolve_persona("") == (None, "")


def test_resolve_persona_bare_name_only(cfg):
    ensure_starters()
    # Just the persona word, nothing after → empty remainder intent.
    name, intent = resolve_persona("git")
    assert name == "git" and intent == ""


def test_load_persona_returns_text(cfg):
    ensure_starters()
    text = load_persona("git")
    assert "git persona" in text.lower()


def test_load_persona_missing_returns_empty(cfg):
    ensure_starters()
    assert load_persona("nope") == ""


def test_main_personas_lists_starters(cfg, capsys):
    from dwim.__main__ import main
    rc = main(["--personas"])
    assert rc == 0
    out = capsys.readouterr().out
    for name in ("git", "k8s", "sql"):
        assert name in out
    assert personas_dir() in out   # final hint line shows the dir
