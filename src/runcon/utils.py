import hashlib
import re
from collections import abc
from datetime import datetime
from typing import Union

Numeric = Union[int, float, complex]
Scalar = Union[Numeric, str, bool, None]
Struct = Union[Scalar, abc.Mapping, abc.Sequence]
FILENAME_SANITIZER_PATTERN = re.compile("[^A-Za-z0-9_.]")


def hash_string(string):
    return hashlib.md5(string.encode()).hexdigest()


def get_time_stamp(include_date=True, include_micros=False):
    micros = ""
    if include_micros:
        micros = "-%f"
    if include_date:
        return datetime.now().strftime("%Y%m%d-%H%M%S" + micros)
    else:
        return datetime.now().strftime("%H%M%S" + micros)


def sanitize_filename(name):
    return FILENAME_SANITIZER_PATTERN.sub("_", name)
