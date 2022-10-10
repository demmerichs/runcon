#!/usr/bin/env python3

import argparse
from copy import deepcopy
from math import inf, pi
from pathlib import Path

import pytest
import yaml

from runcon import Config
from runcon.utils import get_time_stamp


def test_finalization_of_config():
    cfg = Config({"b": 3, "a": 2 + 3j, "c": [3, "asdf", {"cool": inf}]})
    cfg.finalize()

    assert """_CFG_ID: c94fff15151e0d64e518cc353d5aa9c7

b: 3

a: 2+3j

c:
- 3
- asdf
- cool: .inf
""" == str(
        cfg
    )

    with pytest.raises(ValueError) as err:
        cfg["d"] = None
    assert (
        err.value.args[0]
        == "This Config was already finalized! Setting attribute or item with name"
        " d to value None failed!"
    )

    with pytest.raises(ValueError) as err:
        cfg["b"] = 3 + 2j
    assert (
        err.value.args[0]
        == "This Config was already finalized! Setting attribute or item with name"
        " b to value (3+2j) failed!"
    )

    with pytest.raises(TypeError) as err:
        cfg["c"][2]["cool"] = pi
    assert (
        err.value.args[0] == "'FrozenAttrDict' object does not support item assignment"
    )
    assert cfg["c"][2].cool == inf

    with pytest.raises(TypeError) as err:
        del cfg["c"][1]
    assert err.value.args[0] == "'tuple' object doesn't support item deletion"

    cfg.unfinalize()

    cfg["d"] = None
    cfg["b"] = 3 + 2j
    cfg["c"][2]["cool"] = pi
    del cfg["c"][1]

    assert """_CFG_ID: f85ab6d23bdd7609a2a943a63c0a23ba

b: 3+2j

a: 2+3j

c:
- 3
- cool: 3.141592653589793

d: null
""" == str(
        cfg
    )


def test_cfg_id_of_config():
    cfg1 = Config({"a": 3, "b": {"d": None, "c": "c"}, "c": "c"})
    cfg2 = Config({"a": "hi", "b": {"d": 3, "c": "c"}, "c": pi})
    cfg3 = Config({"b": {"c": None, "d": None}, "a": None, "c": None})
    cfg4 = Config({"b": {"c": None, "d": None, "e": None}, "a": None, "c": None})
    cfg5 = Config({"b": {"d": None}, "a": None, "c": None})
    cfg6 = Config({"b": {"c": None, "d": None}, "c": None})
    cfg7 = Config({"b": {"c": None, "d": None}, "a": None, "e": None})
    cfg1.finalize()
    cfg2.finalize()
    cfg3.finalize()
    cfg4.finalize()
    cfg5.finalize()
    cfg6.finalize()
    cfg7.finalize()
    id1 = cfg1.get_cfg_id()
    id2 = cfg2.get_cfg_id()
    id3 = cfg3.get_cfg_id()
    id4 = cfg4.get_cfg_id()
    id5 = cfg5.get_cfg_id()
    id6 = cfg6.get_cfg_id()
    id7 = cfg7.get_cfg_id()

    assert id2 == id1
    assert id3 == id1
    assert len({id1, id2, id3, id4, id5, id6, id7}) == 5, (
        id1,
        id2,
        id3,
        id4,
        id5,
        id6,
        id7,
    )

    cfg1_repr = """_CFG_ID: fef72b7e6e4509f04447a5bdce122c2d

a: 3

b:
  d: null
  c: c

c: c
"""

    assert cfg1_repr == str(cfg1)
    cfg1.unfinalize()
    assert cfg1_repr == str(cfg1)


def test_deep_copy_of_config():
    cfg1 = Config(num=3, list=[1, 2, 3])
    cfg1.finalize()

    cfg2 = deepcopy(cfg1)
    with pytest.raises(TypeError) as err:
        cfg2.list[1] = 3
    assert err.value.args[0] == "'tuple' object does not support item assignment"


def test_invalid_keys_of_config():
    with pytest.raises(ValueError) as err:
        Config(finalize="asdf")
    assert (
        err.value.args[0]
        == "a key of an AttrDict can not have the same name as a member attribute of"
        " AttrDict finalize"
    )


def test_cfg_hashes():
    cfg1 = Config(
        {
            "asdf": 3,
            "dict": {"jkl": None, "job": True},
        }
    )
    cfg2 = Config(
        {
            "dict": {"jkl": None, "job": True},
            "asdf": 3,
        }
    )
    assert str(cfg1) != str(cfg2)

    cfg3 = Config(
        {
            "dict": {"jkl": None, "job": True},
            "asdf": 4,
        }
    )

    h1 = cfg1.get_hash_value()
    cfg1_unfinalized_repr = str(cfg1)
    cfg1.finalize()
    assert str(cfg1) == cfg1_unfinalized_repr
    h1f = cfg1.get_hash_value()
    h2 = cfg2.get_hash_value()
    h3 = cfg3.get_hash_value()

    assert h1 == h1f
    assert h1 == h2
    assert h1 != h3


def test_file_loading_of_config():
    with pytest.raises(FileNotFoundError) as err:
        Config.from_file(Path("tests/cfgs/does_not_exist.yml"))
    assert (
        str(err.value)
        == "[Errno 2] No such file or directory: 'tests/cfgs/does_not_exist.yml'"
    )
    with pytest.raises(ValueError) as err:
        Config.from_file(Path("tests/cfgs/broken_cfg_id.yml"))
    assert (
        "the loaded config contains a CFG_ID 'ed4df1d3753957459ec8760ace5e6967' which"
        " is not compatible to the rest of the config"
        " '61a8fc69952c1864904f42b0f374a704'" == str(err.value)
    )

    Config.from_file(Path("tests/cfgs/correct_cfg_id.yml"))


def test_base_resolving_of_config():
    cfg = Config.from_file(Path("tests/cfgs/resolve_a_few_bases.yml"))
    assert """_CFG_ID: eb34e5b5e991a59bc9871573a76bd55e

plants:
  tree:
    branches:
      leaves: green
    trunk: brown
  appletree:
    branches:
      leaves: green
      fruits: apples
    trunk: brown
  oaktree:
    branches:
      leaves: green
    trunk: white

with_apples:
  branches:
    fruits: apples

pets:
- dog
- cat

nature:
  non_living:
  - rocks
  - water
  - air
  living:
    animals:
    - dog
    - cat
    plants:
      tree:
        branches:
          leaves: green
        trunk: brown
      appletree:
        branches:
          leaves: green
          fruits: apples
        trunk: brown
      oaktree:
        branches:
          leaves: green
        trunk: white
      algea: null
""" == str(
        cfg
    )


def test_transform_resolving_of_config():
    def remove_element():
        return "dummy"

    with pytest.raises(ValueError) as err:
        Config.register_transform(remove_element)
    assert (
        "can not register 'remove_element' as transform, as the name is already in use"
        == str(err.value)
    )

    cfg = Config.from_file(Path("tests/cfgs/resolve_a_few_transforms.yml"))
    assert """_CFG_ID: 9ce64f4ea2b95bf2f5206728eefd2c1a

nature:
  non_living:
    rocks: null
    water: null
    air: null
  living:
    animals:
      cat: null
    plants:
      appletree:
        BRANCHES:
          LEAVES: green
          FRUITS: apples
        TRUNK: brown
      oaktree:
        BRANCHES:
          leaves: green
        TRUNK: white
      algea: null
""" == str(
        cfg
    )


def test_a_lot_of_functionality_of_config():
    # test config recursive update
    cfg1 = Config(
        num=3,
        str="asdf",
        list=[1, 2, 3],
        seq=[4, {"uiop": 3}, 6],
        dict={"asdf": 3},
        bool=True,
        alphadict={"b": "a", "a": "b", "D": "D", "c": "c"},
    )
    cfg2 = {
        "str": "update",
        "list": [3, 4, 5],
        "dict": {"asdf": 5},
        "list_of_list": [[1, 2], [3], 4],
    }
    cfg1.rupdate(cfg2)
    assert """_CFG_ID: ed4df1d3753957459ec8760ace5e6967

num: 3

str: update

list:
- 3
- 4
- 5

seq:
- 4
- uiop: 3
- 6

dict:
  asdf: 5

bool: true

alphadict:
  b: a
  a: b
  D: D
  c: c

list_of_list:
- - 1
  - 2
- - 3
- 4
""" == str(
        cfg1
    )
    assert type(cfg1) == Config
    assert type(cfg1.dict) == Config
    assert type(cfg1.seq) == list
    assert type(cfg1.seq[1]) == dict
    assert (
        str(yaml.safe_load(str(cfg1)))
        == "{'_CFG_ID': 'ed4df1d3753957459ec8760ace5e6967', 'num': 3, 'str': 'update',"
        " 'list': [3, 4, 5], 'seq': [4, {'uiop': 3}, 6], 'dict': {'asdf': 5},"
        " 'bool': True, 'alphadict': {'b': 'a', 'a': 'b', 'D': 'D', 'c': 'c'},"
        " 'list_of_list': [[1, 2], [3], 4]}"
    )
    cfg1.set_description("cfg1")
    cfg1_temp = deepcopy(cfg1)
    cfg1_temp.initialize_cfg_path(
        "/tmp/runcon_test",
        timestamp=True,
    )
    cfg1_temp = deepcopy(cfg1)
    cfg1_temp.initialize_cfg_path(
        "/tmp/runcon_test",
        timestamp=get_time_stamp(include_micros=False),
    )
    cfg1_temp = deepcopy(cfg1)
    cfg1_temp.initialize_cfg_path(
        "/tmp/runcon_test",
        timestamp=get_time_stamp(include_date=False),
    )


def test_argparse_config():
    parser = argparse.ArgumentParser()
    base_cfgs = Config.from_file("tests/cfgs/resolve_a_few_bases.yml")
    Config.add_cli_parser(parser, base_cfgs)
    args = parser.parse_args(
        "--config nature with_apples"
        " --set planets ['Mercury','Venus','Earth','Mars',"
        "'Jupiter','Saturn','Uranus','Neptune']"
        " branches.fruits pears"
        " --unset living.plants non_living".split()
    )
    assert """_CFG_ID: d75ffd508e287912cdf17a05271e95e3

living:
  animals:
  - dog
  - cat

branches:
  fruits: pears

planets:
- Mercury
- Venus
- Earth
- Mars
- Jupiter
- Saturn
- Uranus
- Neptune
""" == str(
        args.config
    )
