from pathlib import Path
from typing import Any, Optional, Union, cast

import yaml
from loguru import logger
from pydantic import BaseModel, ValidationError

from easyconfig.instantiator import Instantiator
from easyconfig.parser import SchemaParser

pathLike = Union[str, Path]


class ConfigBuilder:
    def __init__(self, schema_yaml: Optional[str] = None) -> None:
        self.instantiator = Instantiator()
        self.schema_model: Optional[type[BaseModel]] = None
        if schema_yaml:
            parser = SchemaParser()
            self.schema_model = parser.parse(schema_yaml)

    @staticmethod
    def _deep_merge(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
        """Recursively merge dict b into dict a."""
        merged = a.copy()
        for k, v in b.items():
            if k in merged and isinstance(merged[k], dict) and isinstance(v, dict):
                merged[k] = ConfigBuilder._deep_merge(merged[k], v)
            else:
                merged[k] = v
        return merged

    @staticmethod
    def _read_yaml(path: Path) -> dict[str, Any]:
        """Load a YAML file and return it as a dict."""
        try:
            with path.open("r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(f"❌ Failed to read YAML file {path}: {e}")
            raise

    @classmethod
    def from_files(
        cls,
        config_paths: Union[pathLike, list[pathLike]],
        overrides: Optional[dict[str, Any]] = None,
        schema_path: Optional[pathLike] = None,
    ) -> BaseModel | dict[str, Any]:
        """Build configuration from one or more YAML files with optional overrides and schema."""
        # Normalize paths
        paths = [Path(p) for p in (config_paths if isinstance(config_paths, list) else [config_paths])]
        if not paths:
            raise ValueError("No configuration paths provided.")

        # Merge all config files
        merged_config: dict[str, Any] = {}
        logger.info(f"📄 Building config from {len(paths)} file(s):")
        for path in paths:
            logger.info(f"    -> Loading: {path}")
            merged_config = cls._deep_merge(merged_config, cls._read_yaml(path))

        # Apply overrides
        if overrides:
            merged_config = cls._deep_merge(merged_config, overrides)

        # Load schema if provided
        schema_yaml: Optional[str] = None
        if schema_path:
            try:
                schema_yaml = Path(schema_path).read_text(encoding="utf-8")
            except Exception as e:
                logger.error(f"❌ Failed to read schema file {schema_path}: {e}")
                raise

        # Instantiate objects
        builder = cls(schema_yaml=schema_yaml)
        instantiated = builder.instantiator(merged_config)  # pass dict directly

        # If no schema, return raw instantiated dict
        if builder.schema_model is None:
            return cast(dict[str, Any], instantiated)

        # Validate with Pydantic schema
        try:
            return builder.schema_model(**instantiated)
        except ValidationError as e:
            logger.error(f"❌ Configuration validation failed:\n{e}")
            raise ValueError(f"Configuration validation failed: {e}") from e
