from pathlib import Path
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


@pytest.fixture()
def parser() -> SchemaParser:
    return SchemaParser()


def test_should_generate_pydantic_model_from_yaml_string(parser: SchemaParser) -> None:
    model = parser.parse(config)
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


def test_should_raise_schema_error_for_unsupported_type(parser: SchemaParser) -> None:
    invalid_config = """
    training:
        early_stopping:
            patience: unknown_type
    """

    with pytest.raises(SchemaError) as exc_info:
        parser.parse(invalid_config)

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
def test_should_raise_validation_error(
    input_data: dict[str, Any], parser: SchemaParser
) -> None:
    model = parser.parse(config)

    with pytest.raises(ValidationError):
        model.model_validate(input_data)


def test_should_handle_union_types(parser: SchemaParser) -> None:
    union_config = """
    dropout: float?
    """

    model = parser.parse(union_config)

    instance1: Any = model.model_validate({"dropout": 0.2})
    assert instance1.dropout == 0.2

    instance2: Any = model.model_validate({})
    assert instance2.dropout is None

    with pytest.raises(ValidationError):
        model.model_validate({"dropout": "invalid"})


def test_should_handle_alias_types(parser: SchemaParser) -> None:
    alias_config = """
    types:
        ClassifierHead:
            num_classes: int
            hidden_dims: list[int]
    schema:
        model:
            head1: ClassifierHead
            head2: ClassifierHead
    """

    model = parser.parse(alias_config)

    instance: Any = model.model_validate(
        {
            "model": {
                "head1": {"num_classes": 10, "hidden_dims": [64, 32]},
                "head2": {"num_classes": 5, "hidden_dims": [128]},
            }
        }
    )
    assert instance.model.head1.num_classes == 10
    assert instance.model.head1.hidden_dims == [64, 32]
    assert instance.model.head2.num_classes == 5
    assert instance.model.head2.hidden_dims == [128]


def test_should_handle_types_defined_in_any_order(parser: SchemaParser) -> None:
    alias_config = """
    types:
        A: B
        B: int
    schema:
        num_classes: A
    """

    model = parser.parse(alias_config)

    instance: Any = model.model_validate({"num_classes": 10})
    assert instance.num_classes == 10


def test_should_handle_enum_types(parser: SchemaParser) -> None:
    enum_config = """
    types:
        OptimizerType: 
            - sgd
            - adam
            - rmsprop
        LearningRateType:
            - 0.001
            - 0.01
            - 0.1
    schema:
        optimizer: OptimizerType
        learning_rate: LearningRateType
    """

    model = SchemaParser().parse(enum_config)

    instance: Any = model.model_validate({"optimizer": "adam", "learning_rate": 0.01})
    assert instance.optimizer.value == "adam"
    assert instance.learning_rate.value == 0.01

    with pytest.raises(ValidationError):
        model.model_validate({"optimizer": "invalid_optimizer", "learning_rate": 0.01})

    with pytest.raises(ValidationError):
        model.model_validate({"optimizer": "sgd", "learning_rate": 0.05})


def test_should_handle_inherited_models(parser: SchemaParser) -> None:
    inherited_config = """
    types:
        AggregationType: 
            - mean
            - sum
            - max
        Backbone:
            n_layers: int
        GraphSage < Backbone:
            aggr_type: AggregationType
    schema:
        backbone: GraphSage
    """

    model = parser.parse(inherited_config)

    instance: Any = model.model_validate(
        {"backbone": {"n_layers": 3, "aggr_type": "mean"}}
    )
    assert instance.backbone.n_layers == 3
    assert instance.backbone.aggr_type.value == "mean"


def test_should_handle_inheritance_with_forward_refs(parser: SchemaParser) -> None:
    config = """
    types:
        A < B:
            a: int
        B < C:
            b: int
        C:
            c: int
    schema:
        model: A
    """

    model = parser.parse(config)

    instance: Any = model.model_validate(
        {
            "model": {
                "a": 1,
                "b": 2,
                "c": 3,
            }
        }
    )

    assert instance.model.a == 1
    assert instance.model.b == 2
    assert instance.model.c == 3


def test_should_raise_error_on_circular_inheritance_dependency(
    parser: SchemaParser,
) -> None:
    config = """
    types:
        A < B:
            a: int
        B < A:
            b: int
    schema:
        model: A
    """

    with pytest.raises(SchemaError) as exc_info:
        parser.parse(config)

    assert "Circular dependency" in str(exc_info.value)


def test_should_raise_error_on_circular_alias_dependency(parser: SchemaParser) -> None:
    config = """
    types:
        A: B
        B: A
    schema:
        value: A
    """

    with pytest.raises(SchemaError) as exc_info:
        parser.parse(config)

    assert "Circular" in str(exc_info.value) or "unresolved" in str(exc_info.value)


def test_should_handle_external_types(parser: SchemaParser) -> None:
    config = """
    types:
        Path: pathlib:Path
    schema:
        path: Path
    """
    model = parser.parse(config)

    instance: Any = model.model_validate({"path": "/some/path"})
    assert instance.path == Path("/some/path")
