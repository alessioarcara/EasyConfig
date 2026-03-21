from pathlib import Path
from typing import Any

from easyconfig.config_builder import ConfigBuilder

import pytest


def test_should_instantiate_class_from_file(fake_dataset_file: Path) -> None:
    schema = f"""
    dataset: {fake_dataset_file}:Dataset
    """

    config = f"""
    dataset:
        _target_type_: {fake_dataset_file}:FakeDataset
        _init_args_:
             num_classes: 100
    """

    builder = ConfigBuilder(schema)
    built_config: Any = builder.build(config)

    assert built_config["dataset"].__class__.__name__ == "FakeDataset"
    assert built_config["dataset"].num_classes == 100


@pytest.mark.parametrize("path_kind", ["absolute", "relative"])
def test_happy_path_file(
    path_kind: str,
    fake_dataset_file: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if path_kind == "absolute":
        target = f"{fake_dataset_file}:FakeDataset"
    else:
        monkeypatch.chdir(fake_dataset_file.parent)
        target = "dataset.py:FakeDataset"

    config = f"""
    dataset:
        _target_type_: {target}
        _init_args_:
            num_classes: 100
    """

    config_builder = ConfigBuilder("")
    built_config = config_builder.build(config)

    dataset = built_config["dataset"]
    assert dataset.__class__.__name__ == "FakeDataset"
    assert dataset.num_classes == 100
