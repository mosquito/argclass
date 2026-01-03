# Changelog

All notable changes to argclass are documented here.

## [1.2.0] - 2024

### Added

- `ArgumentSingle` and `ArgumentSequence` for precise type inference
- Type overloads for `Argument()` with proper `nargs` handling
- `EnumArgument` with `use_value` and `lowercase` options
- Container type support (`list[T]`, `set[T]`, `frozenset[T]`)
- PEP 604 union type support (`X | None`)
- PEP 649 (Python 3.14) compatibility for deferred annotation evaluation
- Secret leakage prevention in help output
- Sphinx documentation with Furo theme

### Changed

- Split `__init__.py` into submodules for better organization
- `LogLevel` now uses `EnumArgument` internally
- Improved type hints throughout

### Fixed

- Subparser attribute isolation
- Nested subparser chain building
- `Secret()` with type annotation

## [1.1.0] - 2023

### Added

- Subparser support with `__parent__` access
- `current_subparsers` property
- Config file search paths

### Changed

- Improved error messages

## [1.0.0] - 2023

### Added

- Initial stable release
- `Parser` and `Group` classes
- `Argument`, `Secret`, `Config` functions
- INI and JSON config file support
- Environment variable support
- `SecretString` for safe secret handling
- Boolean parsing utilities

## Version History

| Version | Python Support | Status |
|---------|---------------|--------|
| 1.2.x | 3.10 - 3.14 | Current |
| 1.1.x | 3.8 - 3.12 | Maintenance |
| 1.0.x | 3.8 - 3.11 | End of Life |
