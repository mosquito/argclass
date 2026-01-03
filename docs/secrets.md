# Secrets

argclass provides built-in support for handling sensitive values securely.

## Secret Arguments

Use `argclass.Secret()` to mark sensitive arguments:

<!--- name: test_secrets_basic --->
```python
import argclass

class Parser(argclass.Parser):
    username: str
    password: str = argclass.Secret(help="Database password")
    api_key: str = argclass.Secret()

parser = Parser()
parser.parse_args(["--username", "admin", "--password", "secret123", "--api-key", "key456"])

assert parser.username == "admin"
assert str(parser.password) == "secret123"
assert str(parser.api_key) == "key456"
```

Or use the `secret=True` parameter:

<!--- name: test_secrets_param --->
```python
import argclass

class Parser(argclass.Parser):
    password: str = argclass.Argument(
        secret=True,
        help="Database password"
    )

parser = Parser()
parser.parse_args(["--password", "supersecret"])

assert str(parser.password) == "supersecret"
```

## SecretString Type

Secret string values are wrapped in `SecretString`:

<!--- name: test_secrets_string_type --->
```python
import argclass
from argclass import SecretString

class Parser(argclass.Parser):
    password: str = argclass.Secret()

parser = Parser()
parser.parse_args(["--password", "supersecret"])

# Value is wrapped
assert isinstance(parser.password, SecretString)
assert repr(parser.password) == "'******'"
assert str(parser.password) == "supersecret"
```

## Preventing Accidental Logging

`SecretString` prevents accidental exposure when used with logging:

<!--- name: test_secrets_logging --->
```python
from argclass import SecretString

password = SecretString("supersecret")

# repr always shows masked value
assert repr(password) == "'******'"

# Use !r in f-strings for safe output
assert f"{password!r}" == "'******'"

# str() returns the actual value - use with caution
actual = str(password)
assert actual == "supersecret"
```

## Secrets from Environment

Combine secrets with environment variables:

<!--- name: test_secrets_env --->
```python
import os
import argclass

os.environ["DB_PASSWORD"] = "secret_db_pass"
os.environ["API_KEY"] = "key123"

class Parser(argclass.Parser):
    db_password: str = argclass.Secret(
        env_var="DB_PASSWORD",
        help="Database password"
    )
    api_key: str = argclass.Secret(
        env_var="API_KEY",
        help="API authentication key"
    )

parser = Parser()
parser.parse_args([])

assert str(parser.db_password) == "secret_db_pass"
assert str(parser.api_key) == "key123"

# Clean up environment after parsing
parser.sanitize_env()

assert "DB_PASSWORD" not in os.environ
assert "API_KEY" not in os.environ
```

## Secrets from Config Files

Secrets can also come from config files (use with caution):

<!--- name: test_secrets_config --->
```python
import argclass
from pathlib import Path
from tempfile import NamedTemporaryFile

class DatabaseGroup(argclass.Group):
    host: str = "localhost"
    password: str = argclass.Secret()

class Parser(argclass.Parser):
    api_key: str = argclass.Secret()
    database = DatabaseGroup()

# Create config file
with NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
    f.write("[DEFAULT]\n")
    f.write("api_key = your-secret-key\n\n")
    f.write("[database]\n")
    f.write("password = db-password\n")
    config_path = f.name

parser = Parser(config_files=[config_path])
parser.parse_args([])

assert str(parser.api_key) == "your-secret-key"
assert str(parser.database.password) == "db-password"

Path(config_path).unlink()
```

## Secret Groups

Group related secrets:

<!--- name: test_secrets_groups --->
```python
import argclass

class CredentialsGroup(argclass.Group):
    username: str
    password: str = argclass.Secret()
    token: str = argclass.Secret()

class Parser(argclass.Parser):
    credentials = CredentialsGroup()

parser = Parser()
parser.parse_args([
    "--credentials-username", "admin",
    "--credentials-password", "secret123",
    "--credentials-token", "token456"
])

assert parser.credentials.username == "admin"
assert str(parser.credentials.password) == "secret123"
assert str(parser.credentials.token) == "token456"
```

## Comparison Methods

`SecretString` supports comparison without exposing values:

<!--- name: test_secrets_comparison --->
```python
from argclass import SecretString

secret1 = SecretString("password123")
secret2 = SecretString("password123")
secret3 = SecretString("different")

# Comparisons work
assert secret1 == secret2
assert secret1 != secret3
assert secret1 == "password123"

# repr is always safe
assert repr(secret1) == "'******'"
```

## Best Practices

### 1. Use Environment Variables

Prefer environment variables over config files for secrets:

<!--- name: test_secrets_best_env --->
```python
import os
import argclass

os.environ["API_KEY"] = "from_environment"

class Parser(argclass.Parser):
    # Good: from environment
    api_key: str = argclass.Secret(env_var="API_KEY")

parser = Parser()
parser.parse_args([])

assert str(parser.api_key) == "from_environment"

del os.environ["API_KEY"]
```

### 2. Sanitize After Parsing

Remove secrets from the environment:

<!--- name: test_secrets_sanitize --->
```python
import os
import argclass

os.environ["SECRET_VALUE"] = "sensitive"

class Parser(argclass.Parser):
    secret: str = argclass.Secret(env_var="SECRET_VALUE")

parser = Parser()
parser.parse_args([])

assert "SECRET_VALUE" in os.environ
parser.sanitize_env()  # Removes secret env vars
assert "SECRET_VALUE" not in os.environ
```

### 3. Use repr for Safe Logging

Always use `!r` in f-strings for safe output:

<!--- name: test_secrets_logging_safe --->
```python
import argclass

class Parser(argclass.Parser):
    password: str = argclass.Secret()

parser = Parser()
parser.parse_args(["--password", "supersecret"])

# Safe - use !r format specifier
safe_output = f"Password: {parser.password!r}"
assert "supersecret" not in safe_output
assert "******" in safe_output
```
