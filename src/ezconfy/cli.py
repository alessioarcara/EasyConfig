from pathlib import Path

import typer
from loguru import logger

from ezconfy.codegen import run_generation
from ezconfy.core.schema_parser import SchemaParser

app = typer.Typer()


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
