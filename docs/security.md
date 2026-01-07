# Security Checklist

This page provides security best practices for handling secrets and sensitive
data in CLI applications built with argclass.

## Quick Checklist

- [ ] Use `argclass.Secret()` for sensitive arguments
- [ ] Sanitize secrets after parsing (use `parse_args(sanitize_secrets=True)` or call `parser.sanitize_env()`)
- [ ] Use `{secret!r}` in f-strings (never `{secret}`)
- [ ] Prefer environment variables over config files for secrets
- [ ] If using config files for secrets, verify `chmod 600` permissions
- [ ] Use `logging.info("value: %s", secret)` (not f-strings) for safe logging
- [ ] Never pass secrets via command-line arguments in production

## Threat Model

### What `sanitize_env()` Protects Against

`sanitize_env()` **only** prevents accidental secret leakage via environment
variable inheritance to child processes. It removes environment variables from
the current process after parsing, so that subprocesses spawned afterward do not
inherit them.

There are two ways to sanitize:

- `parse_args(sanitize_secrets=True)` - automatically removes only secret env vars during parsing
- `sanitize_env()` - removes all used env vars after parsing
- `sanitize_env(only_secrets=True)` - removes only secret env vars after parsing

| Protected | Not Protected |
|-----------|---------------|
| Environment variable inheritance to child processes | Secrets in process memory |
| Accidental leakage to trusted tools | Exfiltration by malicious code |
| Defense-in-depth for well-behaved subprocesses | Command-line argument visibility (`ps`, `/proc`) |
| | Secrets in config files, logs, crash dumps |
| | Network-based exfiltration |
| | Filesystem access by child processes |

### What `sanitize_env()` Does NOT Do

:::{danger}
**`sanitize_env()` is NOT a sandbox.**

It does not prevent malicious or compromised code from accessing secrets.
Any code running in your process can read memory, inspect stack frames,
or extract secrets before sanitization occurs. Do not run untrusted code.
:::

If you need to run untrusted code, use proper isolation:

- **Containers** (Docker, Podman) with restricted capabilities
- **Virtual machines** for complete isolation
- **OS-level sandboxing** (seccomp, AppArmor, SELinux)
- **Separate user accounts** with minimal privileges

These are outside the scope of argclass.

---

## Preventing Environment Leakage to Child Processes

### The Problem: Environment Variable Inheritance

When your application spawns subprocesses, runs shell commands, or calls
external tools, those processes inherit a copy of ALL environment variables—
including your secrets.

**Leakage scenario:**

```
1. Your app reads DB_PASSWORD from environment
2. Your app calls subprocess.run(["backup-tool", ...])
3. backup-tool inherits DB_PASSWORD in its environment
4. Secret is exposed (intentionally or via logging/crash dumps)
```

### Solution: Sanitize Environment for Trusted Subprocesses

This pattern is for cases where you run **trusted** subprocesses but want
to prevent accidental secret inheritance:

<!--- name: test_security_sanitize --->
```python
import os
import subprocess
import argclass

os.environ["DB_PASSWORD"] = "secret123"
os.environ["API_KEY"] = "key456"

class Parser(argclass.Parser):
    db_password: str = argclass.Secret(env_var="DB_PASSWORD")
    api_key: str = argclass.Secret(env_var="API_KEY")

parser = Parser()
parser.parse_args([])

# Secrets are parsed and stored in parser
assert str(parser.db_password) == "secret123"

# BEFORE sanitizing: subprocess inherits the secret
leaked = subprocess.check_output(
    "echo $DB_PASSWORD", shell=True, text=True
).strip()
assert leaked == "secret123"  # Secret visible to child process

# Sanitize environment
parser.sanitize_env()

# AFTER sanitizing: subprocess cannot see the secret via env
clean_output = subprocess.check_output(
    "echo $DB_PASSWORD", shell=True, text=True
).strip()
assert clean_output == ""  # Environment variable removed

# Your application still has access to the parsed value
assert str(parser.db_password) == "secret123"
```

### Recommended Flow

```python
import argclass
import subprocess

class Parser(argclass.Parser):
    api_key: str = argclass.Secret(env_var="API_KEY")
    database_url: str = argclass.Secret(env_var="DATABASE_URL")

def main():
    # Step 1: Parse arguments and sanitize secrets in one call
    parser = Parser()
    parser.parse_args(sanitize_secrets=True)

    # Step 2: Extract secrets into local variables if needed
    api_key = str(parser.api_key)
    db_url = str(parser.database_url)

    # Step 3: Use secrets in your application
    connect_to_db(db_url)

    # Step 4: Spawn trusted subprocesses (they won't inherit secrets)
    subprocess.run(["backup-tool", "--compress"])

if __name__ == "__main__":
    main()
```

Alternatively, sanitize manually after parsing:

```python
def main():
    parser = Parser()
    parser.parse_args()

    # Sanitize only secrets, keep other env vars
    parser.sanitize_env(only_secrets=True)

    # Or sanitize all used env vars
    # parser.sanitize_env()

    subprocess.run(["backup-tool", "--compress"])
```

## Other Secret Leakage Channels

Even with `sanitize_env()`, secrets can leak through other channels:

### Command-Line Arguments

Secrets in command-line arguments are visible to all users via `ps`:

```console
# Anyone on the system can see this:
$ ps aux | grep python
user  1234  python app.py --password=supersecret
```

**Mitigation:** Never pass secrets via command-line arguments. Use environment
variables or config files with restricted permissions.

### Log Files

Secrets can be accidentally logged when using f-strings:

```python
import logging
import argclass

api_key = argclass.SecretString("LEAK ME")

# WRONG: F-string evaluates str() before logging
logging.info(f"Connecting with key: {api_key}")

# RIGHT: %-formatting lets logging call repr()
logging.info("Connecting with key: %s", api_key)
```

**Mitigation:** Use `logging.info("msg: %s", secret)` instead of f-strings.
The logging module calls `repr()` on SecretString, which returns `'******'`.

### Config Files

Config files persist on disk and may be readable by other users:

```console
# Check permissions
$ ls -la config.ini
-rw-r--r-- 1 user user ... config.ini  # WRONG: world-readable
```

**Mitigation:** Use `chmod 600` for config files containing secrets. Prefer
environment variables for secrets.

### Crash Dumps and Core Files

Secrets in memory may appear in crash dumps:

```console
# Core dumps may contain secrets
$ ulimit -c unlimited  # Enables core dumps
```

**Mitigation:** Disable core dumps in production (`ulimit -c 0`), or ensure
core dump directories have restricted permissions.

### Process Memory

Any code running in your process can inspect memory:

```python
import argclass
import os

class Parser(argclass.Parser):
    api_key: str = argclass.Secret(env_var="API_KEY")

os.environ["API_KEY"] = "supersecret"

parser = Parser()
parser.parse_args([])
    
# Malicious code can extract secrets from parser object
secret_value = str(parser.api_key)
```

**Mitigation:** Do not run untrusted code. There is no library-level protection
against code running in the same process.

---

## SecretString Guarantees

### What SecretString Protects Against

| Scenario | Protected? | Details |
|----------|------------|---------|
| `repr(secret)` | Yes | Returns `'******'` |
| `f"{secret!r}"` | Yes | Uses repr, shows `'******'` |
| `log.info("x: %s", secret)` | Yes | Logging uses repr, shows `'******'` |
| `print(secret)` | **No** | Uses str, shows actual value |
| `f"{secret}"` | **No** | Uses str, shows actual value |
| `log.info(f"x: {secret}")` | **No** | F-string uses str before logging |
| `str(secret)` | **No** | Returns actual value (intended) |

### Safe Logging

<!--- name: test_security_logging_safe --->
```python
import argclass
import logging

class Parser(argclass.Parser):
    password: str = argclass.Secret()

parser = Parser()
parser.parse_args(["--password", "supersecret"])


log_output = ""

# Add a custom logging handler to capture log output for 
# this example will demonstrate safe logging practices.
class LogCaptureHandler(logging.Handler):
    def emit(self, record):
        global log_output
        log_output += self.format(record) + "\n"

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(LogCaptureHandler())


# SAFE - logging with %s uses repr()
logging.info("Password: %s", parser.password)

assert "supersecret" not in log_output

# SAFE - f-string with !r also works
safe_fstring = f"Password: {parser.password!r}"
assert "supersecret" not in safe_fstring
assert "******" in safe_fstring

# UNSAFE - f-string without !r exposes the secret
assert f"Password: {parser.password}" == "Password: supersecret"
```

**Recommended logging pattern:**

```python
import logging
from argclass import SecretString

secret = SecretString("api_key_value")

# SAFE: Use %-formatting, logging calls repr() on SecretString
# logging.info("Connecting with API key: %s", secret)  # Shows '******'
```

### Comparison Without Exposure

SecretString supports equality comparison without exposing the value:

<!--- name: test_security_comparison --->
```python
from argclass import SecretString

secret1 = SecretString("password123")
secret2 = SecretString("password123")

# Comparisons work without exposing values
assert secret1 == secret2
assert secret1 == "password123"

# repr never exposes the value
assert repr(secret1) == "'******'"
```

## Config File Security

### File Permissions

If you choose to store secrets in config files, you **must** verify file permissions:

```console
# Restrict permissions (Unix/Linux/macOS)
chmod 600 /path/to/config.ini

# Owner can read/write, no one else
# -rw------- 1 user user ... config.ini
```

### Prefer Environment Variables

Environment variables are often more secure than config files because:

- Config files can be accidentally committed to version control
- Config files persist on disk and can be read by other users
- Environment variables are process-scoped and not persisted

```python
# Store secrets in environment, not in config.ini
os.environ["API_KEY"] = "your_secret"  # Set by deployment system
```

Here is the recommended pattern:

<!--- name: test_security_env_over_config --->
```python
import os
import argclass

# RECOMMENDED: Use environment variables for secrets
os.environ["API_KEY"] = "secret_from_env"

class Parser(argclass.Parser):
    # Secret from environment - not stored in files
    api_key: str = argclass.Secret(env_var="API_KEY")

    # Non-secrets can come from config
    log_level: str = "info"
    max_retries: int = 3

parser = Parser(config_files=["config.ini"])  # Config for non-secrets only
parser.parse_args([])
parser.sanitize_env()  # Removes API_KEY from environment
```

---

## Passing Secrets to Subprocesses

### Passing Secrets via Command Line is Insecure

Not passing secrets via command-line arguments is critical, as they are
visible to all users on the system:

```python
import subprocess

# WRONG - secret visible in process listing
subprocess.check_output(
    ["ps aux | grep python | grep --password"],
    shell=True,
    text=True,
)
```

## Common Mistakes

### Don't Do This

Notice the mistakes in this example:

```python
import os
import argclass
import logging
import subprocess


class Parser(argclass.Parser):
    api_key: str = argclass.Secret(env_var="API_KEY")


os.environ["API_KEY"] = "supersecret"

parser = Parser()
parser.parse_args([])

# WRONG: F-string logs the actual secret
print(f"Using API key: {parser.api_key}")

# WRONG: Includes secret in exception
raise ValueError(f"Invalid key: {parser.api_key}")

# WRONG: Forgets to sanitize before subprocess
print(subprocess.check_output("echo $API_KEY", shell=True, text=True).strip())
```

### Do This Instead

```python
import argclass
import logging
import subprocess

class Parser(argclass.Parser):
    api_key: str = argclass.Secret(env_var="API_KEY")

parser = Parser()
parser.parse_args([])

# IMMEDIATELY sanitize
parser.sanitize_env()

# RIGHT: %-formatting uses repr() - shows '******'
logging.info("Using API key: %s", parser.api_key)

# RIGHT: Just indicate presence
print("API key configured: Yes")

# RIGHT: Don't include secret in errors
raise ValueError("Invalid API key provided")

# RIGHT: Environment sanitized before subprocess
subprocess.run(["some-tool"])
```

## FAQ

### If I sanitize env, can I safely run third-party scripts?

**No.** Sanitizing environment variables only removes secrets from the
environment that child processes inherit. It does not make it safe to run
untrusted or third-party code.

Untrusted code running in your process (before or after sanitization) can:

- Read secrets from the parser object or local variables
- Inspect process memory or stack frames
- Access secrets before `sanitize_env()` is called
- Read secrets from config files on disk
- Intercept secrets passed to functions

If you need to run untrusted code, you must use proper isolation mechanisms
(containers, VMs, separate user accounts) that are outside the scope of this
library. `sanitize_env()` is a defense-in-depth measure for preventing
accidental leakage to well-behaved, trusted subprocesses—not a security
boundary against malicious code.
