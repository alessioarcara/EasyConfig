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

    def __call__(self, config: str) -> dict[str, Any]:
        data = yaml.safe_load(config)
        build_config: dict[str, Any] = {}

        for field, value in data.items():
            if isinstance(value, dict) and "_target_type_" in value:
                target = value["_target_type_"]
                args = value.get("_init_args_", {})

                cls: Any = self._loader.load_class(target)
                build_config[field] = cls(**args)
            else:
                build_config[field] = value

        return build_config
