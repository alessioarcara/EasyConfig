from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from easyconfig.parser import SchemaError, SchemaParser

config = """
wandb_run_name: str
model:
  hidden_dims: list[int]
training:
  batch_size: int = 32
  num_epochs: int = 10
  shuffle: bool = true
"""


def test_should_generate_pydantic_model_from_yaml_string() -> None:
    model = SchemaParser.parse(config)
    input_data = {
        "training": {"batch_size": 64},
        "model": {"hidden_dims": [128, 64]},
        "wandb_run_name": "test_run",
    }

    instance: Any = model.model_validate(input_data)

    assert issubclass(model, BaseModel)
    assert instance.training.batch_size == 64
    assert instance.training.num_epochs == 10
    assert instance.model.hidden_dims == [128, 64]
    assert instance.wandb_run_name == "test_run"
    assert instance.training.shuffle is True


def test_should_raise_schema_error_for_unsupported_type() -> None:
    invalid_config = """
    training:
        early_stopping:
            patience: unknown_type
    """

    with pytest.raises(SchemaError) as exc_info:
        SchemaParser.parse(invalid_config)

    assert "training.early_stopping.patience" in str(exc_info.value)


@pytest.mark.parametrize(
    "input_data",
    [
        pytest.param(
            {
                "training": {"batch_size": 64},
                "model": {"hidden_dims": [128, 64]},
            },
            id="missing_required_field",
        ),
        pytest.param(
            {
                "training": {"batch_size": "not_a_number"},
                "model": {"hidden_dims": [128, 64]},
                "wandb_run_name": "test_run",
            },
            id="invalid_batch_size_type",
        ),
    ],
)
def test_should_raise_validation_error(input_data: dict[str, Any]) -> None:
    model = SchemaParser.parse(config)

    with pytest.raises(ValidationError):
        model.model_validate(input_data)


def test_should_handle_union_types() -> None:
    union_config = """
    dropout: float | null
    """

    model = SchemaParser.parse(union_config)

    instance1: Any = model.model_validate({"dropout": 0.2})
    assert instance1.dropout == 0.2

    instance2: Any = model.model_validate({})
    assert instance2.dropout is None

    with pytest.raises(ValidationError):
        model.model_validate({"dropout": "invalid"})
