import keyword
import re
from enum import Enum
from types import GenericAlias, UnionType
from typing import Any, ForwardRef, TypeAlias, get_args

import yaml
from pydantic import BaseModel, Field, create_model

TypeNamespace: TypeAlias = dict[str, Any]


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

        if "types" in data:
            if "schema" not in data:
                raise SchemaError(
                    "Missing root 'schema' node. When defining custom 'types', "
                    "you must also provide a 'schema' block to define the main model."
                )
            custom_types_def = data.pop("types")
            root_definition = data.pop("schema")
        else:
            custom_types_def = {}
            root_definition = data.get("schema", data)

        if not isinstance(root_definition, dict):
            raise SchemaError("Schema definition must be a dictionary.")

        type_aliases: TypeNamespace = {}

        for raw_name in custom_types_def:
            clean_name = raw_name.split("<")[0].strip()
            cls._validate_name(clean_name, "custom type")
            type_aliases[clean_name] = ForwardRef(clean_name)

        for raw_name, type_def in custom_types_def.items():
            cls._build_custom_type(raw_name, type_def, type_aliases)

        root_model = cls._build_model(
            "ConfigModel", root_definition, type_aliases=type_aliases
        )

        root_model.model_rebuild(_types_namespace=type_aliases)

        return root_model

    @classmethod
    def _build_custom_type(
        cls, raw_name: str, type_def: Any, aliases: TypeNamespace
    ) -> None:
        base_class = BaseModel
        name = raw_name.strip()

        # Support for inheritance: ModelName < BaseModelName
        if "<" in name:
            name, parent_name = map(str.strip, name.split("<", 1))
            if parent_name not in aliases:
                raise SchemaError(
                    f"Base type '{parent_name}' not defined for '{name}'."
                )
            base_class = aliases[parent_name]

        cls._validate_name(name, "custom type")

        result: Any
        if isinstance(type_def, list):
            if all(isinstance(v, int) for v in type_def):
                result = cls._build_enum(name, type_def, int)
            elif all(isinstance(v, float) for v in type_def):
                result = cls._build_enum(name, type_def, float)
            else:
                result = cls._build_enum(name, type_def, str)
        elif isinstance(type_def, dict):
            result = cls._build_model(name, type_def, aliases, base_class=base_class)
        else:
            result = cls._parse_type(str(type_def), f"types.{name}", aliases)

        aliases[name] = result

    @classmethod
    def _build_model(
        cls,
        model_name: str,
        data: dict[str, Any],
        type_aliases: TypeNamespace,
        path: str = "",
        base_class: type[BaseModel] | Any = BaseModel,
    ) -> type[BaseModel]:
        model_fields: dict[str, tuple[Any, Any]] = {}

        for field_name, value in data.items():
            field_path = f"{path}.{field_name}" if path else field_name
            cls._validate_name(field_name, "field", field_path)

            if isinstance(value, dict):
                nested_name = "".join(w.capitalize() for w in field_name.split("_"))
                nested_model = cls._build_model(
                    nested_name, value, type_aliases, field_path
                )
                model_fields[field_name] = (nested_model, Field(...))
            else:
                model_fields[field_name] = cls._parse_field_def(
                    str(value), field_path, type_aliases
                )

        return create_model(model_name, __base__=base_class, **model_fields)  # type: ignore

    @classmethod
    def _parse_field_def(
        cls, raw_value: str, path: str, aliases: TypeNamespace
    ) -> tuple[Any, Any]:
        if "=" in raw_value:
            type_part, default_part = map(str.strip, raw_value.split("=", 1))
            parsed_default = yaml.safe_load(default_part)
        else:
            type_part, parsed_default = raw_value, ...

        field_type = cls._parse_type(type_part, path, aliases)

        if parsed_default is ... and cls._is_optional(field_type):
            parsed_default = None

        field_info = (
            Field(default=parsed_default) if parsed_default is not ... else Field(...)
        )
        return (field_type, field_info)

    @classmethod
    def _parse_type(cls, type_str: str, path: str, type_aliases: dict[str, Any]) -> Any:
        type_str = type_str.strip()

        # Optional: T?
        if type_str.endswith("?"):
            inner = cls._parse_type(type_str[:-1].strip(), path, type_aliases)
            return inner | None

        # Union: T1 | T2
        if "|" in type_str:
            parts = [
                cls._parse_type(p.strip(), path, type_aliases)
                for p in type_str.split("|")
            ]
            result_type = parts[0]
            for t in parts[1:]:
                result_type |= t
            return result_type

        # List: list[T]
        m = re.fullmatch(r"list\[(.+)\]", type_str)
        if m:
            inner = cls._parse_type(m.group(1), path, type_aliases)
            return GenericAlias(list, (inner,))

        # Primitive
        if type_str in cls.PRIMITIVES:
            return cls.PRIMITIVES[type_str]

        # Alias
        if type_str in type_aliases:
            return type_aliases[type_str]

        raise SchemaError(f"Unknown or unsupported type '{type_str}' at '{path}'.")

    @staticmethod
    def _build_enum(name: str, values: list[Any], value_type: type = str) -> type[Enum]:
        if not values:
            raise SchemaError(f"Enum '{name}' cannot be empty.")
        if not all(isinstance(v, value_type) for v in values):
            raise SchemaError(
                f"Enum '{name}' contains invalid values for type {value_type.__name__}."
            )

        enum_members = {f"V{i}": v for i, v in enumerate(values)}
        return Enum(name, enum_members)  # type: ignore

    @classmethod
    def _validate_name(cls, name: str, context: str, path: str = "") -> None:
        location = f" at '{path}'" if path else ""

        if not name.isidentifier():
            raise SchemaError(
                f"Invalid {context} name '{name}'{location}. "
                "Names must start with a letter or underscore, and contain only alphanumeric characters or underscores. "
                "Spaces and hyphens (-) are not allowed."
            )
        if keyword.iskeyword(name):
            raise SchemaError(
                f"Invalid {context} name '{name}'{location}. "
                f"'{name}' is a reserved Python keyword and cannot be used."
            )

    @staticmethod
    def _is_optional(tp: Any) -> bool:
        if isinstance(tp, UnionType):
            return type(None) in get_args(tp)
        return False
