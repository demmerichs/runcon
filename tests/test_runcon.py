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
    assert """_CFG_ID: 0a6a5f378de0c87441ed16983b3ba94a

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

apples: apples

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
    with pytest.raises(ValueError) as err:
        cfg.resolve_transforms()
    assert "environment variable named $RUNCON_TEST_ENV was not defined" == str(
        err.value
    )

    import os

    os.environ["RUNCON_TEST_ENV"] = "ENV_SET"

    cfg = Config.from_file(Path("tests/cfgs/resolve_a_few_transforms.yml"))
    cfg.resolve_transforms()
    assert """_CFG_ID: 78ede4e425031ef67f21e9d9cb4c3cef

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
  virtual_env:
    direct: ENV_SET
    list:
    - ENV_SET
    - running_test
    list_of_list:
    - - ENV_SET
      - running_test
    - - ENV_SET
      - running_test
""" == str(
        cfg
    )


def test_correct_transform_resolving_during_auto_label():
    @Config.register_transform
    def check_and_annotate_a(cfg):
        assert "a" not in cfg.top
        cfg.top.a = 6.28

    @Config.register_transform
    def check_and_annotate_b(cfg):
        assert "b" not in cfg.top
        cfg.top.b = 2.72

    base_cfgs = Config(
        default={"top": {"middle": {"bottom": 3.14}}},
        annotate_a={"_TRANSFORM": ["check_and_annotate_a"]},
        annotate_b={"_TRANSFORM": ["check_and_annotate_b"]},
    )

    transform_attr_exception_cfg = Config(outer=deepcopy(base_cfgs.annotate_a))

    with pytest.raises(AttributeError) as err:
        transform_attr_exception_cfg.resolve_transforms()
    assert "AttrDict has no key top" == str(err.value)

    cfg = deepcopy(base_cfgs.default)
    cfg.rupdate(base_cfgs.annotate_a)
    cfg.rupdate(base_cfgs.annotate_b)
    cfg.resolve_transforms()
    assert """_CFG_ID: ed5e5c36560dbeee9e96b795fa22b51d

top:
  middle:
    bottom: 3.14
  a: 6.28
  b: 2.72
""" == str(
        cfg
    )
    assert cfg.create_auto_label(base_cfgs) == "default annotate_a annotate_b"


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
        dump_code=True,
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
        " some_path /path/to"
        " --unset living.plants non_living".split()
    )
    assert """_CFG_ID: 2d5634fe9da161e243c79101af0a84eb

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

some_path: /path/to
""" == str(
        args.config
    )


def test_diff_of_finalized_vs_unfinalized_config():
    cfg = Config(
        {
            "list_of_dicts": [{"a": 3}, {"b": 1}, {"c": 4}],
        }
    )
    cfg_unfinalized = cfg
    cfg_finalized = deepcopy(cfg).finalize()
    assert """_CFG_ID: 8a80554c91d9fca8acb82f023de02f11
""" == str(
        cfg_unfinalized.diff(cfg_finalized)
    )
    assert """_CFG_ID: 8a80554c91d9fca8acb82f023de02f11
""" == str(
        cfg_finalized.diff(cfg_unfinalized)
    )


def test_transform_order():
    base_cfgs = Config(
        {
            "default": {"pi": 3.14, "e": 2.72},
            "some_transform": {"_TRANSFORM": ["MAKE_KEYS_UPPER_CASE"]},
            "some_other_transform": {
                "_TRANSFORM": [{"name": "remove_element", "target": "pi"}]
            },
        }
    )
    cfg = base_cfgs.create(["default", "some_other_transform", "some_transform"])
    assert """_CFG_ID: f48cdd40f7b13a4e609dae0c5693c3a7

E: 2.72
""" == str(
        cfg
    )

    with pytest.raises(KeyError) as err:
        cfg = base_cfgs.create(["default", "some_transform", "some_other_transform"])
    assert "'pi'" == str(err.value)


def test_set_value_dot_concat_notation():
    cfg = Config()
    cfg["top.middle.bottom"] = 3.14
    assert """_CFG_ID: 8fe42c8c06258012f8fd887222903e52

top:
  middle:
    bottom: 3.14
""" == str(
        cfg
    )


def test_pickling():
    import pickle

    cfg = Config(pi=3.14, e=2.72, constants=[3.14, 2.72])
    pcfg = pickle.loads(pickle.dumps(cfg))
    assert str(cfg) == str(pcfg)
    assert not cfg._finalized and cfg._finalized == pcfg._finalized
    assert isinstance(cfg.constants, list) and isinstance(pcfg.constants, list)

    cfg.finalize()
    pcfg = pickle.loads(pickle.dumps(cfg))
    assert str(cfg) == str(pcfg)
    assert cfg._finalized and cfg._finalized == pcfg._finalized
    assert isinstance(cfg.constants, tuple) and isinstance(pcfg.constants, tuple)
