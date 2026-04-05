from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Iterable

from loguru import logger
from pydantic import BaseModel

from ezconfy.codegen.type_utils import is_enum, is_pydantic_model, resolve_type


class Extractor(ABC):
    def children(self, node: type[Any]) -> Iterable[type[Any]]:
        return []

    @abstractmethod
    def extract(self, node: type[Any]) -> None: ...

    @abstractmethod
    def emit(self) -> tuple[list[str], set[tuple[str, str]]]: ...


class ModelExtractor(Extractor):
    def __init__(self) -> None:
        self.results: list[type[BaseModel]] = []

    def children(self, node: type[Any]) -> Iterable[type[Any]]:
        if is_pydantic_model(node):
            return (f.annotation for f in node.model_fields.values() if f.annotation is not None)
        return []

    def extract(self, node: type[Any]) -> None:
        if is_pydantic_model(node):
            self.results.append(node)

    def emit(self) -> tuple[list[str], set[tuple[str, str]]]:
        body: list[str] = []
        imports: set[tuple[str, str]] = {("pydantic", "BaseModel"), ("pydantic", "Field")}

        for model in self.results:
            base = model.__bases__[0]
            parent_fields = set(base.model_fields.keys()) if is_pydantic_model(base) else set()

            field_lines: list[str] = []
            for field_name, field_info in model.model_fields.items():
                # skip inherited fields to avoid duplication
                if field_name in parent_fields:
                    continue
                annotation = field_info.annotation
                if annotation is None:
                    logger.error(f"Field '{field_name}' has no type annotation.")
                    raise ValueError(f"Field '{field_name}' has no type annotation.")
                type_str, type_imports = resolve_type(annotation)
                imports.update(type_imports)
                default_str = "..." if field_info.is_required() else repr(field_info.default)
                field_lines.append(f"    {field_name}: {type_str} = Field({default_str})")

            if not field_lines:
                field_lines.append("    pass")

            body.extend(["", "", f"class {model.__name__}({base.__name__}):"])
            body.extend(field_lines)

        return body, imports


class EnumExtractor(Extractor):
    def __init__(self) -> None:
        self.results: list[type[Enum]] = []

    def extract(self, node: type[Any]) -> None:
        if is_enum(node):
            self.results.append(node)

    def emit(self) -> tuple[list[str], set[tuple[str, str]]]:
        body: list[str] = []
        imports: set[tuple[str, str]] = set()
        for enum_type in self.results:
            imports.add(("enum", "Enum"))
            body.extend(["", "", f"class {enum_type.__name__}(Enum):"])
            for member_name, member in enum_type.__members__.items():
                body.append(f"    {member_name} = {member.value!r}")
        return body, imports


__all__ = ["Extractor", "ModelExtractor", "EnumExtractor"]
