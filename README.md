<p align="center">
  <img src="docs/logo.svg" alt="ezconfy logo" width="280" />
</p>

EasyConfig is designed for ML/data science projects that want **typed, validated configs with automatic object wiring** - without the complexity of a full framework like Hydra.

## Installation

```bash
pip install ezconfy
```

## Quick Start

Define a schema and a config file, then load them:

```python
from ezconfy import ConfigBuilder

cfg = ConfigBuilder.from_files(config_paths="config.yaml", schema_path="schema.yaml")
print(cfg.training.batch_size)  # validated, typed access
```

## Schema

A schema file describes the expected shape and types of your configuration. It can define custom types and the root structure:

```yaml
types:
  OptimizerType:
    - adam
    - sgd
    - rmsprop

schema:
  model:
    hidden_dims: list[int]
  training:
    batch_size: int = 32
    num_epochs: int = 10
    shuffle: bool = true
    dropout: float?
    optimizer: OptimizerType
```

### Supported type syntax

| Syntax | Meaning |
|---|---|
| `int`, `float`, `str`, `bool` | Primitive types |
| `type?` | Optional (defaults to `None`) |
| `type = value` | Type with default |
| `list[T]` | List of T |
| `A \| B` | Union type |
| `[a, b, c]` | Enum |
| `Child < Parent` | Model inheritance |
| `pathlib:Path` | External type (import path) |
| `/path/to/file.py:ClassName` | External type (file path) |

If no `types` are needed, the entire YAML is treated as the root schema (no `schema:` wrapper required).

## Object Instantiation

ezconfy can instantiate Python objects directly from config using `_target_type_`:

```yaml
dataset:
  _target_type_: mypackage.data:MyDataset
  _init_args_:
    num_classes: 100
    root: /data
```

Use `_init_method_` to call an alternative constructor (e.g. `from_pretrained`):

```yaml
encoder:
  _target_type_: mypackage.models:BertEncoder
  _init_method_: from_pretrained
  _init_args_:
    model_name: bert-base-uncased
```

## Placeholder Injection

Reference other config values with `${key}`. Supports attribute access and method calls:

```yaml
num_classes: 10

dataset:
  _target_type_: mypackage.data:MyDataset
  _init_args_:
    num_classes: ${num_classes}   # scalar reference

model:
  _target_type_: mypackage.models:Classifier
  _init_args_:
    in_features: ${dataset.num_classes}   # attribute access
    params: ${encoder.parameters()}       # method call
```

Objects are instantiated in topological order based on their dependencies, so forward references work automatically.

## Multi-file Configs & Overrides

Pass multiple files — they are deep-merged in order (later files win on conflicts):

```python
cfg = ConfigBuilder.from_files(config_paths=["base.yaml", "experiment.yaml"])
```

Apply programmatic overrides on top:

```python
cfg = ConfigBuilder.from_files(
    config_paths="config.yaml",
    overrides={"training": {"batch_size": 64}},
)
```

## Code Generation CLI

Generate a Pydantic model file from a schema:

```bash
ezconfy generate schema.yaml output.py
```

This produces a standalone `.py` file with `BaseModel` classes matching the schema, useful for editor autocompletion and static analysis.

## Requirements

- Python 3.11+
