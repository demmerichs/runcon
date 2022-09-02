from typing import List, Union

from .attrdict import is_mapping
from .runcon import Config


def remove_element(cfg: dict, target: str, key: Union[int, str]) -> None:
    subcfg = cfg
    for t in target.split("."):
        subcfg = subcfg[t]
    del subcfg[key]


Config.register_transform(remove_element)


def make_setlike_dict(cfg: dict, targets: List[str]) -> None:
    for target in targets:
        subcfg = cfg
        *layer_cfgs, last_cfg = target.split(".")
        for t in layer_cfgs:
            subcfg = subcfg[t]
        subcfg[last_cfg] = Config({k: None for k in subcfg[last_cfg]})


Config.register_transform(make_setlike_dict)


def make_keys_upper_case(cfg: dict, recursive: bool = True):
    keys = list(cfg.keys())
    for k in keys:
        upper_k = k.upper()
        if upper_k in cfg:
            raise ValueError("upper case of key '%s' already exists" % k)
        cfg[upper_k] = cfg[k]
        del cfg[k]

    if recursive:
        for _k, v in cfg.items():
            if is_mapping(v):
                make_keys_upper_case(v, recursive=recursive)


Config.register_transform(make_keys_upper_case)
Config.register_transform(make_keys_upper_case, name="MAKE_KEYS_UPPER_CASE")
