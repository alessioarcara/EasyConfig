import re
from graphlib import CycleError, TopologicalSorter
from typing import Any

from easyconfig.module_loader import ModuleLoader

PLACEHOLDER_PATTERN = re.compile(r"\$\{([\w\.\(\)]+)\}")


class Instantiator:
    def __init__(self) -> None:
        self._loader = ModuleLoader()

    def __call__(self, config: dict[str, Any]) -> dict[str, Any]:
        dep_graph = self._build_dependency_graph(config)
        return self._instantiate_topologically(config, dep_graph)

    def _build_dependency_graph(self, config: dict[str, Any]) -> dict[str, set[str]]:
        graph = {}
        nodes = set(config.keys())
        for name, node in config.items():
            deps = {p.split(".")[0] for p in self._find_placeholders(node)}
            missing = deps - nodes
            if missing:
                raise KeyError(f"Node '{name}' is missing dependencies: {missing}")
            graph[name] = deps
        return graph

    def _find_placeholders(self, node: Any) -> set[str]:
        if isinstance(node, str):
            m = PLACEHOLDER_PATTERN.fullmatch(node)
            return {m.group(1)} if m else set()

        if isinstance(node, dict):
            return {dep for v in node.values() for dep in self._find_placeholders(v)}

        if isinstance(node, list):
            return {dep for item in node for dep in self._find_placeholders(item)}

        return set()

    def _resolve_path(self, path: str, context: dict[str, Any]) -> Any:
        """
        Navigates through a resolved object using dot-notation.
        """
        # Split the path into parts separated by dots
        parts = path.split(".")
        # Start with the top-level variable from the context
        current = context[parts[0]]

        # Iterate through the remaining parts to resolve attributes and method calls
        for part in parts[1:]:
            is_method = part.endswith("()")
            attr = part[:-2] if is_method else part

            # Access dictionary key if current is a dict
            if isinstance(current, dict) and attr in current:
                current = current[attr]
            # Otherwise access as an attribute if it exists
            elif hasattr(current, attr):
                current = getattr(current, attr)
            # Raise an error if neither works
            else:
                raise AttributeError(f"Cannot resolve '{attr}' on {current}")

            # Call the method if this part is a method
            if is_method and callable(current):
                current = current()

        return current

    def _instantiate_obj(self, node: Any, context: dict[str, Any]) -> Any:
        if isinstance(node, str) and (m := PLACEHOLDER_PATTERN.fullmatch(node)):
            return self._resolve_path(m.group(1), context)

        if isinstance(node, dict):
            if "_target_type_" in node:
                cls: Any = self._loader.load_class(node["_target_type_"])
                raw_args = node.get("_init_args_", {})
                resolved_args = {k: self._instantiate_obj(v, context) for k, v in raw_args.items()}
                return cls(**resolved_args)

            return {k: self._instantiate_obj(v, context) for k, v in node.items()}

        if isinstance(node, list):
            return [self._instantiate_obj(i, context) for i in node]

        return node

    def _instantiate_topologically(self, config: dict[str, Any], graph: dict[str, set[str]]) -> dict[str, Any]:
        resolved_context: dict[str, Any] = {}
        sorter = TopologicalSorter(graph)

        try:
            for key in sorter.static_order():
                resolved_context[key] = self._instantiate_obj(config[key], resolved_context)
        except CycleError as e:
            raise ValueError(f"Circular reference detected in configuration: {e}") from e

        return resolved_context
