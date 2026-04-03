from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from types import UnionType
from typing import Any, TypeGuard, Union, get_args, get_origin

import typer
from loguru import logger
from pydantic import BaseModel

from ezconfy.schema_parser import SchemaParser

app = typer.Typer()


def _is_union(t: object) -> bool:
    # Handles both `Union[A, B]` (typing) and `A | B` (PEP 604 / UnionType)
    origin = get_origin(t)
    return origin is Union or isinstance(t, UnionType)


def _is_pydantic_model(annotation: Any) -> TypeGuard[type[BaseModel]]:
    return isinstance(annotation, type) and issubclass(annotation, BaseModel) and annotation is not BaseModel


def _is_enum(annotation: Any) -> TypeGuard[type[Enum]]:
    return isinstance(annotation, type) and issubclass(annotation, Enum)


def _is_builtin(annotation: Any) -> bool:
    return getattr(annotation, "__module__", None) == "builtins"


def resolve_type(annotation: type[Any]) -> tuple[str, set[tuple[str, str]]]:
    type_str: str
    imports: set[tuple[str, str]] = set()
    origin = get_origin(annotation)

    if origin is not None:
        # Generic type: List[X], Dict[K, V], Optional[X], Union[A, B], etc.
        args = get_args(annotation)
        if _is_union(annotation):
            non_none_args = [a for a in args if a is not type(None)]
            has_none = type(None) in args
            resolved = []
            for arg in non_none_args:
                arg_str, arg_imports = resolve_type(arg)
                resolved.append(arg_str)
                imports.update(arg_imports)
            type_str = " | ".join(resolved)
            if has_none:
                type_str += " | None"
        else:
            # Non-union generic: recurse into each type argument
            resolved = []
            for arg in args:
                arg_str, arg_imports = resolve_type(arg)
                resolved.append(arg_str)
                imports.update(arg_imports)
            origin_name = getattr(origin, "__name__", str(origin))
            type_str = f"{origin_name}[{', '.join(resolved)}]"

    elif _is_pydantic_model(annotation) or _is_enum(annotation) or _is_builtin(annotation):
        type_str = annotation.__name__
    else:
        type_str = annotation.__name__
        imports.add((annotation.__module__, annotation.__name__))

    return type_str, imports


def _walk_schema(
    annotation: Any,
    visited: list[type[Any]] | None = None,
) -> list[type[Any]]:
    seen: set[int] = set()
    ordered_nodes = visited if visited is not None else []

    def _visit(current: Any) -> None:
        origin = get_origin(current)
        if origin is not None:
            for arg in get_args(current):
                _visit(arg)
            return

        if not isinstance(current, type):
            return

        current_id = id(current)
        if current_id in seen:
            return
        seen.add(current_id)

        if _is_pydantic_model(current):
            for field_info in current.model_fields.values():
                if field_info.annotation is not None:
                    _visit(field_info.annotation)

        ordered_nodes.append(current)

    _visit(annotation)
    return ordered_nodes


@dataclass
class SchemaTypes:
    models: list[type[BaseModel]] = field(default_factory=list)
    enums: list[type[Enum]] = field(default_factory=list)


def _collect_schema_types(model: type[BaseModel]) -> SchemaTypes:
    schema_types = SchemaTypes()
    for node in _walk_schema(model):
        if _is_pydantic_model(node):
            schema_types.models.append(node)
        elif _is_enum(node):
            schema_types.enums.append(node)

    schema_types.models = [nested_model for nested_model in schema_types.models if nested_model is not model]
    return schema_types


def _emit_enum_block(enum_type: type[Enum]) -> list[str]:
    lines = [f"class {enum_type.__name__}(Enum):"]
    for member_name, member in enum_type.__members__.items():
        lines.append(f"    {member_name} = {member.value!r}")
    return lines


def _emit_class_block(model: type[BaseModel]) -> tuple[list[str], set[tuple[str, str]]]:
    """Return (field_lines, imports) for a single model class."""
    all_imports: set[tuple[str, str]] = set()
    field_lines: list[str] = []

    for field_name, field_info in model.model_fields.items():
        annotation = field_info.annotation
        if annotation is None:
            logger.error(f"Field '{field_name}' has no type annotation.")
            raise ValueError(f"Field '{field_name}' has no type annotation.")

        type_str, type_imports = resolve_type(annotation)
        all_imports.update(type_imports)

        if field_info.is_required():
            default_str = "..."
        else:
            default_str = repr(field_info.default)

        field_lines.append(f"    {field_name}: {type_str} = Field({default_str})")

    if not field_lines:
        field_lines.append("    pass")

    return field_lines, all_imports


def run_generation(
    schema_path: Path,
    output_path: Path,
    parser: SchemaParser,
) -> None:
    schema_str = schema_path.read_text(encoding="utf-8")
    model = parser.parse(schema_str)

    schema_types = _collect_schema_types(model)
    all_models = [*schema_types.models, model]

    all_imports: set[tuple[str, str]] = set()
    class_blocks: list[tuple[str, list[str]]] = []

    for m in all_models:
        field_lines, imports = _emit_class_block(m)
        all_imports.update(imports)
        class_blocks.append((m.__name__, field_lines))

    # Build import lines
    lines: list[str] = []
    lines.append("# This file was auto-generated by ezconfy. Do not edit manually.")
    for module, name in sorted(all_imports):
        lines.append(f"from {module} import {name}")
    if schema_types.enums:
        lines.append("from enum import Enum")
    lines.append("from pydantic import BaseModel, Field")

    for enum_type in schema_types.enums:
        lines.append("")
        lines.append("")
        lines.extend(_emit_enum_block(enum_type))

    # Build class blocks
    for class_name, field_lines in class_blocks:
        lines.append("")
        lines.append("")
        lines.append(f"class {class_name}(BaseModel):")
        lines.extend(field_lines)

    generated_code = "\n".join(lines) + "\n"
    output_path.write_text(generated_code, encoding="utf-8")
    logger.info(f"Code generated successfully at {output_path}")


@app.command()
def generate(
    schema_path: Path = typer.Argument(..., help="Path to the YAML/JSON schema file."),
    output_path: Path = typer.Option(Path("generated.py"), "--output", "-o", help="Target output file."),
) -> None:
    if not schema_path.exists():
        logger.error(f"File not found: {schema_path}")
        raise typer.Exit(1)
    try:
        run_generation(schema_path, output_path, SchemaParser())
    except Exception as e:
        logger.error(f"Generation failed: {e}")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
