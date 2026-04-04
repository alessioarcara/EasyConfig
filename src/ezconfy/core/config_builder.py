from pathlib import Path
from typing import Any

from loguru import logger
from pydantic import BaseModel, ValidationError

from ezconfy.core.exceptions import InstantiationError
from ezconfy.core.instantiator import Instantiator
from ezconfy.core.io import read_yaml
from ezconfy.core.module_loader import ModuleLoader
from ezconfy.core.schema_parser import SchemaParser

PathLike = str | Path


class ConfigBuilder:
    def __init__(self, schema_yaml: str | None = None) -> None:
        shared_loader = ModuleLoader()
        self.instantiator = Instantiator(module_loader=shared_loader)
        self.schema_model: type[BaseModel] | None = None
        if schema_yaml:
            parser = SchemaParser(module_loader=shared_loader)
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

    def build(
        self,
        config_paths: PathLike | list[PathLike],
        overrides: dict[str, Any] | None = None,
    ) -> BaseModel | dict[str, Any]:
        """Build configuration from one or more YAML files using this builder's schema."""
        paths = [Path(p) for p in (config_paths if isinstance(config_paths, list) else [config_paths])]
        if not paths:
            raise ValueError("No configuration paths provided.")

        merged_config: dict[str, Any] = {}
        logger.info(f"Building config from {len(paths)} file(s):")
        for path in paths:
            logger.info(f"  -> Loading: {path}")
            merged_config = self._deep_merge(merged_config, read_yaml(path))

        if overrides:
            merged_config = self._deep_merge(merged_config, overrides)

        instantiated = self.instantiator(merged_config)

        if self.schema_model is None:
            return instantiated

        try:
            return self.schema_model.model_validate(instantiated)
        except ValidationError as e:
            field_errors = "; ".join(
                f"{' -> '.join(str(loc) for loc in err['loc'])}: {err['msg']}" for err in e.errors()
            )
            msg = f"Configuration validation failed ({e.error_count()} error(s)): {field_errors}"
            logger.error(msg)
            raise InstantiationError(msg) from e

    @classmethod
    def from_files(
        cls,
        config_paths: PathLike | list[PathLike],
        overrides: dict[str, Any] | None = None,
        schema_path: PathLike | None = None,
    ) -> BaseModel | dict[str, Any]:
        """Build configuration from one or more YAML files with optional overrides and schema."""
        schema_yaml: str | None = None
        if schema_path:
            try:
                schema_yaml = Path(schema_path).read_text(encoding="utf-8")
            except Exception as e:
                logger.error(f"Failed to read schema file {schema_path}: {e}")
                raise

        builder = cls(schema_yaml=schema_yaml)
        return builder.build(config_paths, overrides=overrides)
