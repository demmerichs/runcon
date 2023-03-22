import os
from typing import Any, List

from .attrdict import is_mapping
from .runcon import Config, is_sequence


def remove_element(cfg: Config, key: str, idx: int = None) -> None:
    """Remove an element from a collection.

    Examples:
        >>> cfg = Config(
        ...     a={'b': [3.14, 2.71], 'c': 'pi'},
        ...     _TRANSFORM=[
        ...         {'name': 'remove_element', 'key': 'a.c'},
        ...         {'name': 'remove_element', 'key': 'a.b', 'idx': 1},
        ...     ]
        ... )
        >>> print(cfg.resolve_transforms())
        _CFG_ID: a2faf743fded6c92e3fc83b994b7a065
        <BLANKLINE>
        a:
          b:
          - 3.14
        <BLANKLINE>

    Args:
        cfg: The configuration to which the transform is applied.
        key: The config key which is removed (or a list-element, see idx).
        idx: If not None, specifying a specific list idx to be deleted
             instead of the entire list.
    """
    if idx is None:
        del cfg[key]
    else:
        del cfg[key][idx]


Config.register_transform(remove_element)


def resolve_env(cfg: Any) -> Any:
    """Resolve environment variables in all collections, marked through a leading $.

    Examples:
        >>> cfg = Config(
        ...     a={'b': [3.14, '$RESOLVABLE_ENV_VARIABLE']},
        ...     _TRANSFORM=['resolve_env']
        ... )
        >>> os.environ['RESOLVABLE_ENV_VARIABLE'] = 'pi'
        >>> print(cfg.resolve_transforms())
        _CFG_ID: a2faf743fded6c92e3fc83b994b7a065
        <BLANKLINE>
        a:
          b:
          - 3.14
          - pi
        <BLANKLINE>

    Args:
        cfg: The configuration, or any subcollection, to which the transform is applied.
    """
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


def copy(cfg: Config, src: str, dest: str, expr: str = None, **kwargs) -> None:
    """Copy a value from one config key to another.

    Examples:
        >>> cfg = Config(
        ...     a={'b': 3.14},
        ...     _TRANSFORM=[
        ...         dict(name='copy',src='a.b',dest='c.d.e'),
        ...         dict(name='copy',src='a.b', another_src='c.d', dest='f',
        ...              expr='[src, another_src, src*2, [src]*2]'),
        ...     ]
        ... )
        >>> print(cfg.resolve_transforms())
        _CFG_ID: 4dea82568c56bf77f51d19e9aaa27f95
        <BLANKLINE>
        a:
          b: 3.14
        <BLANKLINE>
        c:
          d:
            e: 3.14
        <BLANKLINE>
        f:
        - 3.14
        - e: 3.14
        - 6.28
        - - 3.14
          - 3.14
        <BLANKLINE>

    Args:
        cfg: The configuration to which the transform is applied.
        src: The key of the source value.
        dest: The key that is created or overriden using the source value.
        expr: If provided, the destination will become an evaluation of the string,
              replacing names with config values specified by src and other kwargs.
              `simpleeval` is the package used in the background
              and only supports basic operations.
    """
    if expr is None:
        if src not in cfg:
            raise ValueError("config has no key '%s' to copy from:\n%s" % (src, cfg))
        if len(kwargs):
            raise ValueError(
                "kwargs were provided without an 'expr' that uses them:\n%s"
                % set(kwargs.keys())
            )
        cfg[dest] = cfg[src]
    else:
        import copy as copy_module

        import simpleeval as se

        kwargs["src"] = src
        substitutions = se.DEFAULT_NAMES
        for name, key in kwargs.items():
            if name not in expr:
                raise ValueError(
                    "variable %s was given in kwargs but not used in expr '%s'"
                    % (name, expr)
                )
            if key not in cfg:
                raise ValueError(
                    "config has no key '%s' to copy from:\n%s" % (key, cfg)
                )
            substitutions[name] = copy_module.copy(cfg[key])
        cfg[dest] = se.EvalWithCompoundTypes(names=substitutions).eval(expr)


Config.register_transform(copy, name="copy")


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
