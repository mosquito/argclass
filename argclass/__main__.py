import argparse
import sys
from pathlib import Path

import argclass


class GreetCommand(argclass.Parser):
    user: str = argclass.Argument("user", help="User to greet")

    def __call__(self) -> int:
        print(f"Hello, {self.user}!")
        return 0


class Parser(argclass.Parser):
    verbose: bool = False
    secret_key: str = argclass.Secret(help="Secret API key")
    greet = GreetCommand()


def main() -> None:
    parser = Parser(
        prog=f"{Path(sys.executable).name} -m argclass",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "This code produces this help:\n\n```"
            f"python\n{open(__file__).read().strip()}\n```"
        ),
    )
    parser.parse_args()
    parser.sanitize_env()
    exit(parser())


if __name__ == "__main__":
    main()
