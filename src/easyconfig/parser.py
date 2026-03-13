import re
from types import GenericAlias
from typing import Any

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
        "null": type(None),
    }

    @classmethod
    def parse(cls, config_str: str) -> type[BaseModel]:
        """
        Parse a YAML string and generate a Pydantic BaseModel.

        Args:
            config_str (str): A YAML-formatted string representing the configuration schema.

        Returns:
            type[BaseModel]: A dynamically generated Pydantic model class based on the provided schema.

        Raises:
            SchemaError: If an unsupported type is encountered.
            yaml.YAMLError: If the YAML string is malformed.
        """
        data = yaml.safe_load(config_str)
        return cls._build_model("ConfigModel", data)

    @classmethod
    def _build_model(
        cls, model_name: str, data: dict[str, Any], path: str = ""
    ) -> type[BaseModel]:
        model_fields: dict[str, tuple[Any, Any]] = {}

        for field_name, value in data.items():
            field_path = f"{path}.{field_name}" if path else field_name

            # Nested model
            if isinstance(value, dict):
                nested_model = cls._build_model(field_name, value, field_path)
                model_fields[field_name] = (nested_model, ...)  # ? model is required ?

            else:
                # Split type = default
                if isinstance(value, str) and "=" in value:
                    type_part, default_part = map(str.strip, value.split("=", 1))
                    default = yaml.safe_load(default_part)

                else:
                    type_part = value
                    default = ...

                field_type = cls._parse_type(type_part, field_path)
                if "None" in str(field_type):
                    default = None

                model_fields[field_name] = (field_type, default)

        return create_model(model_name, **model_fields)  # type: ignore

    @classmethod
    def _parse_type(cls, type_str: str, path: str) -> Any:
        type_str = type_str.strip()

        # union types: T1 | T2
        if "|" in type_str:
            parts = [cls._parse_type(p.strip(), path) for p in type_str.split("|")]
            result_type = parts[0]
            for t in parts[1:]:
                result_type |= t  # operator |
            return result_type

        # list[T]
        m = re.fullmatch(r"list\[(.+)\]", type_str)
        if m:
            inner = cls._parse_type(m.group(1), path)
            return GenericAlias(list, (inner,))

        # primitive
        if type_str in cls.PRIMITIVES:
            return cls.PRIMITIVES[type_str]

        raise SchemaError(f"Unsupported type '{type_str}' at '{path}'")
