# Getting Started

This tutorial walks you through EzConfy from scratch. By the end you will have a validated, typed configuration that automatically constructs Python objects — all from a simple YAML file.

---

## 1. Install EzConfy

```bash
pip install ezconfy
```

---

## 2. Create a config file

A config file is just a YAML file. Create `config.yaml`:

```yaml
project_name: my-experiment
lr: 0.001
epochs: 10
data_path: ./data
```

---

## 3. Load it in Python

```python
from ezconfy import ConfigBuilder

cfg = ConfigBuilder.from_files(config_paths="config.yaml")
```

Without a schema, `cfg` is a plain dictionary:

```python
print(cfg["lr"])          # 0.001
print(cfg["data_path"])   # './data' (a string — not a Path object)
```

!!! note "Why a dictionary?"
    Without a schema, EzConfy has no type information. The result is a raw dictionary with YAML-parsed values. Adding a schema upgrades this to a validated Pydantic model.

---

## 4. Add a schema

A schema tells EzConfy what types your config values should have. Create `schema.yaml`:

```yaml
project_name: str
lr: float
epochs: int
data_path: pathlib:Path
```

Now load with the schema:

```python
cfg = ConfigBuilder.from_files(
    config_paths="config.yaml",
    schema_path="schema.yaml",
)

print(cfg.lr)          # 0.001 (float — validated)
print(cfg.data_path)   # PosixPath('./data') — automatically cast
print(cfg.epochs)      # 10 (int — validated)
```

!!! tip "What changed?"
    1. **Dot access** — `cfg.lr` instead of `cfg["lr"]`. With a schema, the result is a Pydantic model.
    2. **Automatic casting** — `data_path` is now a real `Path` object, not a string.

    If you make a typo in the config (e.g. `epochs: "ten"`), EzConfy raises a clear validation error immediately.

---

## 5. Instantiate objects

Here is where EzConfy gets really useful. Instead of writing boilerplate to construct objects from config values, let EzConfy do it for you.

Say you have a `Dataset` class:

```python
# my_project/data.py
class Dataset:
    def __init__(self, root: str, num_classes: int):
        self.root = root
        self.num_classes = num_classes
```

In your config, use `_target_type_` to tell EzConfy which class to instantiate and `_init_args_` for the constructor arguments:

=== "config.yaml"

    ```yaml
    num_classes: 10

    dataset:
      _target_type_: my_project.data:Dataset
      _init_args_:
        root: ./data
        num_classes: ${num_classes}
    ```

=== "Python"

    ```python
    cfg = ConfigBuilder.from_files(config_paths="config.yaml")

    print(cfg["dataset"])              # <my_project.data.Dataset object>
    print(cfg["dataset"].root)         # './data'
    print(cfg["dataset"].num_classes)  # 10
    ```

!!! info "Placeholder resolution"
    The `${num_classes}` placeholder pulls the value from the top-level `num_classes` key. EzConfy resolves dependencies automatically — objects that depend on other objects are instantiated in the correct order.

---

## 6. Combine schema + instantiation

For full validation with object instantiation:

=== "schema.yaml"

    ```yaml
    types:
      Dataset: my_project.data:Dataset

    schema:
      num_classes: int
      dataset: Dataset
    ```

=== "Python"

    ```python
    cfg = ConfigBuilder.from_files(
        config_paths="config.yaml",
        schema_path="schema.yaml",
    )

    print(cfg.dataset)              # <Dataset object> — validated
    print(cfg.dataset.num_classes)  # 10 — typed correctly
    ```

---

## 7. Override per experiment

You can split your config into a base file and experiment-specific overrides:

```python
cfg = ConfigBuilder.from_files(
    config_paths=["base.yaml", "experiment_large.yaml"],
)
```

Later files win on conflicts. You can also pass overrides programmatically:

```python
cfg = ConfigBuilder.from_files(
    config_paths="config.yaml",
    overrides={"lr": 0.01, "epochs": 50},
)
```

---

## Summary

| Step | What you get |
|------|-------------|
| Config YAML only | Plain dictionary with raw values |
| + Schema | Pydantic model with validation, typing, and automatic casting |
| + `_target_type_` | Fully constructed Python objects from config |
| + Placeholders | Cross-references between config values |
| + Multi-file | Experiment overrides without duplicating config |

---

## Next Steps

- **[Schema & Validation](schema.md)** — full type syntax reference
- **[Object Instantiation](instantiation.md)** — `_target_type_`, `_init_method_`, and dependency ordering
- **[Placeholders & Expressions](placeholders.md)** — `${key}`, attribute access, method calls, arithmetic
