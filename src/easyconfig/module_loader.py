from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import TypeVar

T = TypeVar("T")


class ModuleLoader:
    def __init__(self) -> None:
        self._file_cache: dict[Path, ModuleType] = {}

    def load_class(self, target: str) -> type[T]:
        """
        Load a class from:
        - module.path:ClassName
        - /path/to/file.py:ClassName
        """
        try:
            module_path, class_name = target.split(":", 1)
        except ValueError as e:
            raise ValueError(f"Invalid target '{target}', expected 'module:ClassName'") from e

        if self._is_file_path(module_path):
            module = self._load_from_file(Path(module_path))
        else:
            module = self._load_from_import(module_path)

        try:
            obj = getattr(module, class_name)
        except AttributeError as e:
            raise AttributeError(f"Class '{class_name}' not found in '{target}'") from e

        if not isinstance(obj, type):
            raise TypeError(f"Target '{target}' is not a class (got {type(obj).__name__})")

        return obj

    def _is_file_path(self, module_path: str) -> bool:
        return module_path.endswith(".py") or "/" in module_path

    def _load_from_import(self, module_path: str) -> ModuleType:
        try:
            return importlib.import_module(module_path)
        except ImportError as e:
            raise ImportError(f"Cannot import module '{module_path}': {e}") from e

    def _load_from_file(self, file_path: Path) -> ModuleType:
        file_path = file_path.resolve()

        # cache hit
        if file_path in self._file_cache:
            return self._file_cache[file_path]

        if not file_path.exists():
            raise FileNotFoundError(f"Python file not found: {file_path}")

        # reuse already loaded module
        for module in sys.modules.values():
            module_file = getattr(module, "__file__", None)
            if module_file and Path(module_file).resolve() == file_path:
                self._file_cache[file_path] = module
                return module

        module_name = f"_dynamic_{file_path.stem}_{abs(hash(file_path))}"
        spec = importlib.util.spec_from_file_location(module_name, file_path)

        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load module from {file_path}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        self._file_cache[file_path] = module
        return module

    def _get_class(
        self,
        module: ModuleType,
        class_name: str,
        target: str,
    ) -> type[T]:
        try:
            obj = getattr(module, class_name)
        except AttributeError as e:
            raise AttributeError(f"Class '{class_name}' not found in '{target}'") from e

        if not isinstance(obj, type):
            raise TypeError(f"Target '{target}' is not a class (got {type(obj).__name__})")

        return obj
