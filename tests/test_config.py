from loguru import logger

from project_name import config


def test_load_dataset_config_merges_defaults():
    params = {
        "defaults": {"download": {"on_exists": "skip"}},
        "sources": {
            "inegi": {
                "datasets": {
                    "denue_sonora_2024_05": {
                        "name": "DENUE Sonora",
                        "url": "https://example.com/denue.zip",
                    }
                }
            }
        },
    }

    dataset = config.load_dataset_config(params, source="inegi", dataset="denue_sonora_2024_05")

    assert dataset["name"] == "DENUE Sonora"
    assert dataset["download"] == {"on_exists": "skip"}


def test_load_dataset_config_dataset_override_wins_over_default():
    params = {
        "defaults": {"download": {"on_exists": "skip"}},
        "sources": {
            "inegi": {
                "datasets": {
                    "denue_sonora_2024_05": {
                        "download": {"on_exists": "overwrite"},
                    }
                }
            }
        },
    }

    dataset = config.load_dataset_config(params, source="inegi", dataset="denue_sonora_2024_05")

    assert dataset["download"] == {"on_exists": "overwrite"}


def test_load_params_parses_yaml_file(tmp_path, monkeypatch):
    params_file = tmp_path / "params.yml"
    params_file.write_text("logging:\n  level: INFO\nsources:\n  inegi: {}\n")
    monkeypatch.setattr(config, "PARAMS_FILE", params_file)

    params = config.load_params()

    assert params == {"logging": {"level": "INFO"}, "sources": {"inegi": {}}}


def test_load_logging_writes_to_configured_file(tmp_path):
    log_file = tmp_path / "nested" / "test.log"

    config.load_logging(level="INFO", log_file=log_file, console=False)
    with logger.contextualize(job="test"):
        logger.info("hello from test")

    assert log_file.exists()
    assert "hello from test" in log_file.read_text()
