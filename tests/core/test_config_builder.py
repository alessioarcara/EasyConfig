from pathlib import Path
from typing import Any

import pytest

from ezconfy.core.config_builder import ConfigBuilder


def _write_temp_yaml(tmpdir: Path, content: str, name: str = "config.yaml") -> Path:
    path = tmpdir / name
    path.write_text(content)
    return path


def test_should_instantiate_from_package(fake_dataset_package: str, tmp_path: Path) -> None:
    schema = f"dataset: {fake_dataset_package}.dataset:Dataset"
    config = f"""
dataset:
    _target_type_: {fake_dataset_package}.dataset:FakeDataset
    _init_args_:
        num_classes: 100
"""

    config_file = _write_temp_yaml(tmp_path, config, "config.yaml")
    schema_file = _write_temp_yaml(tmp_path, schema, "schema.yaml")

    built_config: Any = ConfigBuilder.from_files(config_paths=config_file, schema_path=schema_file)

    assert built_config.dataset.__class__.__name__ == "FakeDataset"
    assert built_config.dataset.num_classes == 100


@pytest.mark.parametrize("path_kind", ["absolute", "relative"])
def test_should_instantiate_from_file(
    path_kind: str,
    fake_dataset_file: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
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

    config_file = _write_temp_yaml(tmp_path, config, "config.yaml")

    built_config: Any = ConfigBuilder.from_files(config_paths=config_file)

    dataset = built_config["dataset"]
    assert dataset.__class__.__name__ == "FakeDataset"
    assert dataset.num_classes == 100
    assert built_config["training"]["batch_size"] == 32


def test_should_instantiate_multiple_classes(fake_dataset_package: str, tmp_path: Path) -> None:
    schema = f"""
types:
    Dataset: {fake_dataset_package}.dataset:Dataset
schema:
    datasets: list[Dataset]
"""
    config = f"""
datasets:
    - _target_type_: {fake_dataset_package}.dataset:FakeDataset
      _init_args_:
          num_classes: 100
    - _target_type_: {fake_dataset_package}.dataset:FakeDataset
      _init_args_:
          num_classes: 50
"""

    config_file = _write_temp_yaml(tmp_path, config, "config.yaml")
    schema_file = _write_temp_yaml(tmp_path, schema, "schema.yaml")

    built_config: Any = ConfigBuilder.from_files(config_paths=config_file, schema_path=schema_file)

    datasets = built_config.datasets
    assert isinstance(datasets, list)
    assert datasets[0].__class__.__name__ == "FakeDataset"
    assert datasets[0].num_classes == 100
    assert datasets[1].__class__.__name__ == "FakeDataset"
    assert datasets[1].num_classes == 50


def test_deep_merge_of_multiple_configs(fake_dataset_package: str, tmp_path: Path) -> None:
    config1 = f"""
dataset:
    _target_type_: {fake_dataset_package}.dataset:FakeDataset
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

    file1 = _write_temp_yaml(tmp_path, config1, "config1.yaml")
    file2 = _write_temp_yaml(tmp_path, config2, "config2.yaml")

    built_config: Any = ConfigBuilder.from_files(config_paths=[file1, file2])

    dataset = built_config["dataset"]
    assert dataset.__class__.__name__ == "FakeDataset"
    assert dataset.num_classes == 100
    assert built_config["training"]["batch_size"] == 32
    assert built_config["training"]["epochs"] == 10
    assert built_config["optimizer"]["type"] == "Adam"


def test_overrides_applied_correctly(fake_dataset_package: str, tmp_path: Path) -> None:
    """Test that overrides dictionary properly overwrites configuration values."""
    config = f"""
dataset:
    _target_type_: {fake_dataset_package}.dataset:FakeDataset
    _init_args_:
        num_classes: 100
training:
    batch_size: 32
    epochs: 10
"""

    overrides = {"dataset": {"_init_args_": {"num_classes": 50}}, "training": {"batch_size": 64}}

    config_file = _write_temp_yaml(tmp_path, config, "config.yaml")

    built_config: Any = ConfigBuilder.from_files(config_paths=config_file, overrides=overrides)

    dataset = built_config["dataset"]
    assert dataset.__class__.__name__ == "FakeDataset"
    assert dataset.num_classes == 50
    assert built_config["training"]["batch_size"] == 64
    assert built_config["training"]["epochs"] == 10


def test_should_instantiate_with_placeholder(fake_dataset_package: str, tmp_path: Path) -> None:
    config = f"""
num_classes: 10
dataset:
    _target_type_: {fake_dataset_package}.dataset:FakeDataset
    _init_args_:
        num_classes: ${{num_classes}}
"""

    config_file = _write_temp_yaml(tmp_path, config, "config.yaml")

    built_config: Any = ConfigBuilder.from_files(config_paths=config_file)

    assert built_config["num_classes"] == 10
    dataset = built_config["dataset"]
    assert dataset.__class__.__name__ == "FakeDataset"
    assert dataset.num_classes == 10


def test_placeholder_attribute_access(fake_dataset_package: str, tmp_path: Path) -> None:
    config = f"""
dataset:
    _target_type_: {fake_dataset_package}.dataset:FakeDataset
    _init_args_:
        num_classes: 5

model:
    _target_type_: {fake_dataset_package}.model:FakeModel
    _init_args_:
        dout: ${{dataset.num_classes}}
"""

    config_file = _write_temp_yaml(tmp_path, config, "config.yaml")

    built_config: Any = ConfigBuilder.from_files(config_paths=config_file)

    model = built_config["model"]
    dataset = built_config["dataset"]

    assert model.dout == 5
    assert dataset.num_classes == 5


def test_instantiate_model_and_optimizer_with_schema(tmp_path: Path) -> None:
    module_content = """
class Model:
    def parameters(self):
        return [1, 2, 3]

class Optimizer:
    def __init__(self, params: list[int]):
        self.params = params
"""
    module_file = _write_temp_yaml(tmp_path, module_content, "mock.py")

    config = f"""
model:
    _target_type_: {module_file}:Model
optimizer:
    _target_type_: {module_file}:Optimizer
    _init_args_:
        params: ${{model.parameters()}}
"""
    config_file = _write_temp_yaml(tmp_path, config, "config.yaml")

    schema = f"""
model: {module_file}:Model
optimizer: {module_file}:Optimizer
"""
    schema_file = _write_temp_yaml(tmp_path, schema, "schema.yaml")

    cfg: Any = ConfigBuilder.from_files(config_paths=config_file, schema_path=schema_file)

    assert cfg.model.__class__.__name__ == "Model"
    assert cfg.optimizer.__class__.__name__ == "Optimizer"
    assert cfg.optimizer.params == [1, 2, 3]


def test_instantiate_with_custom_init_method(tmp_path: Path) -> None:
    module_content = """
class Bert:
    @classmethod
    def from_pretrained(cls, model_name: str):
        instance = cls()
        instance.model_name = model_name
        return instance
"""
    module_file = _write_temp_yaml(tmp_path, module_content, "mock.py")

    config = f"""
bert:
    _target_type_: {module_file}:Bert
    _init_method_: from_pretrained
    _init_args_:
        model_name: bert-base-uncased
"""
    config_file = _write_temp_yaml(tmp_path, config, "config.yaml")

    schema = f"""
bert: {module_file}:Bert
"""
    schema_file = _write_temp_yaml(tmp_path, schema, "schema.yaml")

    cfg: Any = ConfigBuilder.from_files(config_paths=config_file, schema_path=schema_file)

    assert cfg.bert.__class__.__name__ == "Bert"
    assert cfg.bert.model_name == "bert-base-uncased"


def test_extra_config_fields_preserved_when_schema_is_provided(tmp_path: Path) -> None:
    schema = """
lr: float
"""
    config = """
lr: 0.001
wd: 0.0001
"""
    schema_file = _write_temp_yaml(tmp_path, schema, "schema.yaml")
    config_file = _write_temp_yaml(tmp_path, config, "config.yaml")

    cfg: Any = ConfigBuilder.from_files(config_paths=config_file, schema_path=schema_file)

    assert cfg.lr == 0.001
    assert cfg.wd == 0.0001
    print(type(cfg.lr))
    print(type(cfg.wd))
