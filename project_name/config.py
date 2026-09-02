from pathlib import Path
import sys

from loguru import logger
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PARAMS_FILE = PROJECT_ROOT / "params.yml"


def load_params() -> dict:
    with PARAMS_FILE.open() as file:
        return yaml.safe_load(file)


def load_dataset_config(params: dict, source: str, dataset: str) -> dict:
    defaults = params["defaults"]["download"]
    config = params["sources"][source]["datasets"][dataset]

    return {
        **config,
        "download": {
            **defaults,
            **config.get("download", {}),
        },
    }


def load_logging(level: str, log_file: Path, console: bool = False) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)

    logger.remove()

    logger.add(
        log_file,
        level=level,
        format=("{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {extra[job]} | {message}"),
    )

    if console:
        logger.add(sys.stderr, level=level)
