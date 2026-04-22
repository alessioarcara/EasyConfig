<p align="center">
  <img src="docs/logo.svg" alt="EzConfy logo" width="280" />
</p>

<p align="center">
  <strong>YAML-based configuration with Pydantic validation and dynamic object instantiation.</strong>
</p>

<p align="center">
  <a href="https://pypi.org/project/ezconfy/"><img src="https://img.shields.io/pypi/v/ezconfy?color=blue&label=PyPI" alt="PyPI version"></a>
  <a href="https://pypi.org/project/ezconfy/"><img src="https://img.shields.io/pypi/pyversions/ezconfy" alt="Python versions"></a>
  <a href="https://github.com/alessioarcara/EzConfy/blob/main/LICENSE"><img src="https://img.shields.io/github/license/alessioarcara/EzConfy" alt="License"></a>
</p>

---

## Why EzConfy?

ML projects constantly deal with configuration: learning rates, model parameters, dataset options, augmentation pipelines. EzConfy gives you **typed, validated configs with automatic object wiring** — without the complexity of a full framework like Hydra.

```python
from ezconfy import ConfigBuilder

cfg = ConfigBuilder.from_files(config_paths="config.yaml", schema_path="schema.yaml")
print(cfg.training.batch_size)  # validated, typed access
```

### What you get

| Feature | Description |
|---------|-------------|
| **Pydantic validation** | Type checking with clear error messages |
| **Schema-aware casting** | Strings become `Path` objects, etc. — before constructors run |
| **Dynamic instantiation** | Construct any Python class from YAML via `_target_type_` |
| **Placeholders** | `${key}`, attribute access, method calls, arithmetic |
| **Multi-file merge** | Split configs across files, override per experiment |
| **Code generation** | Generate Pydantic models for editor autocompletion |

## Installation

```bash
pip install ezconfy
```

Requires Python 3.11+.

## Quick Start

**config.yaml**
```yaml
lr: 0.001
batch_size: 32
data_path: ./data
```

**schema.yaml**
```yaml
lr: float
batch_size: int
data_path: pathlib:Path
```

**train.py**
```python
from ezconfy import ConfigBuilder

cfg = ConfigBuilder.from_files(
    config_paths="config.yaml",
    schema_path="schema.yaml",
)

print(cfg.lr)          # 0.001 (float)
print(cfg.batch_size)  # 32 (int)
print(cfg.data_path)   # PosixPath('data') — automatically cast
```

## Schema

A schema file describes the expected shape and types of your configuration:

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

If no `types` are needed, the entire YAML is treated as the root schema (no `schema:` wrapper required).

<details>
<summary><strong>Supported type syntax</strong></summary>

| Syntax | Meaning |
|--------|---------|
| `int`, `float`, `str`, `bool` | Primitive types |
| `type?` | Optional (defaults to `None`) |
| `type = value` | Type with default |
| `list[T]` | List of T |
| `A \| B` | Union type |
| `[a, b, c]` | Enum |
| `Child < Parent` | Model inheritance |
| `pathlib:Path` | External type (import path) |
| `/path/to/file.py:ClassName` | External type (file path) |

</details>

## Object Instantiation

Construct Python objects directly from config using `_target_type_`:

```yaml
dataset:
  _target_type_: mypackage.data:MyDataset
  _init_args_:
    num_classes: 100
    root: /data
```

Use `_init_method_` for alternative constructors (e.g. `from_pretrained`):

```yaml
encoder:
  _target_type_: mypackage.models:BertEncoder
  _init_method_: from_pretrained
  _init_args_:
    model_name: bert-base-uncased
```

## Placeholders & Expressions

Reference other config values with `${key}`. Supports attribute access, method calls, and arithmetic:

```yaml
lr: 0.001
warmup_lr: ${lr * 10}                       # arithmetic

num_classes: 10

dataset:
  _target_type_: mypackage.data:MyDataset
  _init_args_:
    num_classes: ${num_classes}               # scalar reference

model:
  _target_type_: mypackage.models:Classifier
  _init_args_:
    in_features: ${dataset.num_classes}       # attribute access
    params: ${encoder.parameters()}           # method call
```

Objects are instantiated in topological order based on their dependencies — forward references work automatically.

## Multi-file Configs & Overrides

Pass multiple files — they are deep-merged in order (later files win on conflicts):

```python
cfg = ConfigBuilder.from_files(
    config_paths=["base.yaml", "experiment.yaml"],
)
```

Apply programmatic overrides on top:

```python
cfg = ConfigBuilder.from_files(
    config_paths="config.yaml",
    overrides={"training": {"batch_size": 64}},
)
```

## Code Generation CLI

Generate a Pydantic model file from a schema for editor autocompletion and static analysis:

```bash
ezconfy generate schema.yaml -o models.py
```

## Documentation

Full documentation: [alessioarcara.github.io/EzConfy](https://alessioarcara.github.io/EzConfy/)

## License

[MIT](LICENSE)
