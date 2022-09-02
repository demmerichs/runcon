#!/usr/bin/env python3

import pytest
import yaml

from runcon import AttrDict


def test_a_lot_of_functionality_of_attrdict():
    a = {"pops": None}
    print(yaml.safe_dump(AttrDict(a).todict()))
    a = {"_check_keyname_valid": 3}
    with pytest.raises(ValueError):
        AttrDict(a)
