import ast
import operator as op_module
import re
from graphlib import CycleError, TopologicalSorter
from typing import Any, Callable, get_args, get_origin

from pydantic import BaseModel, ConfigDict, TypeAdapter

from ezconfy.core.exceptions import InstantiationError
from ezconfy.core.module_loader import ModuleLoader

# Matches strings like "${...}" and captures the content inside the braces for further processing.
PLACEHOLDER_PATTERN = re.compile(r"\$\{([^}]+)\}")
# Matches simple paths like "A", "A.num_classes", "A.method()", etc., which can be resolved directly.
_SIMPLE_PATH_RE = re.compile(r"^[\w\.\(\)]+$")

_BINARY_OPS: dict[type, Callable[[Any, Any], Any]] = {
    ast.Add: op_module.add,
    ast.Sub: op_module.sub,
    ast.Mult: op_module.mul,
    ast.Div: op_module.truediv,
    ast.FloorDiv: op_module.floordiv,
    ast.Mod: op_module.mod,
    ast.Pow: op_module.pow,
}

_UNARY_OPS: dict[type, Callable[[Any], Any]] = {
    ast.USub: op_module.neg,
    ast.UAdd: op_module.pos,
}


class Instantiator:
    def __init__(self, module_loader: ModuleLoader | None = None) -> None:
        self._loader = module_loader if module_loader is not None else ModuleLoader()

    def __call__(self, config: dict[str, Any], schema_model: type[BaseModel] | None = None) -> dict[str, Any]:
        dep_graph = self._build_dependency_graph(config)
        return self._instantiate_topologically(config, dep_graph, schema_model=schema_model)

    def _build_dependency_graph(self, config: dict[str, Any]) -> dict[str, set[str]]:
        graph = {}
        nodes = set(config.keys())
        for name, node in config.items():
            deps = {p.split(".")[0] for p in self._find_placeholders(node)}
            missing = deps - nodes
            if missing:
                raise InstantiationError(
                    f"Config key '{name}' references undefined keys {missing}. Available keys: {list(nodes)}"
                )
            graph[name] = deps
        return graph

    def _find_placeholders(self, node: Any) -> set[str]:
        if isinstance(node, str):
            m = PLACEHOLDER_PATTERN.fullmatch(node)
            if not m:
                return set()
            content = m.group(1).strip()
            if _SIMPLE_PATH_RE.match(content):
                return {content}
            return self._extract_expr_deps(content)

        if isinstance(node, dict):
            return {dep for v in node.values() for dep in self._find_placeholders(v)}

        if isinstance(node, list):
            return {dep for item in node for dep in self._find_placeholders(item)}

        return set()

    def _extract_expr_deps(self, expr: str) -> set[str]:
        try:
            tree = ast.parse(expr, mode="eval")
        except SyntaxError as e:
            raise InstantiationError(f"Invalid expression '${{{expr}}}': {e}") from e
        return {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}

    def _resolve_path(self, path: str, resolved_config: dict[str, Any]) -> Any:
        """
        Example:

            config = {
                ...
                "A": Dataset,
                "B": {
                    "value": "{A.num_classes}"
                }
            }

            Resolving "{A.num_classes}":

            Path:
                "A.num_classes" -> ["A", "num_classes"]

            Steps:
                current = resolved_config["A"]      -> Dataset
                current = getattr(current, "num_classes") -> 10

            Result:
                10
        """

        def _obj_repr(obj: Any) -> str:
            if isinstance(obj, dict):
                return f"dict with keys {list(obj.keys())}"
            return type(obj).__name__

        def _get_attr(obj: Any, name: str) -> Any:
            if isinstance(obj, dict):
                if name in obj:
                    return obj[name]
                raise InstantiationError(f"Key '{name}' not found in {_obj_repr(obj)}")
            if hasattr(obj, name):
                return getattr(obj, name)
            raise InstantiationError(f"Cannot resolve '{name}' on {_obj_repr(obj)}")

        parts = path.split(".")
        try:
            current = resolved_config[parts[0]]
        except KeyError:
            raise InstantiationError(
                f"Placeholder '${{{path}}}' references unknown key '{parts[0]}'. "
                f"Available keys: {list(resolved_config.keys())}"
            )

        for part in parts[1:]:
            is_method = part.endswith("()")
            name = part[:-2] if is_method else part
            current = _get_attr(current, name)
            if is_method:
                if not callable(current):
                    raise InstantiationError(f"'{name}' is not callable on {current}")
                current = current()

        return current

    def _attr_to_path(self, node: ast.Attribute) -> str:
        parts: list[str] = []
        current: ast.expr = node
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
        return ".".join(reversed(parts))

    def _eval_node(self, node: ast.expr, expr: str, resolved_config: dict[str, Any]) -> Any:
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            return self._resolve_path(node.id, resolved_config)
        if isinstance(node, ast.Attribute):
            return self._resolve_path(self._attr_to_path(node), resolved_config)
        if isinstance(node, ast.BinOp):
            left = self._eval_node(node.left, expr, resolved_config)
            right = self._eval_node(node.right, expr, resolved_config)
            op_func = _BINARY_OPS.get(type(node.op))
            if op_func is None:
                raise InstantiationError(f"Unsupported operator in '${{{expr}}}'")
            return op_func(left, right)
        if isinstance(node, ast.UnaryOp):
            operand = self._eval_node(node.operand, expr, resolved_config)
            unary_op_func = _UNARY_OPS.get(type(node.op))
            if unary_op_func is None:
                raise InstantiationError(f"Unsupported operator in '${{{expr}}}'")
            return unary_op_func(operand)
        raise InstantiationError(f"Unsupported operation '{type(node).__name__}' in '${{{expr}}}'")

    def _evaluate_expression(self, expr: str, resolved_config: dict[str, Any]) -> Any:
        try:
            tree = ast.parse(expr, mode="eval")
        except SyntaxError as e:
            raise InstantiationError(f"Invalid expression '${{{expr}}}': {e}") from e
        return self._eval_node(tree.body, expr, resolved_config)

    def _instantiate_obj(self, node: Any, resolved_config: dict[str, Any], schema_type: Any = None) -> Any:
        if isinstance(node, str) and (m := PLACEHOLDER_PATTERN.fullmatch(node)):
            content = m.group(1).strip()
            if _SIMPLE_PATH_RE.match(content):
                result = self._resolve_path(content, resolved_config)
            else:
                result = self._evaluate_expression(content, resolved_config)
            return self._try_cast(result, schema_type)

        if isinstance(node, dict):
            if "_target_type_" in node:
                target = node["_target_type_"]
                cls: Any = self._loader.load_class(target)
                arg_types = self._get_model_field_types(schema_type)
                resolved_args = {
                    k: self._instantiate_obj(v, resolved_config, schema_type=arg_types.get(k))
                    for k, v in node.get("_init_args_", {}).items()
                }
                init_method_name = node.get("_init_method_")
                if init_method_name:
                    factory = getattr(cls, init_method_name)
                    if not callable(factory):
                        raise InstantiationError(f"'{init_method_name}' is not callable on {cls}")
                    error_context = f"'{target}' via '{init_method_name}'"
                else:
                    factory = cls
                    error_context = f"'{target}'"
                try:
                    return factory(**resolved_args)
                except Exception as e:
                    raise InstantiationError(f"Failed to instantiate {error_context}: {e}") from e

            field_types = self._get_model_field_types(schema_type)
            return {
                k: self._instantiate_obj(v, resolved_config, schema_type=field_types.get(k)) for k, v in node.items()
            }

        if isinstance(node, list):
            elem_type = self._get_list_element_type(schema_type)
            return [self._instantiate_obj(i, resolved_config, schema_type=elem_type) for i in node]

        return self._try_cast(node, schema_type)

    def _instantiate_topologically(
        self, config: dict[str, Any], graph: dict[str, set[str]], schema_model: type[BaseModel] | None = None
    ) -> dict[str, Any]:
        try:
            order = list(TopologicalSorter(graph).static_order())
        except CycleError as e:
            raise InstantiationError(f"Circular reference detected in configuration: {e}") from e

        top_level_types = self._get_model_field_types(schema_model)
        resolved_config: dict[str, Any] = {}
        for key in order:
            try:
                resolved_config[key] = self._instantiate_obj(
                    config[key], resolved_config, schema_type=top_level_types.get(key)
                )
            except InstantiationError:
                raise
            except Exception as e:
                raise InstantiationError(f"Unexpected error while processing config key '{key}': {e}") from e

        return resolved_config

    @staticmethod
    def _try_cast(value: Any, schema_type: Any) -> Any:
        if schema_type is None:
            return value
        try:
            adapter = TypeAdapter(schema_type, config=ConfigDict(arbitrary_types_allowed=True))
            return adapter.validate_python(value)
        except Exception:
            return value

    @staticmethod
    def _get_model_field_types(schema_type: Any) -> dict[str, Any]:
        """
        Given a Pydantic BaseModel, it returns a dict mapping field names to their annotated types.
        This lets the instantiator know the expected type of each field, which can be used for type casting.
        """
        if schema_type is not None and isinstance(schema_type, type) and issubclass(schema_type, BaseModel):
            return {name: info.annotation for name, info in schema_type.model_fields.items()}
        return {}

    @staticmethod
    def _get_list_element_type(schema_type: Any) -> Any:
        if schema_type is not None and get_origin(schema_type) is list:
            args = get_args(schema_type)
            if args:
                return args[0]
        return None
