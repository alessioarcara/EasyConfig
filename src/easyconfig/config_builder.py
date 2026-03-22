from typing import Any, Optional, cast

import yaml
from pydantic import BaseModel, ValidationError

from easyconfig.instantiator import Instantiator
from easyconfig.parser import SchemaParser


class ConfigBuilder:
    def __init__(self, schema_yaml: Optional[str] = None) -> None:
        self.instantiator = Instantiator()
        self.schema_model: Optional[type[BaseModel]] = None

        if schema_yaml:
            parser = SchemaParser()
            self.schema_model = parser.parse(schema_yaml)

    def build(self, config_yaml: str) -> BaseModel | dict[str, Any]:
        raw_data = yaml.safe_load(config_yaml) or {}

        instantiated = self.instantiator(yaml.dump(raw_data))

        if self.schema_model is None:
            return cast(dict[str, Any], instantiated)

        try:
            validated_data = self.schema_model(**instantiated)
        except ValidationError as e:
            raise ValueError(f"Schema validation error: {e}") from e

        return validated_data
