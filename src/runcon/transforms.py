import os
from typing import Any, List, Union

from .attrdict import is_mapping
from .runcon import Config, is_sequence


def remove_element(cfg: dict, target: str, key: Union[int, str] = None) -> None:
    if key is None:
        del cfg[target]
    else:
        del cfg[target][key]


Config.register_transform(remove_element)


def resolve_env(cfg: Any) -> Any:
    if is_mapping(cfg):
        for key in cfg:
            cfg[key] = resolve_env(cfg[key])
    elif is_sequence(cfg):
        try:
            for i, _ in enumerate(cfg):
                cfg[i] = resolve_env(cfg[i])
        except TypeError as err:
            if "does not support item assignment" not in str(err):
                raise
            t = type(cfg)
            cfg = t(resolve_env(elem) for elem in cfg)
    elif isinstance(cfg, str):
        if cfg[0] == "$":
            resolve = os.getenv(cfg[1:])
            if resolve is None:
                raise ValueError("environment variable named %s was not defined" % cfg)
            cfg = resolve

    return cfg


Config.register_transform(resolve_env)


def copy_value(cfg: Config, src: str, dest: str) -> None:
    if src not in cfg:
        raise ValueError("config has no key '%s' to copy from:\n%s" % (src, cfg))
    cfg[dest] = cfg[src]


Config.register_transform(copy_value, name="copy")


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
