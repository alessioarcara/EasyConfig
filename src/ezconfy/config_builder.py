from pathlib import Path
from typing import Any

from loguru import logger
from pydantic import BaseModel, ValidationError

from ezconfy.instantiator import Instantiator
from ezconfy.io import read_yaml
from ezconfy.schema_parser import SchemaParser

PathLike = str | Path


class ConfigBuilder:
    def __init__(self, schema_yaml: str | None = None) -> None:
        self.instantiator = Instantiator()
        self.schema_model: type[BaseModel] | None = None
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

    @classmethod
    def from_files(
        cls,
        config_paths: PathLike | list[PathLike],
        overrides: dict[str, Any] | None = None,
        schema_path: PathLike | None = None,
    ) -> BaseModel | dict[str, Any]:
        """Build configuration from one or more YAML files with optional overrides and schema."""
        # Normalize paths
        paths = [Path(p) for p in (config_paths if isinstance(config_paths, list) else [config_paths])]
        if not paths:
            raise ValueError("No configuration paths provided.")

        # Merge all config files
        merged_config: dict[str, Any] = {}
        logger.info(f"Building config from {len(paths)} file(s):")
        for path in paths:
            logger.info(f"  -> Loading: {path}")
            merged_config = cls._deep_merge(merged_config, read_yaml(path))

        # Apply overrides
        if overrides:
            merged_config = cls._deep_merge(merged_config, overrides)

        # Load schema if provided
        schema_yaml: str | None = None
        if schema_path:
            try:
                schema_yaml = Path(schema_path).read_text(encoding="utf-8")
            except Exception as e:
                logger.error(f"Failed to read schema file {schema_path}: {e}")
                raise

        # Instantiate objects
        builder = cls(schema_yaml=schema_yaml)
        instantiated = builder.instantiator(merged_config)  # pass dict directly

        # If no schema, return raw instantiated dict
        if builder.schema_model is None:
            return instantiated

        # Validate with Pydantic schema
        try:
            return builder.schema_model.model_validate(instantiated)
        except ValidationError as e:
            logger.error(f"Configuration validation failed:\n{e}")
            raise ValueError(f"Configuration validation failed: {e}") from e
