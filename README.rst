argclass
========

.. image:: https://coveralls.io/repos/github/mosquito/argclass/badge.svg?branch=master
   :target: https://coveralls.io/github/mosquito/argclass?branch=master

.. image:: https://github.com/mosquito/argclass/workflows/tox/badge.svg
   :target: https://github.com/mosquito/argclass/actions?query=workflow%3Atox
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

    import logging

    import argclass


    class AddressPortGroup(argclass.Group):
        address: str = argclass.Argument(default="127.0.0.1")
        port: int


    class Parser(argclass.Parser):
        log_level: int = argclass.LogLevel
        http = AddressPortGroup(title="HTTP options", defaults=dict(port=8080))
        rpc = AddressPortGroup(title="RPC options", defaults=dict(port=9090))


    parser = Parser(
        config_files=[".example.ini", "~/.example.ini", "/etc/example.ini"],
        auto_env_var_prefix="EXAMPLE_"
    )
    parser.parse_args([])

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
    def handle_commit(_: None) -> None:
        pass


    @handle_subparser.register(CommitCommand)
    def handle_commit(subparser: CommitCommand) -> None:
        pass


    @handle_subparser.register(PushCommand)
    def handle_commit(subparser: PushCommand) -> None:
        pass


    parser = Parser(
        config_files=["example.ini", "~/.example.ini", "/etc/example.ini"],
        auto_env_var_prefix="EXAMPLE_"
    )
    parser.parse_args()
    handle_subparser(parser.current_subparser)
