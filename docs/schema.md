# Schema Guide

## Why?

Using a YAML schema lets your configuration be automatically validated with
Pydantic.

This ensures values always match expected types (e.g. no strings where integers
are required), reducing bugs and improving reliability.

It also acts as documentation, making it easy to understand what values exist
and how they are used.

## YAML Structure

A schema can contain two top-level keys:

```yaml
types:
  # type definitions

schema:
  # main configuration
```

If you define `types`, you must also define `schema`.

If `types` is not present, the entire YAML is treated as the root schema.

## Supported types

* **Primitives**: int, float, str, bool
* **Optional**: type?
* **Default values**: type = value
* **Lists**: list[T]
* **Unions**: A | B
* **Nested objects**: via indentation
* **Custom types**: defined in types
* **Enums**: list of values
* **Inheritance**: Child < Parent
* **External types**: e.g. pathlib.Path
