# Third-Party Integrations

**argclass** builds on the standard library's `argparse`, so any argparse
extension or third-party library works seamlessly.

## Rich Help Output

Use `rich_argparse` for beautiful help formatting:

```python
import argclass
from rich_argparse import RawTextRichHelpFormatter

class Parser(argclass.Parser):
    verbose: bool = False
    output: str = "result.txt"

parser = Parser(formatter_class=RawTextRichHelpFormatter)
parser.print_help()
```

![Help Output](https://raw.githubusercontent.com/mosquito/argclass/master/.github/rich_example.png)

## Other argparse Extensions

Any `argparse`-compatible library can be used with argclass:

- **argcomplete** - Tab completion for bash/zsh
- **configargparse** - Config file support (though argclass has built-in support)
- **argparse-manpage** - Generate man pages from parsers
