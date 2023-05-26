import logging

from argclass import SecretString


def test_secret_string():
    s = SecretString("password")
    assert repr(s) != str(s)
    assert repr(s) == repr(SecretString.PLACEHOLDER)
    assert f"{s!r}" == repr(SecretString.PLACEHOLDER)


def test_secret_log(caplog):
    s = SecretString("password")
    caplog.set_level(logging.INFO)

    with caplog.at_level(logging.INFO):
        logging.info(s)

    assert caplog.records[0].message == SecretString.PLACEHOLDER
    caplog.records.clear()

    with caplog.at_level(logging.INFO):
        logging.info("%s", s)

    assert caplog.records[0].message == SecretString.PLACEHOLDER
    caplog.records.clear()
