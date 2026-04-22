# Code Generation CLI

EzConfy can generate standalone Python files with Pydantic model definitions from your schema. This gives you editor autocompletion, type checking, and documentation for your config structure — without writing the models by hand.

---

## Usage

```bash
ezconfy generate schema.yaml -o models.py
```

This reads `schema.yaml` and writes a Python file with `BaseModel` classes matching the schema.

---

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `schema_path` | *(required)* | Path to the YAML schema file |
| `-o`, `--output` | `generated.py` | Output file path |

---

## Example

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

    schema:
      training: TrainingConfig
      name: str
      debug: bool?
    ```

=== "Generated output"

    ```python
    from enum import Enum

    from pydantic import BaseModel, ConfigDict


    class OptimizerType(Enum):
        V0 = "adam"
        V1 = "sgd"


    class TrainingConfig(BaseModel):
        model_config = ConfigDict(arbitrary_types_allowed=True)

        lr: float = 0.001
        epochs: int = 10
        optimizer: OptimizerType


    class ConfigModel(BaseModel):
        model_config = ConfigDict(arbitrary_types_allowed=True)

        training: TrainingConfig
        name: str
        debug: bool | None = None
    ```

---

## Why Generate Code?

<div class="grid cards" markdown>

-   :material-auto-fix:{ .lg .middle } **Editor autocompletion**

    ---

    Your IDE knows every config field and its type.

-   :material-check-decagram:{ .lg .middle } **Static analysis**

    ---

    `mypy` and other type checkers can verify your config usage.

-   :material-book-open-variant:{ .lg .middle } **Documentation**

    ---

    The generated file acts as a readable reference for your config structure.

-   :material-shield-refresh-outline:{ .lg .middle } **Refactoring safety**

    ---

    Renaming a field in the schema and regenerating catches all usages.

</div>

---

## Workflow

A typical workflow:

1. Define or update `schema.yaml`
2. Run `ezconfy generate schema.yaml -o config_models.py`
3. Import the generated models for type hints:

```python
from config_models import ConfigModel
from ezconfy import ConfigBuilder

cfg: ConfigModel = ConfigBuilder.from_files(  # type: ignore[assignment]
    config_paths="config.yaml",
    schema_path="schema.yaml",
)

# Now your editor knows about cfg.training.lr, cfg.name, etc.
```

!!! tip
    Regenerate whenever the schema changes to keep your type hints in sync.
