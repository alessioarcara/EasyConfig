import importlib
import importlib.util
import sys
from pathlib import Path
from typing import Any

import yaml


class Instantiator:
    """
    YAML-driven object instantiator with support for both Python module targets
    and direct file-based targets.

    Supported target formats
    ------------------------
    1. Python import path:
        package.module:ClassName

       Example:
        tests.test_instantiator:FakeDataset

    2. File path:
        /absolute/path/to/file.py:ClassName
        relative/path/to/file.py:ClassName

       Example:
        tests/test_instantiator.py:FakeDataset
    """

    def __call__(self, config: str) -> dict[str, Any]:
        data = yaml.safe_load(config)
        build_config: dict[str, Any] = {}

        for field, value in data.items():
            if isinstance(value, dict) and "_target_type_" in value:
                target = value["_target_type_"]
                args = value.get("_init_args_", {})

                cls = self._load_target(target)
                build_config[field] = cls(**args)

        return build_config

    def _load_target(self, target: str) -> type[Any]:
        """
        Supports:
        - Python dotted path:
          tests.test_instantiator:FakeDataset

        - Absolute/relative file path:
          /abs/path/to/test_instantiator.py:FakeDataset
          tests/test_instantiator.py:FakeDataset
        """
        if ".py:" in target or target.endswith(".py"):
            return self._load_from_file_path(target)

        return self._load_from_python_path(target)

    def _load_from_python_path(self, target: str) -> type[Any]:
        try:
            module_path, class_name = target.split(":", 1)
        except ValueError as e:
            raise ValueError(
                "Module path targets must be in the format 'module.ClassName'"
            ) from e

        module = importlib.import_module(module_path)
        return getattr(module, class_name)  # type: ignore

    def _load_from_file_path(self, target: str) -> type[Any]:
        try:
            file_path_str, class_name = target.split(":", 1)
        except ValueError as e:
            raise ValueError(
                "File path targets must be in the format '/path/to/file.py:ClassName'"
            ) from e

        file_path = Path(file_path_str).resolve()
        if not file_path.exists():
            raise FileNotFoundError(f"Python file not found: {file_path}")

        # Reuse an already-loaded module if it points to the same file
        for module in sys.modules.values():
            module_file = getattr(module, "__file__", None)
            if module_file is not None and Path(module_file).resolve() == file_path:
                try:
                    return getattr(module, class_name)  # type: ignore
                except AttributeError as e:
                    raise AttributeError(
                        f"Class '{class_name}' not found in already loaded module '{module.__name__}'"
                    ) from e

        # Otherwise load it dynamically
        module_name = f"_dynamic_module_{file_path.stem}_{abs(hash(file_path))}"
        spec = importlib.util.spec_from_file_location(module_name, file_path)

        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot create import spec for {file_path}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        try:
            return getattr(module, class_name)  # type: ignore
        except AttributeError as e:
            raise AttributeError(
                f"Class '{class_name}' not found in file '{file_path}'"
            ) from e
