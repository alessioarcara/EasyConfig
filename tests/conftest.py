from pathlib import Path

import pytest


@pytest.fixture()
def fake_dataset_file(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("file_target")
    file_path = root / "dataset.py"

    file_path.write_text(
        """
from abc import ABC, abstractmethod


class Dataset(ABC): ...

class FakeDataset(Dataset):
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
from abc import ABC
class Dataset(ABC): ...

class FakeDataset(Dataset):
    def __init__(self, num_classes: int) -> None:
        self.num_classes = num_classes
""".lstrip(),
        encoding="utf-8",
    )

    monkeypatch.syspath_prepend(str(root))
    return "fakepkg:FakeDataset"
