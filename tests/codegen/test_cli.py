import ast
import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

from ezconfy.codegen import run_generation
from ezconfy.core.schema_parser import SchemaParser

flat_schema = """
wandb_run_name: str
learning_rate: float = 0.001
"""

nested_schema = """
wandb_run_name: str
model:
  hidden_dims: list[int]
training:
  batch_size: int = 32
  num_epochs: int = 10
"""

deeply_nested_schema = """
experiment:
  model:
    hidden_dims: list[int]
  optimizer:
    lr: float = 0.001
"""

enum_schema = """
types:
  OptimizerType:
    - sgd
    - adam
  LearningRateType:
    - 0.001
    - 0.01
schema:
  optimizer: OptimizerType
  learning_rate: LearningRateType
"""


@pytest.fixture()
def parser() -> SchemaParser:
    return SchemaParser()


def _generate(schema: str, tmp_path: Path, parser: SchemaParser) -> tuple[Path, str]:
    schema_file = tmp_path / "schema.yaml"
    schema_file.write_text(schema, encoding="utf-8")
    output_file = tmp_path / "generated.py"
    run_generation(schema_file, output_file, parser)
    return output_file, output_file.read_text(encoding="utf-8")


def test_flat_schema_generates_single_class(tmp_path: Path, parser: SchemaParser) -> None:
    _, code = _generate(flat_schema, tmp_path, parser)

    assert "class ConfigModel(BaseModel):" in code
    assert "wandb_run_name: str = Field(...)" in code
    assert "learning_rate: float = Field(0.001)" in code
    # Only one class definition
    assert code.count("class ") == 1


def test_nested_schema_generates_all_classes(tmp_path: Path, parser: SchemaParser) -> None:
    _, code = _generate(nested_schema, tmp_path, parser)

    assert "class ConfigModel(BaseModel):" in code
    assert "class Training(BaseModel):" in code
    assert "class Model(BaseModel):" in code


def test_nested_classes_defined_before_root(tmp_path: Path, parser: SchemaParser) -> None:
    _, code = _generate(nested_schema, tmp_path, parser)

    config_pos = code.index("class ConfigModel")
    training_pos = code.index("class Training")
    model_pos = code.index("class Model")

    assert training_pos < config_pos
    assert model_pos < config_pos


def test_generated_code_is_valid_python(tmp_path: Path, parser: SchemaParser) -> None:
    _, code = _generate(nested_schema, tmp_path, parser)
    # Will raise SyntaxError if invalid
    ast.parse(code)


def test_generated_code_is_importable_and_validates(tmp_path: Path, parser: SchemaParser) -> None:
    output_file, _ = _generate(nested_schema, tmp_path, parser)

    spec = importlib.util.spec_from_file_location("generated_config", output_file)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["generated_config"] = module
    spec.loader.exec_module(module)

    ConfigModel = getattr(module, "ConfigModel")
    data: dict[str, Any] = {
        "wandb_run_name": "test_run",
        "model": {"hidden_dims": [128, 64]},
        "training": {"batch_size": 64},
    }
    instance: Any = ConfigModel.model_validate(data)

    assert instance.wandb_run_name == "test_run"
    assert instance.model.hidden_dims == [128, 64]
    assert instance.training.batch_size == 64
    assert instance.training.num_epochs == 10


def test_deeply_nested_schema_generates_all_levels(tmp_path: Path, parser: SchemaParser) -> None:
    _, code = _generate(deeply_nested_schema, tmp_path, parser)

    assert "class ConfigModel(BaseModel):" in code
    assert "class Experiment(BaseModel):" in code
    assert "class Model(BaseModel):" in code
    assert "class Optimizer(BaseModel):" in code

    experiment_pos = code.index("class Experiment")
    model_pos = code.index("class Model")
    optimizer_pos = code.index("class Optimizer")
    config_pos = code.index("class ConfigModel")

    assert experiment_pos < config_pos
    assert model_pos < experiment_pos
    assert optimizer_pos < experiment_pos


def test_generated_code_supports_enum_types(tmp_path: Path, parser: SchemaParser) -> None:
    output_file, code = _generate(enum_schema, tmp_path, parser)

    assert "from enum import Enum" in code
    assert "class OptimizerType(Enum):" in code
    assert "class LearningRateType(Enum):" in code
    assert "optimizer: OptimizerType = Field(...)" in code
    assert "learning_rate: LearningRateType = Field(...)" in code

    spec = importlib.util.spec_from_file_location("generated_config_enums", output_file)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["generated_config_enums"] = module
    spec.loader.exec_module(module)

    ConfigModel = getattr(module, "ConfigModel")
    instance: Any = ConfigModel.model_validate({"optimizer": "adam", "learning_rate": 0.01})

    assert instance.optimizer.value == "adam"
    assert instance.learning_rate.value == 0.01


def test_generated_code_with_dynamic_types(tmp_path: Path, parser: SchemaParser) -> None:
    module_file = tmp_path / "my_model.py"
    module_file.write_text(
        "class MyModel:\n    def __init__(self):\n        pass\n",
        encoding="utf-8",
    )

    schema = f"model: {module_file}:MyModel\n"
    _, code = _generate(schema, tmp_path, parser)

    assert "from my_model import MyModel" in code
    assert "model: MyModel = Field(...)" in code


def test_generated_code_supports_inheritance(tmp_path: Path, parser: SchemaParser) -> None:
    schema = """
schema:
    A:
        x: str
    B < A:
        y: int
    """
    _, code = _generate(schema, tmp_path, parser)

    assert "class A(BaseModel):" in code
    assert "class B(A):" in code
    assert "x: str = Field(...)" in code
    assert "y: int = Field(...)" in code
