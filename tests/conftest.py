from pathlib import Path

import pytest


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
