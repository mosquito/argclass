import argparse
import inspect
import os
import sys
import textwrap
from enum import Enum
from pathlib import Path
from typing import Literal, Optional

import argclass


def print_source(*classes_or_instances: object) -> None:
    """Print the source code of classes or instances."""
    print("### Source code ###\n")
    for obj in classes_or_instances:
        cls = obj if isinstance(obj, type) else type(obj)
        print(textwrap.dedent(inspect.getsource(cls)))
    print("###################")
    print()


DESCRIPTION = """\
argclass — declarative CLI parser built on top of argparse.

Type hints become CLI arguments automatically:
  str → string, int → integer, bool → flag,
  Optional[T] → optional, list[T] → multi-value,
  Literal[...] → choices, Enum → choices.

Priority: defaults < config files < env vars < CLI args.

Minimal example:

  class CLI(argclass.Parser):
      host: str = "localhost"      # --host
      port: int = 8080             # --port
      verbose: bool = False        # --verbose (flag)

  parser = CLI()
  parser.parse_args()

Run subcommands below to explore each feature interactively:
"""

EPILOG = """\
Value priority (lowest to highest):
  1. Class defaults
  2. Config files (INI/JSON/TOML)
  3. Environment variables
  4. CLI arguments

Examples:
  %(prog)s basic --name World --count 3 --debug
  %(prog)s types --mode fast --tags a b c --color green
  %(prog)s groups --server-host 0.0.0.0 --db-port 3306
  %(prog)s secrets --api-key my-secret
  DEMO_HOST=example.com %(prog)s env
  %(prog)s subcommands hello --user Alice
"""


# -- Helper types -------------------------------------------------


class Color(Enum):
    RED = "red"
    GREEN = "green"
    BLUE = "blue"


# -- Groups -------------------------------------------------------


class ServerGroup(argclass.Group):
    host: str = "localhost"
    port: int = 8080


class DatabaseGroup(argclass.Group):
    host: str = "localhost"
    port: int = 5432
    name: str = "mydb"


# -- Subcommand: basic -------------------------------------------


class BasicDemo(argclass.Parser):
    """Demonstrates basic type annotations.

    Python type hints map directly to argparse argument types:

      class CLI(argclass.Parser):
          name: str = "world"          # --name (string)
          count: int = 1               # --count (integer)
          ratio: float = 0.5           # --ratio (float)
          debug: bool = False          # --debug (flag)
          nickname: Optional[str]      # --nickname (optional)

    Try: basic --name Test --count 3 --ratio 0.7 --debug
    """

    name: str = argclass.Argument(
        default="world",
        help="A string argument",
    )
    count: int = argclass.Argument(
        default=1,
        help="An integer argument",
    )
    ratio: float = argclass.Argument(
        default=0.5,
        help="A float argument",
    )
    debug: bool = False
    nickname: Optional[str] = argclass.Argument(
        default=None,
        help="Optional string (not required)",
    )

    def __call__(self) -> int:
        print_source(self)
        print("== Basic Type Annotations ==\n")
        print(f"  name     = {self.name!r:20s} (str)")
        print(f"  count    = {self.count!r:20s} (int)")
        print(f"  ratio    = {self.ratio!r:20s} (float)")
        print(f"  debug    = {self.debug!r:20s} (bool flag)")
        print(f"  nickname = {self.nickname!r:20s} (Optional[str])")
        print()
        print("How it works:")
        print("  - str/int/float → argparse uses the type directly")
        print("  - bool with False default → --debug is store_true")
        print("  - Optional[str] → argument is not required")
        return 0


# -- Subcommand: types -------------------------------------------


class TypesDemo(argclass.Parser):
    """Demonstrates advanced types: Literal, list, Enum, frozenset.

      class CLI(argclass.Parser):
          mode: Literal["fast", "slow", "auto"] = "auto"
          tags: list[str] = []       # --tags a b c
          color: Color = Color.RED   # --color {red,green,blue}
          unique: frozenset[int] = argclass.Argument(
              type=int, nargs="+", converter=frozenset,
          )

    Try: types --mode fast --tags a b c --color green \\
               --unique 1 2 3 2 1
    """

    mode: Literal["fast", "slow", "auto"] = argclass.Argument(
        default="auto",
        help="Literal type becomes choices",
    )
    tags: list[str] = argclass.Argument(
        nargs=argclass.Nargs.ZERO_OR_MORE,
        default=[],
        help="List of strings (nargs=*)",
    )
    color: Color = argclass.Argument(
        default=Color.RED,
        help="Enum type becomes choices",
    )
    unique: frozenset = argclass.Argument(  # type: ignore[type-arg]
        type=int,
        nargs=argclass.Nargs.ONE_OR_MORE,
        converter=frozenset,
        default=frozenset(),
        help="frozenset deduplicates values",
    )

    def __call__(self) -> int:
        print_source(Color, self)
        print("== Advanced Types ==\n")
        print(f"  mode   = {self.mode!r}")
        print("    Literal['fast','slow','auto'] → choices")
        print(f"  tags   = {self.tags!r}")
        print("    list[str] with nargs=* → multiple values")
        print(f"  color  = {self.color!r}")
        print("    Enum → choices from enum values")
        print(f"  unique = {self.unique!r}")
        print("    frozenset + converter → deduplicated")
        return 0


# -- Subcommand: groups ------------------------------------------


class GroupsDemo(argclass.Parser):
    """Demonstrates argument groups with prefixes.

    Groups organize related arguments and add prefixes
    to avoid name collisions:

      class ServerGroup(argclass.Group):
          host: str = "localhost"
          port: int = 8080

      class DatabaseGroup(argclass.Group):
          host: str = "localhost"
          port: int = 5432

      class CLI(argclass.Parser):
          server = ServerGroup(title="Server options")
          db = DatabaseGroup(
              title="Database options", prefix="db",
          )

    Both groups have 'host' and 'port', but CLI flags
    are --server-host/--server-port vs --db-host/--db-port.

    Try: groups --server-host 0.0.0.0 --server-port 9090 \\
               --db-host db.local --db-port 3306 --db-name app
    """

    server: ServerGroup = ServerGroup(title="Server options")
    db: DatabaseGroup = DatabaseGroup(
        title="Database options",
        prefix="db",
    )

    def __call__(self) -> int:
        print_source(self.server, self.db, self)
        print("== Argument Groups ==\n")
        print("  Server group (prefix='server'):")
        print(f"    --server-host = {self.server.host!r}")
        print(f"    --server-port = {self.server.port!r}")
        print()
        print("  Database group (prefix='db'):")
        print(f"    --db-host     = {self.db.host!r}")
        print(f"    --db-port     = {self.db.port!r}")
        print(f"    --db-name     = {self.db.name!r}")
        print()
        print("How it works:")
        print("  - Group name or explicit prefix= avoids")
        print("    collisions when fields have the same name")
        print("  - Each group gets its own section in --help")
        return 0


# -- Subcommand: secrets -----------------------------------------


class SecretsDemo(argclass.Parser):
    """Demonstrates Secret arguments and SecretString masking.

      class CLI(argclass.Parser):
          api_key: str = argclass.Secret(
              env_var="API_KEY",
              help="Masked in repr/logs",
          )
          password: str = argclass.Secret()
          username: str = "admin"   # not a secret

    Secret values are wrapped in SecretString:
      - repr(value) → '******' (safe for logs)
      - str(value)  → actual value (when you need it)

    Try: secrets --api-key sk-12345 --password hunter2
    Also: API_KEY=from-env secrets
    """

    api_key: str = argclass.Secret(
        default="demo-key",
        env_var="DEMO_API_KEY",
        help="API key (masked in repr)",
    )
    password: str = argclass.Secret(
        default="s3cret",
        help="Password (masked in repr)",
    )
    username: str = argclass.Argument(
        default="admin",
        help="Username (not a secret, shown normally)",
    )

    def __call__(self) -> int:
        print_source(self)
        print("== Secrets & SecretString ==\n")
        print(f"  api_key  repr = {self.api_key!r}")
        print(f"  api_key  str  = {self.api_key!s}")
        print(f"  password repr = {self.password!r}")
        print(f"  password str  = {self.password!s}")
        print(f"  username repr = {self.username!r}")
        print()
        print("How it works:")
        print("  - Secret() wraps the value in SecretString")
        print("  - repr() shows '******' (safe for logging)")
        print("  - str() returns the actual value")
        print("  - parser.sanitize_env() clears env vars")
        print("    after parsing (prevents leaking to child")
        print("    processes)")
        return 0


# -- Subcommand: env ---------------------------------------------


class EnvDemo(argclass.Parser):
    """Demonstrates environment variable integration.

    Per-argument env vars:

      class CLI(argclass.Parser):
          host: str = argclass.Argument(
              default="localhost", env_var="APP_HOST",
          )

    Auto-prefix for all arguments:

      parser = CLI(auto_env_var_prefix="APP_")
      # --host reads from APP_HOST automatically

    Priority: default < env var < CLI argument.

    Try: DEMO_HOST=from-env DEMO_PORT=9999 env
    Try: DEMO_HOST=from-env env --host from-cli
    """

    host: str = argclass.Argument(
        default="localhost",
        env_var="DEMO_HOST",
        help="Server host [env: DEMO_HOST]",
    )
    port: int = argclass.Argument(
        default=8080,
        env_var="DEMO_PORT",
        help="Server port [env: DEMO_PORT]",
    )

    def __call__(self) -> int:
        print_source(self)
        print("== Environment Variables ==\n")
        print(f"  host = {self.host!r}")
        print(f"    env DEMO_HOST = {os.environ.get('DEMO_HOST')!r}")
        print(f"  port = {self.port!r}")
        print(f"    env DEMO_PORT = {os.environ.get('DEMO_PORT')!r}")
        print()
        print("How it works:")
        print("  - env_var='NAME' on an argument reads from")
        print("    that environment variable")
        print("  - auto_env_var_prefix='APP_' on Parser()")
        print("    generates env var names for all arguments")
        print("    automatically (e.g. --host → APP_HOST)")
        print("  - CLI args always override env vars")
        print("  - parser.sanitize_env() clears them after")
        return 0


# -- Subcommand: subcommands (with nesting) ----------------------


class HelloCommand(argclass.Parser):
    """Says hello to a user."""

    user: str = argclass.Argument(
        default="World",
        help="Who to greet",
    )
    greeting: str = argclass.Argument(
        default="Hello",
        help="Greeting word",
    )

    def __call__(self) -> int:
        print_source(self)
        print(f"{self.greeting}, {self.user}!")
        return 0


class InfoCommand(argclass.Parser):
    """Shows system information."""

    verbose: bool = False

    def __call__(self) -> int:
        print_source(self)
        print(f"Python:   {sys.version}")
        print(f"argclass: {argclass.__file__}")
        if self.verbose:
            print(f"Platform: {sys.platform}")
            print(f"Prefix:   {sys.prefix}")
        return 0


class SubcommandDemo(argclass.Parser):
    """Demonstrates subcommands and __call__ dispatch.

    Subcommands are Parser subclasses assigned as attributes.
    The default __call__ auto-dispatches to the selected
    subcommand. Override it for custom logic.

    Try: subcommands hello --user Alice
    Try: subcommands info --verbose
    """

    hello = HelloCommand()
    info = InfoCommand()

    def __call__(self) -> int:
        # Find a nested subparser (skip self in the chain)
        for sp in self.current_subparsers:
            if sp is not self:
                return sp()  # type: ignore[return-value]
        print_source(self.hello, self.info, self)
        self.print_help()
        return 1


# -- Top-level parser --------------------------------------------


class DemoParser(argclass.Parser):
    verbose: bool = False
    log_level: int = argclass.LogLevel

    basic = BasicDemo()
    types = TypesDemo()
    groups = GroupsDemo()
    secrets = SecretsDemo()
    env = EnvDemo()
    subcommands = SubcommandDemo()

    def __call__(self) -> int:
        result = super().__call__()
        if result is None:
            self.print_help()
            return 0
        return result


# -- Entry point -------------------------------------------------


def main() -> None:
    parser = DemoParser(
        prog=f"{Path(sys.executable).name} -m argclass",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=DESCRIPTION,
        epilog=EPILOG,
    )
    parser.parse_args()
    parser.sanitize_env()
    exit(parser())


if __name__ == "__main__":
    main()
