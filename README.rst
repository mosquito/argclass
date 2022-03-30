argclass
========

A wrapper around the standard ``argparse`` module that allows you to describe
argument parsers declaratively.

By default, the ``argparse`` module suggests creating parsers imperative,
which is not convenient from the point of view of type checking and
access to attributes, of course, IDE autocompletion and type hints not
applicable in this case.

This module allows you to declare command-line parsers with classes.

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
    parser.parse_args()

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
                            (default: info)

    HTTP options:
      --http-address HTTP_ADDRESS
                            (default: 127.0.0.1)
      --http-port HTTP_PORT
                            (default: 8080)

    RPC options:
      --rpc-address RPC_ADDRESS
                            (default: 127.0.0.1)
      --rpc-port RPC_PORT   (default: 9090)
