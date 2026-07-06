from dwim.config import load_config, DEFAULT_MODEL


def test_load_config_missing_file_uses_default(tmp_path):
    cfg = load_config(str(tmp_path / "nope.toml"))
    assert cfg["model"] == DEFAULT_MODEL


def test_load_config_reads_model(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text('model = "mlx-community/SmolLM2-360M-Instruct-4bit"\n')
    cfg = load_config(str(p))
    assert cfg["model"] == "mlx-community/SmolLM2-360M-Instruct-4bit"
