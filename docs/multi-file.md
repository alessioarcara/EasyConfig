# Multi-file Configs & Overrides

Real projects don't have a single, fixed configuration. You run different experiments, try different augmentation pipelines, swap schedulers, test on different datasets. Copying entire config files for each variation leads to duplication and drift.

EzConfy solves this with multi-file merging and programmatic overrides.

---

## The Idea: One Base, Many Variations

The core pattern is simple:

1. **A base config** defines everything that stays the same across experiments
2. **Small override files** each change only the part that varies
3. You **compose** them at load time — later files override earlier ones

Your training script never changes. You just pick which YAML files to combine.

---

## Multiple Config Files

Pass a list of files to `config_paths`. They are deep-merged in order — later files win on conflicts:

```python
cfg = ConfigBuilder.from_files(
    config_paths=["configs/base.yaml", "configs/heavy_augment.yaml"],
)
```

=== "configs/base.yaml"

    ```yaml
    epochs: 50
    lr: 0.001
    batch_size: 32

    model:
      _target_type_: torchvision.models:resnet18
      _init_args_:
        num_classes: 10

    augmentation:
      _target_type_: torchvision.transforms:Compose
      _init_args_:
        transforms:
          - _target_type_: torchvision.transforms:ToTensor

    optimizer:
      _target_type_: torch.optim:Adam
      _init_args_:
        params: ${model.parameters()}
        lr: ${lr}

    scheduler:
      _target_type_: torch.optim.lr_scheduler:StepLR
      _init_args_:
        optimizer: ${optimizer}
        step_size: 10
    ```

=== "configs/heavy_augment.yaml"

    ```yaml
    augmentation:
      _target_type_: torchvision.transforms:Compose
      _init_args_:
        transforms:
          - _target_type_: torchvision.transforms:RandomHorizontalFlip
          - _target_type_: torchvision.transforms:RandomCrop
            _init_args_:
              size: 32
              padding: 4
          - _target_type_: torchvision.transforms:ToTensor
          - _target_type_: torchvision.transforms:Normalize
            _init_args_:
              mean: [0.4914, 0.4822, 0.4465]
              std: [0.2470, 0.2435, 0.2616]
    ```

!!! tip "Result"
    The model, optimizer, scheduler, and training params come from `base.yaml`. Only `augmentation` is replaced by `heavy_augment.yaml`. Everything else is untouched.

---

## Deep Merge Behavior

Nested dictionaries are merged recursively, not replaced entirely:

=== "base.yaml"

    ```yaml
    training:
      lr: 0.001
      epochs: 10
      batch_size: 32
    ```

=== "override.yaml"

    ```yaml
    training:
      lr: 0.01
    ```

=== "Result"

    ```yaml
    training:
      lr: 0.01        # overridden
      epochs: 10      # preserved from base
      batch_size: 32  # preserved from base
    ```

!!! note
    Non-dict values (scalars, lists) are fully replaced by the later file — unless the later list uses the `...` patch marker described below.

---

## Patching Lists

Replacing a whole list just to tweak one element forces you to restate every other element. Instead, add `...` to the override list to switch it to **patch mode**: `...` expands to the base elements, and the other entries patch, add, or delete individual elements.

=== "base.yaml"

    ```yaml
    callbacks:
      - _id_: early
        _target_type_: my_pkg.callbacks:EarlyStopping
        _init_args_:
          patience: 5
      - _id_: ckpt
        _target_type_: my_pkg.callbacks:Checkpoint
        _init_args_:
          save_top_k: 3
    ```

=== "override.yaml"

    ```yaml
    callbacks:
      - ...
      - _id_: early
        _init_args_:
          patience: 20
    ```

=== "Result"

    ```yaml
    callbacks:
      - _target_type_: my_pkg.callbacks:EarlyStopping
        _init_args_:
          patience: 20      # patched
      - _target_type_: my_pkg.callbacks:Checkpoint
        _init_args_:
          save_top_k: 3     # untouched
    ```

### Matching Rules

A patch entry is matched against base elements:

1. **By `_id_`** — if the entry has an `_id_`, it matches the base element with the same `_id_`. Ids exist only for matching and are stripped from the final config.
2. **By `_target_type_`** — otherwise, it matches the first not-yet-matched base element with the same target. Two patch entries with the same target patch the first and second occurrence, in order.

Matched elements are deep-merged **in place** — they keep their position in the base list, so execution order is preserved. Entries that match nothing are inserted as new elements: before `...` to prepend, after `...` to append.

```yaml
callbacks:
  - _target_type_: my_pkg.callbacks:ProfilerStart   # new, prepended
  - ...
  - _target_type_: my_pkg.callbacks:ProfilerStop    # new, appended
```

### Deleting Elements

Mark an entry with `_delete_: true` to remove the matched element (same matching rules):

```yaml
callbacks:
  - ...
  - _id_: early
    _delete_: true
```

A `_delete_` entry that matches nothing raises a `MergeError` — typos fail loudly instead of silently keeping the element.

!!! note
    Patch mode works identically in override files and in the programmatic `overrides` dictionary (use the string `"..."` there). A list may contain at most one `...` marker.

---

## Composing Multiple Override Files

You are not limited to two files. Combine a base with several focused override files, each responsible for one concern:

```python
cfg = ConfigBuilder.from_files(
    config_paths=[
        "configs/base.yaml",            # full baseline
        "configs/resnet50.yaml",         # swap backbone
        "configs/cosine_scheduler.yaml", # swap scheduler
        "configs/heavy_augment.yaml",    # swap augmentation
    ],
)
```

Each override file is small and single-purpose:

=== "configs/resnet50.yaml"

    ```yaml
    model:
      _target_type_: torchvision.models:resnet50
      _init_args_:
        num_classes: ${num_classes}
    ```

=== "configs/cosine_scheduler.yaml"

    ```yaml
    scheduler:
      _target_type_: torch.optim.lr_scheduler:CosineAnnealingLR
      _init_args_:
        optimizer: ${optimizer}
        T_max: ${epochs}
    ```

Mix and match components freely. Want ResNet50 with heavy augmentation and cosine scheduler? Combine those three files. Want ResNet18 with light augmentation and step scheduler? Use just the base. No duplication, no drift.

---

## Programmatic Overrides

For quick tweaks — hyperparameter sweeps, CLI arguments, test-specific values — pass an `overrides` dictionary. It is applied after all files are merged, so it always wins:

```python
cfg = ConfigBuilder.from_files(
    config_paths=["configs/base.yaml", "configs/resnet50.yaml"],
    overrides={"lr": 0.01, "batch_size": 128},
)
```

!!! example "Hyperparameter sweep"

    ```python
    for lr in [0.1, 0.01, 0.001, 0.0001]:
        cfg = ConfigBuilder.from_files(
            config_paths=["configs/base.yaml"],
            overrides={"lr": lr},
        )
        train(cfg)
    ```

---

## Typical Project Layout

```
project/
  configs/
    base.yaml                # complete baseline experiment
    backbones/
      resnet18.yaml          # swap backbone to ResNet18
      resnet50.yaml          # swap backbone to ResNet50
    augmentations/
      light.yaml             # minimal augmentation
      heavy.yaml             # aggressive augmentation
    schedulers/
      step.yaml              # StepLR scheduler
      cosine.yaml            # CosineAnnealing scheduler
  schema.yaml                # validation schema
  train.py
```

```python
# train.py
import sys
from ezconfy import ConfigBuilder

# Example: python train.py resnet50 heavy cosine
backbone, augment, scheduler = sys.argv[1], sys.argv[2], sys.argv[3]

cfg = ConfigBuilder.from_files(
    config_paths=[
        "configs/base.yaml",
        f"configs/backbones/{backbone}.yaml",
        f"configs/augmentations/{augment}.yaml",
        f"configs/schedulers/{scheduler}.yaml",
    ],
    schema_path="schema.yaml",
)
```

Each experiment is fully described by its combination of YAML files — easy to reproduce, easy to compare, easy to version-control.
