import re
from graphlib import CycleError, TopologicalSorter
from typing import Any

from ezconfy.module_loader import ModuleLoader

PLACEHOLDER_PATTERN = re.compile(r"\$\{([\w\.\(\)]+)\}")


class Instantiator:
    def __init__(self) -> None:
        self._loader = ModuleLoader()

    def __call__(self, config: dict[str, Any]) -> dict[str, Any]:
        dep_graph = self._build_dependency_graph(config)
        return self._instantiate_topologically(config, dep_graph)

    def _build_dependency_graph(self, config: dict[str, Any]) -> dict[str, set[str]]:
        """
        Example:

        config = {
            "A": "value",
            "B": "{A}",
            "C": "{B}.{A}"
        }

        the resulting dependency graph would be:
        {
            "A": set(),
            "B": {"A"},
            "C": {"A", "B"}
        }
        """
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

        def _get_attr(obj: Any, name: str) -> Any:
            if isinstance(obj, dict):
                if name in obj:
                    return obj[name]
                raise AttributeError(f"Key '{name}' not found in dict {obj}")
            if hasattr(obj, name):
                return getattr(obj, name)
            raise AttributeError(f"Cannot resolve '{name}' on {obj}")

        parts = path.split(".")
        current = resolved_config[parts[0]]

        for part in parts[1:]:
            is_method = part.endswith("()")
            name = part[:-2] if is_method else part

            current = _get_attr(current, name)

            if is_method:
                if not callable(current):
                    raise TypeError(f"'{name}' is not callable on {current}")
                current = current()

        return current

    def _instantiate_obj(self, node: Any, resolved_config: dict[str, Any]) -> Any:
        if isinstance(node, str) and (m := PLACEHOLDER_PATTERN.fullmatch(node)):
            return self._resolve_path(m.group(1), resolved_config)

        if isinstance(node, dict):
            if "_target_type_" in node:
                cls: Any = self._loader.load_class(node["_target_type_"])
                raw_args = node.get("_init_args_", {})
                resolved_args = {k: self._instantiate_obj(v, resolved_config) for k, v in raw_args.items()}

                # Determine which method to use for instantiation
                init_method_name = node.get("_init_method_", "__init__")
                if init_method_name == "__init__":
                    return cls(**resolved_args)
                else:
                    init_method = getattr(cls, init_method_name)
                    if not callable(init_method):
                        raise TypeError(f"'{init_method_name}' is not callable on {cls}")
                    return init_method(**resolved_args)

            return {k: self._instantiate_obj(v, resolved_config) for k, v in node.items()}

        if isinstance(node, list):
            return [self._instantiate_obj(i, resolved_config) for i in node]

        return node

    def _instantiate_topologically(self, config: dict[str, Any], graph: dict[str, set[str]]) -> dict[str, Any]:
        resolved_config: dict[str, Any] = {}
        sorter = TopologicalSorter(graph)

        try:
            for key in sorter.static_order():
                resolved_config[key] = self._instantiate_obj(config[key], resolved_config)
        except CycleError as e:
            raise ValueError(f"Circular reference detected in configuration: {e}") from e

        return resolved_config
