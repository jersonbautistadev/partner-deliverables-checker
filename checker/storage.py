"""Translate provider failures without confusing unavailable storage with absent originals."""
from contextlib import contextmanager

from botocore.exceptions import BotoCoreError, ClientError


class StorageUnavailable(Exception):
    pass


@contextmanager
def storage_errors():
    try:
        yield
    except (OSError, BotoCoreError, ClientError) as exc:
        raise StorageUnavailable from exc


def file_exists(file):
    with storage_errors():
        return file.storage.exists(file.name)
