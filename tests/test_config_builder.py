from pathlib import Path
from typing import Any

import pytest

from easyconfig.config_builder import ConfigBuilder


def test_should_instantiate_from_package(fake_dataset_package: str) -> None:
    schema = f"""
    dataset: {fake_dataset_package}:Dataset
    """

    config = f"""
    dataset:
        _target_type_: {fake_dataset_package}:FakeDataset
        _init_args_:
             num_classes: 100
    """

    builder = ConfigBuilder(schema)
    built_config: Any = builder.build(config)

    assert built_config.dataset.__class__.__name__ == "FakeDataset"
    assert built_config.dataset.num_classes == 100


@pytest.mark.parametrize("path_kind", ["absolute", "relative"])
def test_should_instantiate_from_file(
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
    training:
        batch_size: 32
    """

    builder = ConfigBuilder("")
    built_config: Any = builder.build(config)

    dataset = built_config["dataset"]
    assert dataset.__class__.__name__ == "FakeDataset"
    assert dataset.num_classes == 100
    assert built_config["training"]["batch_size"] == 32


def test_should_instantiate_multiple_classes(fake_dataset_package: str) -> None:
    schema = f"""
    types:
        Dataset: {fake_dataset_package}:Dataset
    schema:
        datasets: list[Dataset]
    """

    config = f"""
    datasets:
        - _target_type_: {fake_dataset_package}:FakeDataset
          _init_args_:
              num_classes: 100
        - _target_type_: {fake_dataset_package}:FakeDataset
          _init_args_:
              num_classes: 50
    """

    builder = ConfigBuilder(schema)
    built_config: Any = builder.build(config)

    datasets = built_config.datasets
    assert isinstance(datasets, list)
    assert datasets[0].__class__.__name__ == "FakeDataset"
    assert datasets[0].num_classes == 100
    assert datasets[1].__class__.__name__ == "FakeDataset"
    assert datasets[1].num_classes == 50
