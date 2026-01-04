# API Reference

Complete API documentation for argclass.

## Core Classes

### Parser

```{eval-rst}
.. autoclass:: argclass.Parser
   :members:
   :show-inheritance:
```

### Group

```{eval-rst}
.. autoclass:: argclass.Group
   :members:
   :show-inheritance:
```

### Base

```{eval-rst}
.. autoclass:: argclass.Base
   :members:
   :show-inheritance:
```

## Factory Functions

### Argument

```{eval-rst}
.. autofunction:: argclass.Argument
```

### ArgumentSingle

```{eval-rst}
.. autofunction:: argclass.ArgumentSingle
```

### ArgumentSequence

```{eval-rst}
.. autofunction:: argclass.ArgumentSequence
```

### Secret

```{eval-rst}
.. autofunction:: argclass.Secret
```

### Config

```{eval-rst}
.. autofunction:: argclass.Config
```

### EnumArgument

```{eval-rst}
.. autofunction:: argclass.EnumArgument
```

## Types and Enums

### Actions

```{eval-rst}
.. autoclass:: argclass.Actions
   :members:
   :undoc-members:
```

### Nargs

```{eval-rst}
.. autoclass:: argclass.Nargs
   :members:
   :undoc-members:
```

### LogLevelEnum

```{eval-rst}
.. autoclass:: argclass.LogLevelEnum
   :members:
   :undoc-members:
```

## Secret Handling

### SecretString

```{eval-rst}
.. autoclass:: argclass.SecretString
   :members:
   :special-members: __str__, __repr__, __eq__
```

## Configuration

### ConfigArgument

```{eval-rst}
.. autoclass:: argclass.ConfigArgument
   :members:
   :show-inheritance:
```

### INIConfig

```{eval-rst}
.. autoclass:: argclass.INIConfig
   :members:
   :show-inheritance:
```

### JSONConfig

```{eval-rst}
.. autoclass:: argclass.JSONConfig
   :members:
   :show-inheritance:
```

### TOMLConfig

:::{note}
Requires `tomllib` (Python 3.11+) or `tomli` package (Python 3.10).
Install `tomli` for Python 3.10: `pip install tomli`
:::

```{eval-rst}
.. autoclass:: argclass.TOMLConfig
   :members:
   :show-inheritance:
```

### ConfigAction

```{eval-rst}
.. autoclass:: argclass.ConfigAction
   :members:
```

## Config File Parsers

These classes parse configuration files to provide default values for arguments.

### AbstractDefaultsParser

```{eval-rst}
.. autoclass:: argclass.AbstractDefaultsParser
   :members:
   :show-inheritance:
```

### INIDefaultsParser

```{eval-rst}
.. autoclass:: argclass.INIDefaultsParser
   :members:
   :show-inheritance:
```

### JSONDefaultsParser

```{eval-rst}
.. autoclass:: argclass.JSONDefaultsParser
   :members:
   :show-inheritance:
```

### TOMLDefaultsParser

:::{note}
Requires `tomllib` (Python 3.11+) or `tomli` package (Python 3.10).
Install `tomli` for Python 3.10: `pip install tomli`
:::

```{eval-rst}
.. autoclass:: argclass.TOMLDefaultsParser
   :members:
   :show-inheritance:
```

## Internal Classes

### TypedArgument

```{eval-rst}
.. autoclass:: argclass.TypedArgument
   :members:
   :show-inheritance:
```

### Store

```{eval-rst}
.. autoclass:: argclass.Store
   :members:
```

## Utility Functions

### parse_bool

```{eval-rst}
.. autofunction:: argclass.parse_bool
```

### read_configs

```{eval-rst}
.. autofunction:: argclass.read_configs
```

## Pre-built Arguments

### LogLevel

A pre-configured argument for log levels:

```python
import argclass
import logging

class Parser(argclass.Parser):
    log_level: int = argclass.LogLevel

parser = Parser()
parser.parse_args(["--log-level", "debug"])
logging.basicConfig(level=parser.log_level)
```

Accepts: `debug`, `info`, `warning`, `error`, `critical` (case-insensitive).
Returns the corresponding `logging` level integer.
