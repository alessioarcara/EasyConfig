from typing import Any

import yaml

from easyconfig.module_loader import ModuleLoader


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

    def __init__(self) -> None:
        self._loader = ModuleLoader()

    def __call__(self, config: str | dict[str, Any]) -> Any:
        if isinstance(config, str):
            data = yaml.safe_load(config)
        else:
            data = config

        return self._instantiate(data)

    def _instantiate(self, obj: Any) -> Any:
        """
        - dict with "_target_type_" -> instantiate class
        - dict without "_target_type_" -> recurse on values
        - list -> recurse on elements
        - primitives -> return as-is
        """
        if isinstance(obj, dict):
            if "_target_type_" in obj:
                cls: Any = self._loader.load_class(obj["_target_type_"])
                return cls(**obj.get("_init_args_", {}))
            return {k: self._instantiate(v) for k, v in obj.items()}

        if isinstance(obj, list):
            return [self._instantiate(v) for v in obj]

        return obj
