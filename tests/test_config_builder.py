import tempfile
from pathlib import Path
from typing import Any

import pytest

from easyconfig.config_builder import ConfigBuilder


def _write_temp_yaml(tmpdir: Path, content: str, name: str = "config.yaml") -> Path:
    path = tmpdir / name
    path.write_text(content)
    return path


def test_should_instantiate_from_package(fake_dataset_package: str) -> None:
    schema = f"dataset: {fake_dataset_package}:Dataset"
    config = f"""
dataset:
    _target_type_: {fake_dataset_package}:FakeDataset
    _init_args_:
        num_classes: 100
"""

    with tempfile.TemporaryDirectory() as tmpdir_str:
        tmpdir = Path(tmpdir_str)
        config_file = _write_temp_yaml(tmpdir, config, "config.yaml")
        schema_file = _write_temp_yaml(tmpdir, schema, "schema.yaml")

        built_config: Any = ConfigBuilder.from_files(config_paths=config_file, schema_path=schema_file)

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

    with tempfile.TemporaryDirectory() as tmpdir_str:
        tmpdir = Path(tmpdir_str)
        config_file = _write_temp_yaml(tmpdir, config, "config.yaml")

        built_config: Any = ConfigBuilder.from_files(config_paths=config_file)

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

    with tempfile.TemporaryDirectory() as tmpdir_str:
        tmpdir = Path(tmpdir_str)
        config_file = _write_temp_yaml(tmpdir, config, "config.yaml")
        schema_file = _write_temp_yaml(tmpdir, schema, "schema.yaml")

        built_config: Any = ConfigBuilder.from_files(config_paths=config_file, schema_path=schema_file)

        datasets = built_config.datasets
        assert isinstance(datasets, list)
        assert datasets[0].__class__.__name__ == "FakeDataset"
        assert datasets[0].num_classes == 100
        assert datasets[1].__class__.__name__ == "FakeDataset"
        assert datasets[1].num_classes == 50


def test_deep_merge_of_multiple_configs(fake_dataset_package: str) -> None:
    config1 = f"""
dataset:
    _target_type_: {fake_dataset_package}:FakeDataset
    _init_args_:
        num_classes: 100
training:
    batch_size: 32
"""
    config2 = """
training:
    epochs: 10
optimizer:
    type: Adam
"""

    with tempfile.TemporaryDirectory() as tmpdir_str:
        tmpdir = Path(tmpdir_str)
        file1 = _write_temp_yaml(tmpdir, config1, "config1.yaml")
        file2 = _write_temp_yaml(tmpdir, config2, "config2.yaml")

        built_config: Any = ConfigBuilder.from_files(config_paths=[file1, file2])

        # Dataset is still correct
        dataset = built_config["dataset"]
        assert dataset.__class__.__name__ == "FakeDataset"
        assert dataset.num_classes == 100

        # Training values are merged
        assert built_config["training"]["batch_size"] == 32
        assert built_config["training"]["epochs"] == 10

        # Optimizer is present
        assert built_config["optimizer"]["type"] == "Adam"


def test_overrides_applied_correctly(fake_dataset_package: str) -> None:
    """Test that overrides dictionary properly overwrites configuration values."""
    config = f"""
dataset:
    _target_type_: {fake_dataset_package}:FakeDataset
    _init_args_:
        num_classes: 100
training:
    batch_size: 32
    epochs: 10
"""

    overrides = {"dataset": {"_init_args_": {"num_classes": 50}}, "training": {"batch_size": 64}}

    with tempfile.TemporaryDirectory() as tmpdir_str:
        tmpdir = Path(tmpdir_str)
        config_file = _write_temp_yaml(tmpdir, config, "config.yaml")

        built_config: Any = ConfigBuilder.from_files(config_paths=config_file, overrides=overrides)

        # Dataset overridden
        dataset = built_config["dataset"]
        assert dataset.__class__.__name__ == "FakeDataset"
        assert dataset.num_classes == 50

        # Training overridden
        assert built_config["training"]["batch_size"] == 64
        # Non-overridden values remain
        assert built_config["training"]["epochs"] == 10
