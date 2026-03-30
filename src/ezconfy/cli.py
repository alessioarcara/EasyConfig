from pathlib import Path
from types import UnionType
from typing import Any, Union, get_args, get_origin

import typer
from loguru import logger

from ezconfy.schema_parser import SchemaParser

app = typer.Typer()


def _is_union(t: object) -> bool:
    origin = get_origin(t)
    return origin is Union or isinstance(t, UnionType)


def resolve_type(annotation: type[Any]) -> tuple[str, set[tuple[str, str]]]:
    origin = get_origin(annotation)
    if origin is not None:
        args = get_args(annotation)
        all_imports: set[tuple[str, str]] = set()

        if _is_union(annotation):
            non_none_args = [a for a in args if a is not type(None)]
            has_none = type(None) in args
            resolved = []
            for arg in non_none_args:
                arg_str, arg_imports = resolve_type(arg)
                resolved.append(arg_str)
                all_imports.update(arg_imports)
            result = " | ".join(resolved)
            if has_none:
                result += " | None"
            return (result, all_imports)

        resolved = []
        for arg in args:
            arg_str, arg_imports = resolve_type(arg)
            resolved.append(arg_str)
            all_imports.update(arg_imports)

        origin_name = getattr(origin, "__name__", str(origin))
        result = f"{origin_name}[{', '.join(resolved)}]"
        return (result, all_imports)

    if annotation.__module__ == "builtins":
        return (annotation.__name__, set())

    return (annotation.__name__, {(annotation.__module__, annotation.__name__)})


def run_generation(
    schema_path: Path,
    output_path: Path,
    parser: SchemaParser,
) -> None:
    schema_str = schema_path.read_text(encoding="utf-8")
    model = parser.parse(schema_str)

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

    if not model.model_fields:
        field_lines.append("    pass")

    # Build import lines
    lines: list[str] = []
    for module, name in sorted(all_imports):
        lines.append(f"from {module} import {name}")

    lines.append("from pydantic import BaseModel, Field")
    lines.append("")
    lines.append("")
    lines.append(f"class {model.__name__}(BaseModel):")
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
