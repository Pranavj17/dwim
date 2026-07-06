from dwim.registry import load_models, resolve_role, backend_status


def test_missing_file_returns_defaults(tmp_path):
    models = load_models(str(tmp_path / "nope.toml"))
    roles = {m["role"] for m in models}
    assert "correct" in roles and "action" in roles


def test_parses_config(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text(
        '[models.qwen]\nbackend="mlx"\nmodel="q"\nrole="correct"\n'
        '[models.sonnet]\nbackend="claude-cli"\nmodel="sonnet"\nrole="action"\n'
    )
    models = load_models(str(p))
    names = {m["name"] for m in models}
    assert names == {"qwen", "sonnet"}
    assert resolve_role("action", str(p))["model"] == "sonnet"


def test_backend_status_claude(monkeypatch):
    import dwim.registry as r
    monkeypatch.setattr(r.shutil, "which", lambda c: "/usr/bin/claude")
    assert backend_status({"backend": "claude-cli"}) == "connected"
    monkeypatch.setattr(r.shutil, "which", lambda c: None)
    assert backend_status({"backend": "claude-cli"}) == "offline"


def test_malformed_toml_falls_back_to_defaults(tmp_path, capsys):
    p = tmp_path / "config.toml"
    p.write_text('[models.qwen\nbackend="mlx"\n')  # missing closing bracket
    models = load_models(str(p))
    roles = {m["role"] for m in models}
    assert "correct" in roles and "action" in roles
    assert "malformed" in capsys.readouterr().err
