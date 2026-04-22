# Schema & Validation

A schema file describes the expected shape and types of your configuration. When you provide a schema, EzConfy:

1. **Validates** every config value against the declared type
2. **Returns** a Pydantic `BaseModel` instance with dot access

---

## YAML Structure

A schema can have two top-level keys:

```yaml
types:
  # custom type definitions (optional)

schema:
  # the root configuration structure
```

!!! tip "Shorthand syntax"
    If you don't need custom types, the entire file is treated as the root schema — no `types`/`schema` wrapper needed:

    ```yaml
    lr: float
    epochs: int
    name: str
    ```

    If you define `types`, you must also define `schema`.

---

## Primitive Types

```yaml
lr: float
epochs: int
name: str
verbose: bool
```

These map directly to Python's `float`, `int`, `str`, and `bool`.

---

## Optional Types

Append `?` to make a field optional. It defaults to `None` if not present in the config:

```yaml
dropout: float?
description: str?
```

---

## Default Values

Use `= value` to set a default:

```yaml
batch_size: int = 32
device: str = "cpu"
shuffle: bool = true
```

If the config file omits these fields, the defaults are used.

---

## Lists

```yaml
hidden_dims: list[int]
tags: list[str]
```

!!! warning
    The element type is validated too — `hidden_dims: [256, "oops"]` would fail validation.

---

## Union Types

Use `|` to accept multiple types:

```yaml
value: int | float
id: str | int
```

---

## Nested Objects

Indent to create a nested structure:

```yaml
training:
  lr: float
  epochs: int
  batch_size: int = 32

data:
  root: str
  num_workers: int = 4
```

This creates nested Pydantic models. Access them with `cfg.training.lr`.

---

## Custom Types

Define reusable types in the `types` section.

### Enums

A list of values creates an enum:

```yaml
types:
  OptimizerType:
    - adam
    - sgd
    - rmsprop

schema:
  optimizer: OptimizerType
```

### Nested model types

A dictionary creates a reusable model:

```yaml
types:
  DataConfig:
    root: str
    num_workers: int = 4

schema:
  train_data: DataConfig
  test_data: DataConfig
```

### Inheritance

Use `<` to inherit from another type:

```yaml
types:
  BaseModel:
    name: str
    hidden_dim: int

  LargeModel < BaseModel:
    num_layers: int
    dropout: float

schema:
  model: LargeModel
```

`LargeModel` inherits all fields from `BaseModel` and adds its own.

---

## External Types

Import any Python class using `module:ClassName` syntax:

=== "From a package"

    ```yaml
    types:
      Path: pathlib:Path
      TorchModule: torch.nn:Module

    schema:
      data_root: Path
      model: TorchModule
    ```

=== "From a file path"

    ```yaml
    model: /path/to/my_models.py:MyModel
    ```

!!! info
    External types are validated with `isinstance` — EzConfy checks that the instantiated object is actually an instance of the declared type.

---

## Complete Example

=== "schema.yaml"

    ```yaml
    types:
      OptimizerType:
        - adam
        - sgd

      TrainingConfig:
        lr: float = 0.001
        epochs: int = 10
        optimizer: OptimizerType

      DataConfig:
        root: str
        num_classes: int

    schema:
      training: TrainingConfig
      data: DataConfig
      name: str
      debug: bool?
    ```

=== "config.yaml"

    ```yaml
    name: cifar-experiment
    training:
      lr: 0.01
      epochs: 50
      optimizer: adam
    data:
      root: ./data/cifar10
      num_classes: 10
    ```

=== "Python"

    ```python
    cfg = ConfigBuilder.from_files(
        config_paths="config.yaml",
        schema_path="schema.yaml",
    )

    print(cfg.name)                  # 'cifar-experiment'
    print(cfg.training.lr)           # 0.01
    print(cfg.training.optimizer)    # <OptimizerType.V0: 'adam'>
    print(cfg.data.num_classes)      # 10
    print(cfg.debug)                 # None (optional, not provided)
    ```
