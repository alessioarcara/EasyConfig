from pathlib import Path

from loguru import logger

from ezconfy.codegen.emitter import render
from ezconfy.codegen.extractors import EnumExtractor, ModelExtractor
from ezconfy.codegen.walker import walk_schema
from ezconfy.core.schema_parser import SchemaParser


def run_generation(
    schema_path: Path,
    output_path: Path,
    parser: SchemaParser,
) -> None:
    schema_str = schema_path.read_text(encoding="utf-8")
    model = parser.parse(schema_str)

    extractors = [EnumExtractor(), ModelExtractor()]
    walk_schema(model, extractors)

    all_body: list[str] = []
    all_imports: set[tuple[str, str]] = set()
    for ext in extractors:
        body, imports = ext.emit()
        all_body.extend(body)
        all_imports.update(imports)

    output_path.write_text(render(all_body, all_imports), encoding="utf-8")
    logger.info(f"Code generated successfully at {output_path}")
