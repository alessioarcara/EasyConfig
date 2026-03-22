import keyword
import re
from enum import Enum
from graphlib import TopologicalSorter
from types import GenericAlias, UnionType
from typing import Any, ForwardRef, TypeAlias, cast, get_args

import yaml
from pydantic import BaseModel, ConfigDict, Field, create_model

from easyconfig.module_loader import ModuleLoader

TypeNamespace: TypeAlias = dict[str, Any]


class SchemaError(Exception):
    pass


class SchemaParser:
    def __init__(self) -> None:
        self.primitives: dict[str, type] = {
            "int": int,
            "float": float,
            "str": str,
            "bool": bool,
        }

        self.type_aliases: TypeNamespace = {}
        self.module_loader = ModuleLoader()

    def parse(self, config_str: str) -> type[BaseModel]:
        self.type_aliases.clear()

        data = yaml.safe_load(config_str) or {}

        if "types" in data and "schema" not in data:
            raise SchemaError(
                "Missing root 'schema' node at top level when 'types' is defined. "
                "Please define a 'schema' key containing your configuration."
            )

        custom_types_def = data.pop("types", {})
        root_definition = data.pop("schema", data)

        if not isinstance(root_definition, dict):
            raise SchemaError("Schema definition at top level must be a dictionary.")

        self._process_custom_types(custom_types_def)
        root_model = self._build_model("ConfigModel", root_definition, path="schema")
        root_model.model_rebuild(_types_namespace=self.type_aliases)

        return root_model

    def _process_custom_types(self, custom_types_def: dict[str, Any]) -> None:
        ts: TopologicalSorter[str] = TopologicalSorter()
        raw_map: dict[str, str] = {}

        for raw_name, type_def in custom_types_def.items():
            name = raw_name.split("<")[0].strip()
            deps = []

            if "<" in raw_name:
                deps.append(raw_name.split("<")[1].strip())
            if isinstance(type_def, str) and type_def not in self.primitives:
                deps.append(type_def.strip())

            raw_map[name] = raw_name
            self.type_aliases[name] = ForwardRef(name)
            ts.add(name, *deps)

        try:
            build_order = list(ts.static_order())
        except ValueError as e:
            raise SchemaError(
                f"Circular dependency detected among custom types: {e}. "
                "Check the order of type definitions or remove circular references."
            )

        for name in build_order:
            if name in raw_map:
                raw_name = raw_map[name]
                self._build_custom_type(raw_name, custom_types_def[raw_name])

    def _build_custom_type(self, raw_name: str, type_def: Any) -> None:
        base_class = BaseModel
        name = raw_name.strip()

        if "<" in name:
            name, parent_name = map(str.strip, name.split("<", 1))
            if parent_name not in self.type_aliases:
                raise SchemaError(f"Base type '{parent_name}' not defined for '{name}' at '{raw_name}'.")
            base_class = self.type_aliases[parent_name]

        self._validate_name(name, "custom type", raw_name)

        if isinstance(type_def, list):
            if not type_def:
                raise SchemaError(
                    f"Enum '{name}' at '{raw_name}' cannot be empty. "
                    "Provide at least one value, e.g., ['RED', 'GREEN']."
                )
            self.type_aliases[name] = Enum(name, {f"V{i}": v for i, v in enumerate(type_def)})
        elif isinstance(type_def, dict):
            self.type_aliases[name] = self._build_model(name, type_def, base_class=base_class, path=raw_name)
        else:
            self.type_aliases[name] = self._parse_type(str(type_def), f"types.{name}")

    def _build_model(
        self,
        model_name: str,
        data: dict[str, Any],
        path: str = "",
        base_class: type[BaseModel] | Any = BaseModel,
    ) -> type[BaseModel]:
        model_fields: dict[str, tuple[Any, Any]] = {}

        for field_name, value in data.items():
            field_path = f"{path}.{field_name}" if path else field_name
            self._validate_name(field_name, "field", field_path)

            if isinstance(value, dict):
                nested_name = "".join(w.capitalize() for w in field_name.split("_"))
                nested_model = self._build_model(nested_name, value, field_path)
                model_fields[field_name] = (nested_model, Field(...))
            else:
                parts = [p.strip() for p in str(value).split("=", 1)]
                field_type = self._parse_type(parts[0], field_path)

                if len(parts) > 1:
                    parsed_default = yaml.safe_load(parts[1])
                    model_fields[field_name] = (
                        field_type,
                        Field(default=parsed_default),
                    )
                else:
                    is_optional = isinstance(field_type, UnionType) and type(None) in get_args(field_type)
                    model_fields[field_name] = (
                        field_type,
                        Field(default=None if is_optional else ...),
                    )

        model = create_model(
            model_name,
            __base__=base_class,
            __config__=ConfigDict(arbitrary_types_allowed=True),
            **model_fields,
        )  # type: ignore

        return cast(type[BaseModel], model)

    def _parse_type(self, type_str: str, path: str) -> Any:
        type_str = type_str.strip()

        # Optional type
        if type_str.endswith("?"):
            return self._parse_type(type_str[:-1], path) | None

        # Union type
        if "|" in type_str:
            parts = [self._parse_type(p, path) for p in type_str.split("|")]
            result_type = parts[0]
            for t in parts[1:]:
                result_type |= t
            return result_type

        # List type
        if m := re.fullmatch(r"list\[(.+)\]", type_str):
            return GenericAlias(list, (self._parse_type(m.group(1), path),))

        # Primitive type
        if type_str in self.primitives:
            return self.primitives[type_str]

        # Custom type alias
        if type_str in self.type_aliases:
            return self.type_aliases[type_str]

        # External type via ModuleLoader
        try:
            return self.module_loader.load_class(type_str)
        except Exception as e:
            raise SchemaError(f"Failed to load external type '{type_str}' at '{path}'. Error: {e}. ") from e

    def _validate_name(self, name: str, context: str, path: str = "") -> None:
        location = f" at '{path}'" if path else ""
        if not name.isidentifier() or keyword.iskeyword(name):
            raise SchemaError(
                f"Invalid {context} name '{name}'{location}. "
                "Must be a valid, non-keyword Python identifier without spaces or hyphens. "
                "For example: 'MyField' or 'custom_type'."
            )
