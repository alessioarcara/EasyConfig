---
hide:
  - navigation
  - toc
---

<style>
.md-typeset h1 { display: none; }
</style>

<div class="hero" markdown>

<p align="center">
  <img src="logo.svg" alt="EzConfy logo" width="280" />
</p>

<p align="center" class="hero-tagline" style="font-size: 1.3em; opacity: 0.8; margin-top: -0.5em;">
  <strong>YAML-based configuration with Pydantic validation and dynamic object instantiation.</strong>
</p>

<p align="center">
  <a href="https://pypi.org/project/ezconfy/"><img src="https://img.shields.io/pypi/v/ezconfy?color=blue&label=PyPI" alt="PyPI version"></a>
  <a href="https://pypi.org/project/ezconfy/"><img src="https://img.shields.io/pypi/pyversions/ezconfy" alt="Python versions"></a>
  <a href="https://github.com/alessioarcara/EzConfy/blob/main/LICENSE"><img src="https://img.shields.io/github/license/alessioarcara/EzConfy" alt="License"></a>
</p>

</div>

---

## The Problem

If you have ever written a Python project — especially in machine learning — you have probably dealt with configuration: learning rates, file paths, model parameters, dataset options. At first you hard-code them, then you move them to a dictionary, then maybe a YAML file. But soon you run into problems:

<div class="grid cards" markdown>

-   :material-alert-circle-outline:{ .lg .middle } **No validation**

    ---

    Misspell a key (`lerning_rate` instead of `learning_rate`) and nothing complains — the value is silently ignored. Pass a string where an integer is expected and you get a crash deep in your training loop.

-   :material-code-tags:{ .lg .middle } **No typing**

    ---

    Every value is a raw string or number. If your code expects a `Path` object, you have to remember to convert it yourself.

-   :material-link-variant-off:{ .lg .middle } **No wiring**

    ---

    You load config values but still have to manually write `MyDataset(num_classes=config["num_classes"])` everywhere.

-   :material-code-braces:{ .lg .middle } **Too much boilerplate**

    ---

    As configs grow, the glue code between "reading a YAML file" and "having usable objects" keeps expanding.

</div>

**EzConfy eliminates all of this.** Write a YAML config, optionally define a schema, and get back fully instantiated, validated Python objects — ready to use.

---

## Key Features

<div class="grid cards" markdown>

-   :material-file-document-outline:{ .lg .middle } **YAML config files**

    ---

    Human-readable, easy to diff and version-control.

-   :material-shield-check-outline:{ .lg .middle } **Pydantic validation**

    ---

    Define a schema and get automatic type checking with clear error messages.

-   :material-swap-horizontal:{ .lg .middle } **Schema-aware type casting**

    ---

    Values are cast to schema types *before* constructors run — strings become `Path` objects automatically.

-   :material-cog-outline:{ .lg .middle } **Dynamic object instantiation**

    ---

    Construct any Python class from config using `_target_type_`.

-   :material-variable:{ .lg .middle } **Placeholders & expressions**

    ---

    Reference other values with `${key}`, including attribute access, method calls, and arithmetic.

-   :material-file-multiple-outline:{ .lg .middle } **Multi-file deep merge**

    ---

    Split configs across files, override per experiment — later files win.

-   :material-console:{ .lg .middle } **Code generation CLI**

    ---

    Generate Pydantic model files from your schema for editor autocompletion.

</div>

---

## Installation

```bash
pip install ezconfy
```

!!! info "Requirements"
    Python 3.11 or later.

---

## Quick Example

=== "config.yaml"

    ```yaml
    lr: 0.001
    batch_size: 32
    data_path: ./data
    ```

=== "schema.yaml"

    ```yaml
    lr: float
    batch_size: int
    data_path: pathlib:Path
    ```

=== "train.py"

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

Three files, three lines of Python, and you get validated, typed configuration.

---

## What's Next?

<div class="grid cards" markdown>

-   :material-rocket-launch-outline:{ .lg .middle } **[Getting Started](getting-started.md)**

    ---

    A step-by-step tutorial from zero to a working config.

-   :material-shield-check-outline:{ .lg .middle } **[Schema & Validation](schema.md)**

    ---

    The full type syntax reference.

-   :material-cog-outline:{ .lg .middle } **[Object Instantiation](instantiation.md)**

    ---

    Construct Python objects directly from YAML.

-   :material-variable:{ .lg .middle } **[Placeholders & Expressions](placeholders.md)**

    ---

    Reference and compute across config values.

-   :material-file-multiple-outline:{ .lg .middle } **[Multi-file Configs](multi-file.md)**

    ---

    Split, merge, and override configurations.

-   :material-console:{ .lg .middle } **[Code Generation](codegen.md)**

    ---

    Generate Pydantic models from your schema.

</div>
