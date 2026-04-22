# Object Instantiation

## Why Use Object Instantiation?

In ML and deep learning projects, you constantly swap components: try a different backbone, switch the optimizer, change the learning rate scheduler, replace the data augmentation pipeline. Without a config-driven approach, you have two options — and neither scales:

**Option 1: Hardcode everything.** Every experiment requires a code change.

```python
optimizer = Adam(model.parameters(), lr=0.001)
scheduler = StepLR(optimizer, step_size=10)
```

Want to try SGD? Edit the code. Want CosineAnnealing? Edit the code again.

**Option 2: Add `if` statements.** The code grows into a component factory full of conditionals.

```python
if args.optimizer == "adam":
    optimizer = Adam(model.parameters(), lr=args.lr)
elif args.optimizer == "sgd":
    optimizer = SGD(model.parameters(), lr=args.lr, momentum=0.9)
elif args.optimizer == "adamw":
    optimizer = AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)

if args.scheduler == "step":
    scheduler = StepLR(optimizer, step_size=10)
elif args.scheduler == "cosine":
    scheduler = CosineAnnealingLR(optimizer, T_max=100)
```

Every new component you want to try requires a new `elif` branch — and this repeats for models, datasets, transforms, loss functions, and so on. The training script becomes a registry of every class you've ever used.

Both options make **ablation studies** painful and **experiment tracking** unreliable.

With EzConfy, swapping a component is a one-line YAML change:

=== "experiment_a.yaml"

    ```yaml
    optimizer:
      _target_type_: torch.optim:Adam
      _init_args_:
        params: ${model.parameters()}
        lr: 0.001
    ```

=== "experiment_b.yaml"

    ```yaml
    optimizer:
      _target_type_: torch.optim:SGD
      _init_args_:
        params: ${model.parameters()}
        lr: 0.01
        momentum: 0.9
    ```

Your training script stays **exactly the same** — it just reads `cfg.optimizer` and uses whatever was configured. This means you can:

- **Run ablation studies** by swapping config files, not code
- **Track experiments** by versioning YAML files (each file is a complete record of what was used)
- **Share configurations** with teammates without them needing to understand the codebase
- **Compose pipelines** — datasets, models, optimizers, schedulers, metrics — all wired together in YAML

The training code becomes a generic loop that works with any combination of components:

```python
cfg = ConfigBuilder.from_files(
    config_paths=["configs/base.yaml", f"configs/{experiment}.yaml"],
    schema_path="schema.yaml",
)

for epoch in range(cfg.epochs):
    train_one_epoch(cfg.model, cfg.train_loader, cfg.optimizer, cfg.criterion)
    evaluate(cfg.model, cfg.test_loader, cfg.metric)
    cfg.scheduler.step()
```

---

## Basic Usage

Use `_target_type_` to specify the class and `_init_args_` for constructor arguments:

```yaml
dataset:
  _target_type_: my_project.data:MyDataset
  _init_args_:
    root: ./data
    num_classes: 10
```

This is equivalent to `MyDataset(root='./data', num_classes=10)`.

!!! info "Import path format"
    The `_target_type_` value is an import path in the format `module.path:ClassName`. EzConfy dynamically imports the class and calls its constructor.

---

## Import Path Formats

EzConfy supports two ways to reference a class:

| Format | Example | When to use |
|--------|---------|-------------|
| Module path | `my_project.data:MyDataset` | Installed packages or importable modules |
| File path | `./models/nn.py:MLP` | Scripts or files not on `sys.path` |

Both absolute and relative file paths work.

---

## Alternative Constructors

Some classes use factory methods or classmethods instead of `__init__`. Use `_init_method_` to call an alternative constructor:

```yaml
encoder:
  _target_type_: transformers:AutoModel
  _init_method_: from_pretrained
  _init_args_:
    pretrained_model_name_or_path: bert-base-uncased
```

This calls `AutoModel.from_pretrained(pretrained_model_name_or_path='bert-base-uncased')`.

---

## Dependency Ordering

EzConfy resolves dependencies automatically using topological sorting. If one object references another via a placeholder, EzConfy instantiates them in the correct order:

```yaml
model:
  _target_type_: torch.nn:Linear
  _init_args_:
    in_features: 784
    out_features: 10

optimizer:
  _target_type_: torch.optim:Adam
  _init_args_:
    params: ${model.parameters()}   # model is instantiated first
    lr: 0.001
```

!!! tip
    You don't need to worry about ordering in your YAML — EzConfy figures it out from the `${}` references.

!!! warning "Circular dependencies"
    If there is a circular dependency (A depends on B, B depends on A), EzConfy raises an error with a clear message.

---

## Nested Instantiation

Objects can be nested inside lists or other objects:

```yaml
transform:
  _target_type_: torchvision.transforms:Compose
  _init_args_:
    transforms:
      - _target_type_: torchvision.transforms:ToTensor
      - _target_type_: torchvision.transforms:Normalize
        _init_args_:
          mean: [0.1307]
          std: [0.3081]
```

This creates a `Compose` containing a `ToTensor` and a `Normalize` — all wired up automatically.

---

## Complete Example: Ablation-Ready Training

Here is a realistic project layout where swapping any component is a YAML change:

```
project/
  configs/
    base.yaml             # shared defaults
    resnet18.yaml          # backbone = ResNet18
    resnet50.yaml          # backbone = ResNet50
    cosine_scheduler.yaml  # lr scheduler = CosineAnnealing
    step_scheduler.yaml    # lr scheduler = StepLR
  schema.yaml
  train.py
```

=== "configs/base.yaml"

    ```yaml
    num_classes: 10
    lr: 0.001
    epochs: 20

    dataset:
      _target_type_: torchvision.datasets:MNIST
      _init_args_:
        root: ./data
        train: true
        download: true

    optimizer:
      _target_type_: torch.optim:Adam
      _init_args_:
        params: ${model.parameters()}
        lr: ${lr}

    criterion:
      _target_type_: torch.nn:CrossEntropyLoss
    ```

=== "configs/resnet18.yaml"

    ```yaml
    model:
      _target_type_: torchvision.models:resnet18
      _init_args_:
        num_classes: ${num_classes}
    ```

=== "configs/resnet50.yaml"

    ```yaml
    model:
      _target_type_: torchvision.models:resnet50
      _init_args_:
        num_classes: ${num_classes}
    ```

=== "train.py"

    ```python
    import sys
    from ezconfy import ConfigBuilder

    backbone = sys.argv[1]  # "resnet18" or "resnet50"

    cfg = ConfigBuilder.from_files(
        config_paths=["configs/base.yaml", f"configs/{backbone}.yaml"],
        schema_path="schema.yaml",
    )

    for epoch in range(cfg.epochs):
        for data, target in DataLoader(cfg["dataset"]):
            output = cfg["model"](data)
            loss = cfg["criterion"](output, target)
            cfg["optimizer"].zero_grad()
            loss.backward()
            cfg["optimizer"].step()
    ```

Running ablations is now just:

```bash
python train.py resnet18
python train.py resnet50
```

No code changes. Each YAML file is a complete, reproducible record of the experiment configuration.
