# Placeholders & Expressions

Placeholders let you reference one config value from another using `${key}` syntax. This avoids duplicating values and lets EzConfy wire objects together automatically.

---

## Basic References

Reference a top-level key:

```yaml
num_classes: 10

dataset:
  _target_type_: my_project.data:MyDataset
  _init_args_:
    num_classes: ${num_classes}   # resolves to 10
```

The placeholder `${num_classes}` is replaced with the value of the `num_classes` key.

---

## Attribute Access

Access attributes on instantiated objects with dot notation:

```yaml
dataset:
  _target_type_: my_project.data:MyDataset
  _init_args_:
    num_classes: 5

model:
  _target_type_: my_project.models:Classifier
  _init_args_:
    output_dim: ${dataset.num_classes}   # resolves to 5
```

!!! info
    This works because `dataset` is instantiated first (EzConfy resolves dependencies), then `dataset.num_classes` reads the attribute from the instantiated `MyDataset` object.

---

## Method Calls

Call methods on instantiated objects by appending `()`:

```yaml
model:
  _target_type_: torch.nn:Linear
  _init_args_:
    in_features: 784
    out_features: 10

optimizer:
  _target_type_: torch.optim:Adam
  _init_args_:
    params: ${model.parameters()}   # calls model.parameters()
    lr: 0.001
```

!!! warning "Limitation"
    Only no-argument methods are supported (e.g. `parameters()`, `state_dict()`).

---

## Nested Dictionary Access

When a config value is a plain dictionary (no `_target_type_`), access nested keys with dot notation:

```yaml
training:
  lr: 0.001
  batch_size: 32

warmup_lr: ${training.lr}   # resolves to 0.001
```

---

## Arithmetic Expressions

Placeholders support arithmetic with `+`, `-`, `*`, `/`, `//`, `%`, and `**`:

```yaml
lr: 0.001
warmup_lr: ${lr * 10}            # 0.01
weight_decay: ${lr / 10}         # 0.0001

a: 3
b: 7
total: ${a + b}                  # 10
half: ${a // 2}                  # 1
```

You can mix references and literals:

```yaml
dataset:
  _target_type_: my_project.data:MyDataset
  _init_args_:
    num_classes: 5

model:
  _target_type_: my_project.models:Classifier
  _init_args_:
    hidden_dim: ${dataset.num_classes * 4}   # 20
```

Unary operators also work:

```yaml
value: 5
negated: ${-value}   # -5
```

---

## How Dependency Resolution Works

EzConfy scans all `${}` references, builds a dependency graph, and processes keys in topological order:

1. Keys with no dependencies are resolved first
2. Keys that reference already-resolved values are resolved next
3. This continues until all keys are processed

```yaml
# Resolution order: a -> b -> c
a: 1
b: ${a}       # depends on a
c: ${a + b}   # depends on a and b
```

!!! warning "Circular dependencies"
    If you create a circular dependency, EzConfy raises an error:

    ```yaml
    # This will fail with "Circular reference detected"
    a: ${b}
    b: ${a}
    ```

---

## Rules and Limitations

!!! abstract "Quick reference"

    | Rule | Example |
    |------|---------|
    | Placeholders must be the **entire** value | `${key}` works, `prefix_${key}` does not |
    | Only **top-level** keys can be the root | `${dataset.attr}` references top-level `dataset`, then accesses `.attr` |
    | Method calls support **no arguments** | `${obj.method()}` is valid, `${obj.method(42)}` is not |
    | Arithmetic supports only **numeric** operands | String concatenation is not supported |
