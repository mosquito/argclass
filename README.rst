argclass
========

.. image:: https://coveralls.io/repos/github/mosquito/argclass/badge.svg?branch=master
   :target: https://coveralls.io/github/mosquito/argclass?branch=master

.. image:: https://github.com/mosquito/argclass/workflows/tests/badge.svg
   :target: https://github.com/mosquito/argclass/actions?query=workflow%3Atests
   :alt: Actions

.. image:: https://img.shields.io/pypi/v/argclass.svg
   :target: https://pypi.python.org/pypi/argclass/
   :alt: Latest Version

.. image:: https://img.shields.io/pypi/pyversions/argclass.svg
   :target: https://pypi.python.org/pypi/argclass/

.. image:: https://img.shields.io/pypi/l/argclass.svg
   :target: https://pypi.python.org/pypi/argclass/

A wrapper around the standard ``argparse`` module that allows you to describe
argument parsers declaratively.

By default, the ``argparse`` module suggests creating parsers imperative,
which is not convenient from the point of view of type checking and
access to attributes, of course, IDE autocompletion and type hints not
applicable in this case.

This module allows you to declare command-line parsers with classes.

Simple example:

.. code-block:: python
    :name: test_simple_example

    import logging

    import argclass


    class CopyParser(argclass.Parser):
        recursive: bool
        preserve_attributes: bool


    parser = CopyParser()
    parser.parse_args(["--recursive", "--preserve-attributes"])
    assert parser.recursive
    assert parser.preserve_attributes

As you can see this example shown a basic module usage, when you want specify
argument default and other options you have to use ``argclass.Argument``.

Following example use ``argclass.Argument`` and argument groups:

.. code-block:: python
    :name: test_example

    from typing import FrozenSet
    import logging

    import argclass


    class AddressPortGroup(argclass.Group):
        address: str = argclass.Argument(default="127.0.0.1")
        port: int


    class Parser(argclass.Parser):
        log_level: int = argclass.LogLevel
        http = AddressPortGroup(title="HTTP options", defaults=dict(port=8080))
        rpc = AddressPortGroup(title="RPC options", defaults=dict(port=9090))
        user_id: FrozenSet[int] = argclass.Argument(
            nargs="*", type=int, converter=frozenset
        )


    parser = Parser(
        config_files=[".example.ini", "~/.example.ini", "/etc/example.ini"],
        auto_env_var_prefix="EXAMPLE_"
    )
    parser.parse_args([])

    # Remove all used environment variables from os.environ
    parser.sanitize_env()

    logging.basicConfig(level=parser.log_level)
    logging.info('Listening http://%s:%d', parser.http.address, parser.http.port)
    logging.info(f'Listening rpc://%s:%d', parser.rpc.address, parser.rpc.port)


    assert parser.http.address == '127.0.0.1'
    assert parser.rpc.address == '127.0.0.1'

    assert parser.http.port == 8080
    assert parser.rpc.port == 9090


Run this script:

.. code-block::

    $ python example.py
    INFO:root:Listening http://127.0.0.1:8080
    INFO:root:Listening rpc://127.0.0.1:9090

Example of ``--help`` output:

.. code-block::

    $ python example.py --help
    usage: example.py [-h] [--log-level {debug,info,warning,error,critical}]
                     [--http-address HTTP_ADDRESS] [--http-port HTTP_PORT]
                     [--rpc-address RPC_ADDRESS] [--rpc-port RPC_PORT]

    optional arguments:
      -h, --help            show this help message and exit
      --log-level {debug,info,warning,error,critical}
                            (default: info) [ENV: EXAMPLE_LOG_LEVEL]

    HTTP options:
      --http-address HTTP_ADDRESS
                            (default: 127.0.0.1) [ENV: EXAMPLE_HTTP_ADDRESS]
      --http-port HTTP_PORT
                            (default: 8080) [ENV: EXAMPLE_HTTP_PORT]

    RPC options:
      --rpc-address RPC_ADDRESS
                            (default: 127.0.0.1) [ENV: EXAMPLE_RPC_ADDRESS]
      --rpc-port RPC_PORT   (default: 9090) [ENV: EXAMPLE_RPC_PORT]

    Default values will based on following configuration files ['example.ini',
    '~/.example.ini', '/etc/example.ini']. Now 1 files has been applied
    ['example.ini']. The configuration files is INI-formatted files where
    configuration groups is INI sections.
    See more https://pypi.org/project/argclass/#configs

Secrets
+++++++

Arguments reflecting some sensitive data, tokens or encryption keys, when
passed through environment variables or a configuration file, can be printed
in the output of `--help`. To hide defaults, add the `secret=True` parameter,
or use the special default constructor `argclass.Secret` instead of
`argclass.Argument`.

.. code-block:: python

    import argclass


    class HttpAuthentication(argclass.Group):
        username: str = argclass.Argument()
        password: str = argclass.Secret()


    class HttpBearerAuthentication(argclass.Group):
        token: str = argclass.Argument(secret=True)


    class Parser(argclass.Parser):
        http_basic = HttpAuthentication()
        http_bearer = HttpBearerAuthentication()


    parser = Parser()
    parser.print_help()

Configs
+++++++

The parser objects might be get default values from environment variables or
one of passed configuration files.

.. code-block:: python

    class AddressPortGroup(argclass.Group):
        address: str = argclass.Argument(default="127.0.0.1")
        port: int


    class Parser(argclass.Parser):
        spam: str
        quantity: int
        log_level: int = argclass.LogLevel
        http = AddressPortGroup(title="HTTP options")
        rpc = AddressPortGroup(title="RPC options")
        user_ids = argclass.Argument(
            type=int, converter=frozenset, nargs=argclass.Nargs.ONE_OR_MORE
        )


    # Trying to parse all passed configuration files
    # and break after first success.
    parser = Parser(
        config_files=[".example.ini", "~/.example.ini", "/etc/example.ini"],
    )
    parser.parse_args()


In this case each passed and existent configuration file will be opened.

The root level arguments might described in the ``[DEFAULT]`` section.

Other arguments might be described in group specific sections.

So the full example of config file for above example is:

.. code-block:: ini

    [DEFAULT]
    log_level=info
    spam=egg
    quantity=100
    user_ids=[1, 2, 3]

    [http]
    address=127.0.0.1
    port=8080

    [rpc]
    address=127.0.0.1
    port=9090


Subparsers
++++++++++

Complex example with subparsers:

.. code-block:: python

    import logging
    from functools import singledispatch
    from pathlib import Path
    from typing import Optional, Any

    import argclass


    class AddressPortGroup(argclass.Group):
        address: str = argclass.Argument(default="127.0.0.1")
        port: int


    class CommitCommand(argclass.Parser):
        comment: str = argclass.Argument()


    class PushCommand(argclass.Parser):
        comment: str = argclass.Argument()


    class Parser(argclass.Parser):
        log_level: int = argclass.LogLevel
        endpoint = AddressPortGroup(
            title="Endpoint options",
            defaults=dict(port=8080)
        )
        commit: Optional[CommitCommand] = CommitCommand()
        push: Optional[PushCommand] = PushCommand()


    @singledispatch
    def handle_subparser(subparser: Any) -> None:
        raise NotImplementedError(
            f"Unexpected subparser type {subparser.__class__!r}"
        )


    @handle_subparser.register(type(None))
    def handle_none(_: None) -> None:
        Parser().print_help()
        exit(2)


    @handle_subparser.register(CommitCommand)
    def handle_commit(subparser: CommitCommand) -> None:
        print("Commit command called", subparser)


    @handle_subparser.register(PushCommand)
    def handle_push(subparser: PushCommand) -> None:
        print("Push command called", subparser)


    parser = Parser(
        config_files=["example.ini", "~/.example.ini", "/etc/example.ini"],
        auto_env_var_prefix="EXAMPLE_"
    )
    parser.parse_args()
    handle_subparser(parser.current_subparser)

Value conversion
++++++++++++++++

If the argument has a generic or composite type, then you must explicitly
describe it using ``argclass.Argument``, while specifying the converter
function with ``type`` or ``converter`` argument to transform the value
after parsing the arguments.

The exception to this rule is `Optional` with a single type. In this case,
an argument without a default value will not be required,
and its value can be None.

.. code-block:: python
    :name: test_converter

    import argclass
    from typing import Optional, Union

    def converter(value: str) -> Optional[Union[int, str, bool]]:
        if value.lower() == "none":
            return None
        if value.isdigit():
            return int(value)
        if value.lower() in ("yes", "true", "enabled", "enable", "on"):
            return True
        return False


    class Parser(argclass.Parser):
        gizmo: Optional[Union[int, str, bool]] = argclass.Argument(
            converter=converter
        )
        optional: Optional[int]


    parser = Parser()

    parser.parse_args(["--gizmo=65535"])
    assert parser.gizmo == 65535

    parser.parse_args(["--gizmo=None"])
    assert parser.gizmo is None

    parser.parse_args(["--gizmo=on"])
    assert parser.gizmo is True
    assert parser.optional is None

    parser.parse_args(["--gizmo=off", "--optional=10"])
    assert parser.gizmo is False
    assert parser.optional == 10
