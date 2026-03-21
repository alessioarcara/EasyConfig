import keyword
import re
from enum import Enum
from graphlib import TopologicalSorter
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

        if "types" in data and "schema" not in data:
            raise SchemaError("Missing root 'schema' node when 'types' is defined.")

        custom_types_def = data.pop("types", {})
        root_definition = data.pop("schema", data)

        if not isinstance(root_definition, dict):
            raise SchemaError("Schema definition must be a dictionary.")

        type_aliases = cls._process_custom_types(custom_types_def)
        root_model = cls._build_model("ConfigModel", root_definition, type_aliases)
        root_model.model_rebuild(_types_namespace=type_aliases)

        return root_model

    @classmethod
    def _process_custom_types(cls, custom_types_def: dict[str, Any]) -> TypeNamespace:
        type_aliases: TypeNamespace = {}
        ts: TopologicalSorter[str] = TopologicalSorter()
        raw_map: dict[str, str] = {}

        for raw_name, type_def in custom_types_def.items():
            name = raw_name.split("<")[0].strip()
            deps = []

            if "<" in raw_name:
                deps.append(raw_name.split("<")[1].strip())
            if isinstance(type_def, str) and type_def not in cls.PRIMITIVES:
                deps.append(type_def.strip())

            raw_map[name] = raw_name
            type_aliases[name] = ForwardRef(name)
            ts.add(name, *deps)

        try:
            build_order = list(ts.static_order())
        except ValueError as e:
            raise SchemaError(f"Circular dependency detected: {e}")

        for name in build_order:
            if name in raw_map:
                raw_name = raw_map[name]
                cls._build_custom_type(
                    raw_name, custom_types_def[raw_name], type_aliases
                )

        return type_aliases

    @classmethod
    def _build_custom_type(
        cls, raw_name: str, type_def: Any, aliases: TypeNamespace
    ) -> None:
        base_class = BaseModel
        name = raw_name.strip()

        if "<" in name:
            name, parent_name = map(str.strip, name.split("<", 1))
            if parent_name not in aliases:
                raise SchemaError(
                    f"Base type '{parent_name}' not defined for '{name}'."
                )
            base_class = aliases[parent_name]

        cls._validate_name(name, "custom type")

        if isinstance(type_def, list):
            if not type_def:
                raise SchemaError(f"Enum '{name}' cannot be empty.")
            aliases[name] = Enum(name, {f"V{i}": v for i, v in enumerate(type_def)})
        elif isinstance(type_def, dict):
            aliases[name] = cls._build_model(
                name, type_def, aliases, base_class=base_class
            )
        else:
            aliases[name] = cls._parse_type(str(type_def), f"types.{name}", aliases)

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
                parts = [p.strip() for p in str(value).split("=", 1)]
                field_type = cls._parse_type(parts[0], field_path, type_aliases)

                if len(parts) > 1:
                    parsed_default = yaml.safe_load(parts[1])
                    model_fields[field_name] = (
                        field_type,
                        Field(default=parsed_default),
                    )
                else:
                    is_optional = isinstance(field_type, UnionType) and type(
                        None
                    ) in get_args(field_type)
                    model_fields[field_name] = (
                        field_type,
                        Field(default=None if is_optional else ...),
                    )

        return create_model(model_name, __base__=base_class, **model_fields)  # type: ignore

    @classmethod
    def _parse_type(cls, type_str: str, path: str, type_aliases: dict[str, Any]) -> Any:
        type_str = type_str.strip()

        if type_str.endswith("?"):
            return cls._parse_type(type_str[:-1], path, type_aliases) | None

        if "|" in type_str:
            parts = [
                cls._parse_type(p, path, type_aliases) for p in type_str.split("|")
            ]
            result_type = parts[0]
            for t in parts[1:]:
                result_type |= t
            return result_type

        if m := re.fullmatch(r"list\[(.+)\]", type_str):
            return GenericAlias(
                list, (cls._parse_type(m.group(1), path, type_aliases),)
            )

        if type_str in cls.PRIMITIVES:
            return cls.PRIMITIVES[type_str]

        if type_str in type_aliases:
            return type_aliases[type_str]

        raise SchemaError(f"Unknown or unsupported type '{type_str}' at '{path}'.")

    @classmethod
    def _validate_name(cls, name: str, context: str, path: str = "") -> None:
        location = f" at '{path}'" if path else ""
        if not name.isidentifier() or keyword.iskeyword(name):
            raise SchemaError(
                f"Invalid {context} name '{name}'{location}. "
                "Must be a valid, non-keyword Python identifier without spaces or hyphens."
            )
