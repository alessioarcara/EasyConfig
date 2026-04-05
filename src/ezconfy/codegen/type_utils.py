import sys
from enum import Enum
from pathlib import Path
from types import UnionType
from typing import Any, TypeGuard, Union, get_args, get_origin

from pydantic import BaseModel


def is_union(t: object) -> bool:
    # Handles both `Union[A, B]` (typing) and `A | B` (PEP 604 / UnionType)
    return get_origin(t) is Union or isinstance(t, UnionType)


def is_pydantic_model(annotation: Any) -> TypeGuard[type[BaseModel]]:
    return isinstance(annotation, type) and issubclass(annotation, BaseModel) and annotation is not BaseModel


def is_enum(annotation: Any) -> TypeGuard[type[Enum]]:
    return isinstance(annotation, type) and issubclass(annotation, Enum)


def is_builtin(annotation: Any) -> bool:
    return getattr(annotation, "__module__", None) == "builtins"


def is_dynamic(annotation: Any) -> bool:
    module_name = getattr(annotation, "__module__", "")
    return module_name.startswith("_dynamic_")


def _resolve_args(args: tuple[Any, ...]) -> tuple[list[str], set[tuple[str, str]]]:
    resolved: list[str] = []
    imports: set[tuple[str, str]] = set()
    for arg in args:
        arg_str, arg_imports = resolve_type(arg)
        resolved.append(arg_str)
        imports.update(arg_imports)
    return resolved, imports


def _resolve_dynamic_import(module_name: str, type_name: str) -> tuple[str, str] | None:
    module = sys.modules.get(module_name)
    if module is None:
        return None
    file = getattr(module, "__file__", None)
    if file is None:
        return None
    return (Path(file).resolve().stem, type_name)


def resolve_type(annotation: type[Any]) -> tuple[str, set[tuple[str, str]]]:
    origin = get_origin(annotation)

    if origin is not None:
        args = get_args(annotation)
        if is_union(annotation):
            non_none_args = tuple(a for a in args if a is not type(None))
            resolved, nested_imports = _resolve_args(non_none_args)
            type_str = " | ".join(resolved)
            if type(None) in args:
                type_str += " | None"
        else:
            resolved, nested_imports = _resolve_args(args)
            origin_name = getattr(origin, "__name__", str(origin))
            type_str = f"{origin_name}[{', '.join(resolved)}]"
        return type_str, nested_imports

    type_name = getattr(annotation, "__name__", None)
    if type_name is None:
        raise TypeError(
            f"Cannot resolve type name for {annotation!r}. "
            "Ensure all forward references are resolved before code generation."
        )

    imports: set[tuple[str, str]] = set()
    if not (is_pydantic_model(annotation) or is_enum(annotation) or is_builtin(annotation)):
        module_name = annotation.__module__
        if is_dynamic(annotation):
            import_tuple = _resolve_dynamic_import(module_name, type_name)
            if import_tuple is not None:
                imports.add(import_tuple)
        else:
            imports.add((module_name, type_name))
    return type_name, imports
