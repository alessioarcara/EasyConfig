import re
from types import GenericAlias, UnionType
from typing import Any, ForwardRef, get_args

import yaml
from pydantic import BaseModel, create_model


class SchemaError(Exception):
    pass


class SchemaParser:
    PRIMITIVES: dict[str, type] = {
        "int": int,
        "float": float,
        "str": str,
        "bool": bool,
    }

    @classmethod
    def parse(cls, config_str: str) -> type[BaseModel]:
        data = yaml.safe_load(config_str) or {}

        custom_types_def = data.get("types", {})
        root_definition = data.get("schema", data) if custom_types_def else data

        type_aliases: dict[str, Any] = {}

        for name in custom_types_def:
            type_aliases[name] = ForwardRef(name)

        for name, type_def in custom_types_def.items():
            # CASE A: If the type_def is a dict, it's a nested Pydantic model
            if isinstance(type_def, dict):
                type_aliases[name] = cls._build_model(
                    name, type_def, type_aliases=type_aliases
                )
            # CASE B: If it's a string, it's either a primitive, an alias, or a complex type
            else:
                type_aliases[name] = cls._parse_type(
                    str(type_def), path=f"types.{name}", type_aliases=type_aliases
                )

        root_model = cls._build_model(
            "ConfigModel", root_definition, type_aliases=type_aliases
        )
        root_model.model_rebuild(_types_namespace=type_aliases)

        return root_model

    @classmethod
    def _build_model(
        cls,
        model_name: str,
        data: dict[str, Any],
        path: str = "",
        type_aliases: dict[str, Any] | None = None,
    ) -> type[BaseModel]:
        if type_aliases is None:
            type_aliases = {}

        model_fields: dict[str, tuple[Any, Any]] = {}

        for field_name, value in data.items():
            field_path = f"{path}.{field_name}" if path else field_name

            # CASE A: Dict -> it's a nested Pydantic Model
            if isinstance(value, dict):
                nested_model = cls._build_model(
                    field_name, value, field_path, type_aliases
                )
                model_fields[field_name] = (nested_model, ...)

            # CASE B: String -> Parse type and default value
            else:
                # "type = default" -> type_part = "type", default = "default_part"
                if isinstance(value, str) and "=" in value:
                    type_part, default_part = map(str.strip, value.split("=", 1))
                    default = yaml.safe_load(default_part)
                # "type" -> type_part = "type", default = ...
                else:
                    type_part = value
                    default = ...

                field_type = cls._parse_type(str(type_part), field_path, type_aliases)

                if default is ... and cls._is_optional(field_type):
                    default = None

                model_fields[field_name] = (field_type, default)

        return create_model(model_name, **model_fields)  # type: ignore

    @classmethod
    def _parse_type(cls, type_str: str, path: str, type_aliases: dict[str, Any]) -> Any:
        type_str = type_str.strip()

        # optional type: T?
        if type_str.endswith("?"):
            inner = cls._parse_type(type_str[:-1].strip(), path, type_aliases)
            return inner | None

        # union type: T1 | T2
        if "|" in type_str:
            parts = [
                cls._parse_type(p.strip(), path, type_aliases)
                for p in type_str.split("|")
            ]
            result_type = parts[0]
            for t in parts[1:]:
                result_type |= t
            return result_type

        # list[T]
        m = re.fullmatch(r"list\[(.+)\]", type_str)
        if m:
            inner = cls._parse_type(m.group(1), path, type_aliases)
            return GenericAlias(list, (inner,))

        # primitive
        if type_str in cls.PRIMITIVES:
            return cls.PRIMITIVES[type_str]

        # alias resolving
        if type_str in type_aliases:
            return type_aliases[type_str]

        raise SchemaError(f"Unsupported type '{type_str}' at '{path}'")

    @staticmethod
    def _is_optional(tp: Any) -> bool:
        if isinstance(tp, UnionType):
            return type(None) in get_args(tp)
        return False
