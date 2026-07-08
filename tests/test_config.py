from dwim.config import load_config, DEFAULT_MODEL


def test_load_config_missing_file_uses_default(tmp_path):
    cfg = load_config(str(tmp_path / "nope.toml"))
    assert cfg["model"] == DEFAULT_MODEL


def test_load_config_reads_model(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text('model = "mlx-community/SmolLM2-360M-Instruct-4bit"\n')
    cfg = load_config(str(p))
    assert cfg["model"] == "mlx-community/SmolLM2-360M-Instruct-4bit"


def test_rag_config_defaults(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))   # no config.toml
    from dwim.config import rag_config
    c = rag_config()
    assert c["roots"] == []          # no implicit corpus — require a path or config
    assert ".md" in c["extensions"] and c["model"].startswith("mlx-community/")

def test_rag_config_override(monkeypatch, tmp_path):
    d = tmp_path / "dwim"; d.mkdir()
    (d / "config.toml").write_text('[rag]\nroots = ["~/notes"]\nmax_file_kb = 50\n')
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from dwim.config import rag_config
    c = rag_config()
    assert c["roots"] == ["~/notes"] and c["max_file_kb"] == 50
    assert ".md" in c["extensions"]                        # defaults kept for unset keys
