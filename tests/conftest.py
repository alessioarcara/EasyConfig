import sys
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


@pytest.fixture
def fake_dataset_package(tmp_path_factory: pytest.TempPathFactory) -> str:
    pkg_root = tmp_path_factory.mktemp("fakepkg")
    pkg_dir = pkg_root / "fakepkg"
    pkg_dir.mkdir()

    (pkg_dir / "__init__.py").write_text("", encoding="utf-8")

    (pkg_dir / "dataset.py").write_text(
        """
from abc import ABC

class Dataset(ABC): ...

class FakeDataset(Dataset):
    def __init__(self, num_classes: int) -> None:
        self.num_classes = num_classes
""".lstrip(),
        encoding="utf-8",
    )

    sys.path.insert(0, str(pkg_root))

    return "fakepkg.dataset"
