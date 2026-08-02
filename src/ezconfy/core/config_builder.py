from pathlib import Path
from typing import Any

from loguru import logger
from pydantic import BaseModel, ValidationError

from ezconfy.core.exceptions import InstantiationError, MergeError
from ezconfy.core.instantiator import Instantiator
from ezconfy.core.io import read_yaml
from ezconfy.core.module_loader import ModuleLoader
from ezconfy.core.schema_parser import SchemaParser

PathLike = str | Path

# Reserved tokens for patching lists during merge (see `_merge_list`).
_REST_MARKER = "..."
_ID_KEY = "_id_"
_DELETE_KEY = "_delete_"

# Reserved tokens for patching lists during merge (see `_merge_list`).
_REST_MARKER = "..."
_ID_KEY = "_id_"
_DELETE_KEY = "_delete_"


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
            elif isinstance(v, list) and _REST_MARKER in v:
                base = merged.get(k)
                merged[k] = ConfigBuilder._merge_list(base if isinstance(base, list) else [], v)
            else:
                merged[k] = v
        return merged

    @staticmethod
    def _merge_list(base: list[Any], patch: list[Any]) -> list[Any]:
        """Patch ``base`` with ``patch``, where ``...`` expands to the base elements.

        Patch elements are matched against base elements by ``_id_`` or, failing
        that, by ``_target_type_`` (first unmatched occurrence). Matched elements
        are deep-merged in place, keeping their base position; ``_delete_: true``
        removes the matched element; unmatched patch elements are inserted at
        their own position, before or after the ``...`` expansion.
        """
        if patch.count(_REST_MARKER) > 1:
            raise MergeError("A list patch may contain at most one '...' marker.")

        consumed: set[int] = set()

        def find_match(el: Any) -> int | None:
            if not isinstance(el, dict):
                return None
            el_id, el_target = el.get(_ID_KEY), el.get("_target_type_")
            for i, base_el in enumerate(base):
                if i in consumed or not isinstance(base_el, dict):
                    continue
                if el_id is not None:
                    if base_el.get(_ID_KEY) == el_id:
                        return i
                elif el_target is not None and base_el.get("_target_type_") == el_target:
                    return i
            return None

        patched: dict[int, Any] = {}
        deleted: set[int] = set()
        prefix: list[Any] = []
        suffix: list[Any] = []
        new_elements = prefix
        for el in patch:
            if el == _REST_MARKER:
                new_elements = suffix
                continue
            match = find_match(el)
            if isinstance(el, dict) and el.get(_DELETE_KEY):
                if match is None:
                    raise MergeError(f"List patch element marked '{_DELETE_KEY}' matches no base element: {el}")
                consumed.add(match)
                deleted.add(match)
            elif match is not None:
                consumed.add(match)
                patched[match] = ConfigBuilder._deep_merge(base[match], el)
            else:
                new_elements.append(el)
        expanded = [patched.get(i, base_el) for i, base_el in enumerate(base) if i not in deleted]
        return prefix + expanded + suffix

    @staticmethod
    def _strip_ids(node: Any) -> Any:
        """Recursively remove ``_id_`` keys, which only exist to match list elements."""
        if isinstance(node, dict):
            return {k: ConfigBuilder._strip_ids(v) for k, v in node.items() if k != _ID_KEY}
        if isinstance(node, list):
            return [ConfigBuilder._strip_ids(item) for item in node]
        return node

    def build(
        self,
        config_paths: PathLike | list[PathLike],
        overrides: dict[str, Any] | None = None,
        return_raw_config: bool = False,
    ) -> BaseModel | dict[str, Any] | tuple[BaseModel | dict[str, Any], dict[str, Any]]:
        """Build configuration from one or more YAML files using this builder's schema.

        When ``return_raw_config`` is True, return a tuple of
        ``(built_config, raw_config)`` where ``raw_config`` is the merged YAML
        dict before instantiation.
        """
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
        merged_config = self._strip_ids(merged_config)

        instantiated = self.instantiator(merged_config, schema_model=self.schema_model)

        built: BaseModel | dict[str, Any]
        if self.schema_model is None:
            built = instantiated
        else:
            try:
                built = self.schema_model.model_validate(instantiated)
            except ValidationError as e:
                field_errors = "; ".join(
                    f"{' -> '.join(str(loc) for loc in err['loc'])}: {err['msg']}" for err in e.errors()
                )
                msg = f"Configuration validation failed ({e.error_count()} error(s)): {field_errors}"
                logger.error(msg)
                raise InstantiationError(msg) from e

        if return_raw_config:
            return built, merged_config
        return built

    @classmethod
    def from_files(
        cls,
        config_paths: PathLike | list[PathLike],
        overrides: dict[str, Any] | None = None,
        schema_path: PathLike | None = None,
        return_raw_config: bool = False,
    ) -> BaseModel | dict[str, Any] | tuple[BaseModel | dict[str, Any], dict[str, Any]]:
        """Build configuration from one or more YAML files with optional overrides and schema.

        When ``return_raw_config`` is True, return a tuple of ``(built_config,
        raw_config)``.
        """
        schema_yaml: str | None = None
        if schema_path:
            try:
                schema_yaml = Path(schema_path).read_text(encoding="utf-8")
            except Exception as e:
                logger.error(f"Failed to read schema file {schema_path}: {e}")
                raise

        builder = cls(schema_yaml=schema_yaml)
        return builder.build(config_paths, overrides=overrides, return_raw_config=return_raw_config)
