from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from easyconfig.instantiator import Instantiator

# 1. Happy path: successful loading from all supported target types
#    (parametrize over absolute file path, relative file path, and module path)

# 2. What happens if the file path is malformed?
#    (parametrize over absolute and relative file path forms)

# 3. What happens if the file does not exist?
#    (parametrize over absolute and relative file path forms)

# 4. What happens if the requested class is not defined in the target?
#    (parametrize over absolute file path, relative file path, and module path)

# 5. What happens if the provided __init__ arguments do not match the class constructor signature?


def _make_config(target: str) -> str:
    return f"""
dataset:
  _target_type_: {target}
  _init_args_:
    num_classes: 100
"""


@pytest.fixture()
def fake_dataset_file(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("file_target")
    file_path = root / "dataset.py"

    file_path.write_text(
        """
class FakeDataset:
    def __init__(self, num_classes: int) -> None:
        self.num_classes = num_classes
""".lstrip(),
        encoding="utf-8",
    )

    return file_path


@pytest.fixture()
def fake_dataset_package(
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> str:
    root = tmp_path_factory.mktemp("package_target")
    package_dir = root / "fakepkg"
    package_dir.mkdir()

    (package_dir / "__init__.py").write_text(
        """
from .dataset import FakeDataset
""".lstrip(),
        encoding="utf-8",
    )

    (package_dir / "dataset.py").write_text(
        """
class FakeDataset:
    def __init__(self, num_classes: int) -> None:
        self.num_classes = num_classes
""".lstrip(),
        encoding="utf-8",
    )

    monkeypatch.syspath_prepend(str(root))
    return "fakepkg:FakeDataset"


@pytest.mark.parametrize("path_kind", ["absolute", "relative"])
def test_happy_path_file(
    path_kind: str,
    fake_dataset_file: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if path_kind == "absolute":
        target = f"{fake_dataset_file}:FakeDataset"
    else:
        monkeypatch.chdir(fake_dataset_file.parent)
        target = "dataset.py:FakeDataset"

    config = _make_config(target)

    instantiator = Instantiator()
    cfg = instantiator(config)

    dataset = cfg["dataset"]
    assert dataset.__class__.__name__ == "FakeDataset"
    assert dataset.num_classes == 100


def test_happy_path_module(fake_dataset_package: str) -> None:
    config = _make_config(fake_dataset_package)

    instantiator = Instantiator()
    cfg = instantiator(config)

    fakepkg = importlib.import_module("fakepkg")
    assert isinstance(cfg["dataset"], fakepkg.FakeDataset)
    assert cfg["dataset"].num_classes == 100
