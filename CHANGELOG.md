# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.2] - 2025-04-02

### Fixed
- Preserve extra config fields that are not declared in the schema when a schema is provided

## [0.1.1] - 2025-03-XX

### Added
- Improved error messages across the config loading pipeline
- Nested model generation in the code generation CLI
- Specific exceptions for `SchemaParser` (`SchemaParserError`) and `Instantiator` (`InstantiatorError`)

## [0.1.0] - 2025-03-XX

### Added
- Initial release
- YAML schema parsing into Pydantic models with support for primitives, optionals, defaults, lists, unions, enums, and inheritance
- Dynamic object instantiation via `_target_type_` and `_init_method_` directives
- Placeholder injection with `${key}` syntax supporting attribute access and method calls
- Multi-file deep-merge configuration loading
- Programmatic overrides via dictionary
- Code generation CLI (`ezconfy generate`) to produce standalone Pydantic model files
- External type support (`module:ClassName` and file path syntax)
- Topological ordering for resolving object instantiation dependencies

[Unreleased]: https://github.com/alessioarcara/EasyConfig/compare/v0.1.2...HEAD
[0.1.2]: https://github.com/alessioarcara/EasyConfig/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/alessioarcara/EasyConfig/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/alessioarcara/EasyConfig/releases/tag/v0.1.0
