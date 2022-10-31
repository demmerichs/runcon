from __future__ import annotations

import argparse
import ast
import os
import shutil
import sys
from collections import abc
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Sequence, Tuple, Union

import yaml
from git import Repo
from typing_extensions import get_args, get_origin

from .attrdict import AttrDict, FrozenAttrDict, is_mapping
from .utils import Scalar, Struct, get_time_stamp, hash_string, sanitize_filename


def is_sequence(struct) -> bool:
    return isinstance(struct, abc.Sequence) and not isinstance(struct, str)


def is_scalar(struct) -> bool:
    assert get_origin(Scalar) is Union
    return isinstance(struct, get_args(Scalar))


def ast_parse(value: str) -> Any:
    try:
        value = ast.literal_eval(value)
    except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
        pass
    return value


class Config(AttrDict):
    BASE_CFG_TOKEN = "_BASE"
    TRANSFORM_CFG_TOKEN = "_TRANSFORM"
    CFG_ID_TOKEN = "_CFG_ID"
    RUPDATE_CONCAT_LISTS = {TRANSFORM_CFG_TOKEN}
    _transforms: Dict[str, Callable] = {}

    @classmethod
    def register_transform(cls, tf: Callable, name: str = None):
        if name is None:
            name = tf.__name__
        if name in cls._transforms:
            raise ValueError(
                "can not register '%s' as transform, as the name is already in use"
                % name
            )
        cls._transforms[name] = tf

    def set_attribute(self, name: str, value: Any):
        # safe way to set an attribute without accidentally setting a key-value pair
        if name in self.keys():
            raise ValueError(
                "can not set attribute '%s' because a key with the same name already"
                " exists" % name
            )
        super(dict, self).__setattr__(name, value)

    def set_description(self, description: str):
        self.set_attribute("_description", description)

    def __init__(self, *args, **kwargs):
        self._finalized: bool
        self._initialized_path: Path
        self._description: str
        self.set_attribute("_finalized", False)
        self.set_attribute("_initialized_path", None)
        self.set_description(None)
        super().__init__(*args, **kwargs)

    @staticmethod
    def _finalize_substructs(struct: Struct, final: bool) -> Struct:
        try:
            return struct.finalize(final)  # type: ignore[union-attr]
        except AttributeError:
            pass

        if is_mapping(struct):
            mapping = {
                k: Config._finalize_substructs(v, final)
                for k, v in struct.items()  # type: ignore[union-attr]
            }
            if final:
                return FrozenAttrDict(mapping)
            else:
                return mapping

        if is_sequence(struct):
            sequence = (Config._finalize_substructs(v, final) for v in struct)  # type: ignore[union-attr]  # noqa: E501
            if final:
                return tuple(sequence)
            else:
                return list(sequence)

        assert is_scalar(struct)
        return struct

    def get_cfg_id(self) -> str:
        sub_cfg_ids = {}
        for k in sorted(self.keys()):
            try:
                sub_cfg_ids[k] = self[k].get_cfg_id()
            except AttributeError:
                sub_cfg_ids[k] = None

        return hash_string(yaml.safe_dump(sub_cfg_ids))

    def finalize(self, final: bool = True) -> Config:
        if final == self._finalized:
            return self

        if not final:
            self.set_attribute("_finalized", False)

        for k, v in self.items():
            self[k] = Config._finalize_substructs(v, final)

        if final:
            self.set_attribute("_finalized", True)

        return self

    def unfinalize(self) -> Config:
        return self.finalize(False)

    def __getitem__(self, *args, **kwargs):
        key = args[0]
        if isinstance(key, str) and "." in key:
            first, *others = key.split(".")
            return self[first][".".join(others)]

        return super().__getitem__(*args, **kwargs)

    def __delitem__(self, *args, **kwargs):
        if self._finalized:
            raise ValueError(
                "This Config was already finalized! "
                "Deleting attribute or item with name %s failed!" % str(args[0])
            )

        key = args[0]
        if isinstance(key, str) and "." in key:
            first, *others = key.split(".")
            return self[first].__delitem__(".".join(others), *args[1:], **kwargs)

        return super().__delitem__(*args, **kwargs)

    def __setitem__(self, *args, **kwargs):
        if hasattr(self, "_finalized") and self._finalized:
            raise ValueError(
                "This Config was already finalized! "
                "Setting attribute or item with name %s to value %s failed!"
                % (str(args[0]), str(args[1]))
            )

        key = args[0]
        if isinstance(key, str) and "." in key:
            first, *others = key.split(".")
            self[first] = self.get(first, Config())
            return self[first].__setitem__(".".join(others), *args[1:], **kwargs)

        return super().__setitem__(*args, **kwargs)

    # required because __setitem__ differs from AttrDict base implementation
    __setattr__ = __setitem__

    def __deepcopy__(self, memo) -> Config:
        # deepcopy only works when not finalized,
        #   otherwise setting values on the copy fails
        # in order to do a deepcopy of a finalized Config,
        #   we need to unfinalize first

        final = self._finalized
        self.unfinalize()

        # doing default deepcopy(3) by deleting(2) this function while backing it up(1)
        # and later restoring it(4)
        deepcopy_method = self.__deepcopy__  # (1) backup
        self.set_attribute("__deepcopy__", None)  # (2) delete
        cp = deepcopy(self, memo)  # (3) default deepcopy
        self.set_attribute("__deepcopy__", deepcopy_method)  # (4) restore
        cp.set_attribute(
            "__deepcopy__", Config.__deepcopy__.__get__(cp, Config)
        )  # (4) restore on copy as well

        self.finalize(final)
        cp.finalize(final)

        return cp

    def _resolve_cfg_id_after_file_loading(self):
        if Config.CFG_ID_TOKEN not in self.keys():
            return

        cfg_id_in_file = self[Config.CFG_ID_TOKEN]
        del self[Config.CFG_ID_TOKEN]

        if cfg_id_in_file != self.get_cfg_id():
            raise ValueError(
                "the loaded config contains a CFG_ID '%s' which is not compatible to"
                " the rest of the config '%s'" % (cfg_id_in_file, self.get_cfg_id())
            )

    @classmethod
    def add_cli_parser(
        cls,
        parser: argparse.ArgumentParser,
        base_cfgs: Config,
        dest: str = "config",
        name: Union[str, Sequence[str]] = ("-c", "--config"),
        set_name: Union[str, Sequence[str]] = ("-s", "--set"),
        unset_name: Union[str, Sequence[str]] = ("-u", "--unset"),
    ):
        group = parser.add_argument_group(dest)

        class ConfigAction(argparse.Action):
            def __call__(
                self,
                parser: argparse.ArgumentParser,
                namespace: argparse.Namespace,
                values,
                option_string=None,
            ):
                if getattr(namespace, self.dest) is None:
                    setattr(namespace, self.dest, cls())

                for cfg_name in values:
                    getattr(namespace, self.dest).rupdate(base_cfgs[cfg_name])

                getattr(namespace, self.dest).resolve_transforms()

        class ConfigSetAction(argparse.Action):
            def __call__(
                self,
                parser: argparse.ArgumentParser,
                namespace: argparse.Namespace,
                values,
                option_string=None,
            ):
                if getattr(namespace, self.dest) is None:
                    setattr(namespace, self.dest, cls())

                N = len(values) // 2
                assert len(values) == 2 * N

                for k, v in zip(values[::2], values[1::2]):
                    getattr(namespace, self.dest)[k] = ast_parse(v)

        class ConfigUnsetAction(argparse.Action):
            def __call__(
                self,
                parser: argparse.ArgumentParser,
                namespace: argparse.Namespace,
                values,
                option_string=None,
            ):
                if getattr(namespace, self.dest) is None:
                    setattr(namespace, self.dest, cls())

                for k in values:
                    del getattr(namespace, self.dest)[k]

        name = [name] if isinstance(name, str) else name
        group.add_argument(*name, action=ConfigAction, nargs="+", dest=dest)
        set_name = [set_name] if isinstance(set_name, str) else set_name
        group.add_argument(*set_name, action=ConfigSetAction, nargs="+", dest=dest)
        unset_name = [unset_name] if isinstance(unset_name, str) else unset_name
        group.add_argument(*unset_name, action=ConfigUnsetAction, nargs="+", dest=dest)

    @classmethod
    def _load_file(cls, filename: Union[str, Path]) -> Config:
        filename = Path(filename)
        with filename.open() as f:
            cfg = Config(yaml.safe_load(f))
        cfg._resolve_cfg_id_after_file_loading()
        return cfg

    @classmethod
    def from_file(cls, filename: Union[str, Path]) -> Config:
        cfg = cls._load_file(filename)
        cfg.resolve_base_cfgs()
        return cfg

    @classmethod
    def from_dir(cls, dirname: Union[str, Path], file_ending: str = ".cfg") -> Config:
        dirname = Path(dirname)
        files = dirname.glob("*" + file_ending)
        key_file_dict = {f.stem: f for f in sorted(files)}
        return cls.from_key_file_dict(key_file_dict)

    @classmethod
    def from_key_file_dict(
        cls, key_file_dict: Mapping[str, Union[str, Path]]
    ) -> Config:
        cfg = Config()

        for k, fname in key_file_dict.items():
            cfg[k] = cls._load_file(fname)

        cfg.resolve_base_cfgs()

        return cfg

    def create(self, cfg_chain: Sequence[str], kv: Sequence[str] = None) -> Config:
        assert len(cfg_chain) > 0
        ans = deepcopy(self[cfg_chain[0]])
        for cfg_name in cfg_chain[1:]:
            ans.rupdate(self[cfg_name])

        ans.resolve_transforms()

        if kv is None:
            return ans

        N = len(kv) // 2
        assert len(kv) == 2 * N

        for k, v in zip(kv[::2], kv[1::2]):
            ans[k] = ast_parse(v)

        return ans

    def resolve_base_cfgs(self, base_cfgs: Config = None) -> Config:
        if base_cfgs is None:
            base_cfgs = self

        # resolve lower-level base configs first
        for k, v in self.items():
            try:
                self[k] = v.resolve_base_cfgs(base_cfgs)
            except AttributeError:
                pass

        if Config.BASE_CFG_TOKEN not in self:
            return self

        # we do a backup and clear
        #   in order to add the base configs first
        #   and then restore the backup
        # this ensures the correct ordering of elements inside the dict,
        #   as intended by the user
        backup = list(self.items())
        if backup[0][0] != Config.BASE_CFG_TOKEN:
            raise ValueError(
                "always put base configs in the beginning of the dictionary, instead"
                " the order was %s" % str([k for k, _v in backup])
            )
        self.clear()

        bases = backup[0][1]
        if not is_sequence(bases):
            bases = [bases]

        for base in bases:
            cur_base_cfg = base_cfgs[base]
            if not is_mapping(cur_base_cfg) and len(backup) == 1 and len(bases) == 1:
                return deepcopy(cur_base_cfg)
            else:
                # ensure cur_base_cfg is resolved before using it
                cur_base_cfg = cur_base_cfg.resolve_base_cfgs(base_cfgs)
                self.rupdate(deepcopy(cur_base_cfg))

        self.rupdate(dict(backup[1:]))
        return self

    def resolve_transforms(self) -> Config:
        # resolve lower-level config transforms first
        for k, v in self.items():
            try:
                self[k] = v.resolve_transforms()
            except AttributeError as err:
                if "has no attribute 'resolve_transforms'" in str(err):
                    pass
                else:
                    raise

        if Config.TRANSFORM_CFG_TOKEN not in self:
            return self

        transforms = self[Config.TRANSFORM_CFG_TOKEN]
        del self[Config.TRANSFORM_CFG_TOKEN]

        if not is_sequence(transforms):
            transforms = [transforms]

        for tf in transforms:
            if isinstance(tf, str):
                tf_name = tf
                tf_kwargs = {}
            elif is_mapping(tf):
                if "name" not in tf:
                    raise ValueError(
                        "you need to specify the transform through a 'name' key, which"
                        " is not present in %s" % str(tf)
                    )
                tf_name = tf["name"]
                tf_kwargs = deepcopy(tf)
                del tf_kwargs["name"]
            else:
                raise ValueError(
                    "transform either needs to be a mapping with 'name' and other"
                    " kwargs or just a string being the name, not %s" % str(tf)
                )

            if tf_name not in self._transforms:
                raise ValueError("no transform named '%s' is registered" % tf_name)
            self._transforms[tf_name](self, **tf_kwargs)

        return self

    def riter(self):
        for k in self:
            try:
                subriter = self[k].riter()
                for s in subriter:
                    yield ".".join([k, s])
            except AttributeError:
                yield k

    def rupdate(
        self,
        struct_update,
    ) -> None:
        try:
            struct_update_items = struct_update.items()
        except AttributeError:
            raise ValueError(
                "trying to rupdate Config with a non-dict %s" % str(struct_update)
            )
        for k, v in struct_update_items:
            try:
                self[k].rupdate(v)
            except (KeyError, AttributeError):
                # if key k is not in self (KeyError),
                # or self[k] is not rupdate-able (AttributeError)
                if (
                    k in Config.RUPDATE_CONCAT_LISTS
                    and k in self
                    and is_sequence(self[k])
                    and is_sequence(v)
                ):
                    self[k].extend(deepcopy(v))
                else:
                    self[k] = deepcopy(v)

    def get_hash_value(self):
        return hash_string(yaml.safe_dump(self, sort_keys=True))

    def dump_cfg(self, filename: Union[str, Path], exist_ok: bool = False):
        filename = Path(filename)
        if not filename.exists():
            with filename.open("w") as f:
                f.write(str(self))
        elif not exist_ok:
            raise EnvironmentError(
                "file '%s' for config dump already exists" % filename
            )

    def __str__(self):
        add_dump_info = {Config.CFG_ID_TOKEN: self.get_cfg_id()}
        dump_dict = add_dump_info
        dump_dict.update(self)
        return yaml.safe_dump(
            dump_dict,
            default_flow_style=False,
            sort_keys=False,
        )

    @staticmethod
    def dump_command(path: Union[str, Path]):
        path = Path(path)
        cmd = str(Path(sys.argv[0]).resolve()) + " " + " ".join(sys.argv[1:])

        cmd_path = path / "command.txt"

        if cmd_path.exists():
            with cmd_path.open() as f:
                lines = "\n".join(f.readlines())
            if cmd != lines:
                raise ValueError(
                    "a command was already dumped at '%s' which contains '%s' and is"
                    " different from the current command '%s'" % (cmd_path, lines, cmd)
                )

        with cmd_path.open("w") as f:
            f.write(cmd)

    @staticmethod
    def create_description_symlink(
        path: Union[str, Path], description: str, name: str = "description"
    ):
        path = Path(path)

        if description != sanitize_filename(description):
            raise ValueError(
                "description '%s' is not a safe filename, consider to use '%s' instead"
                % (description, sanitize_filename(description))
            )

        src = Path("..") / path.name
        dst = path.parent / name / description
        dst.parent.mkdir(parents=True, exist_ok=True)

        try:
            dst.exists()
        except OSError as err:
            if "File name too long:" in str(err):
                raise OSError(
                    str(err) + "\nCan not create symlink for '%s'" % path
                ) from err
            else:
                raise

        if dst.exists():
            if not dst.is_symlink():
                raise EnvironmentError(
                    "destination '%s' for description symlink already exists but is not"
                    " a symlink" % dst
                )
            if Path(os.readlink(dst)) != src:
                raise EnvironmentError(
                    "destination '%s' for description symlink already exists, but is"
                    " linked to a different target '%s'" % (dst, Path(os.readlink(dst)))
                )
            return
        dst.symlink_to(src)
        Path(str(dst) + ".cfg").symlink_to(str(src) + ".cfg")

    @staticmethod
    def dump_description(path: Union[str, Path], description: str):
        path = Path(path)
        dst = path / "description.txt"
        if dst.exists():
            with dst.open("r") as fin:
                lines = "\n".join(fin.readlines())
            if lines != description:
                raise ValueError(
                    "dumping description '%s' failed because an existing description"
                    " file '%s' with different content '%s' was found"
                    % (description, dst, lines)
                )
        else:
            with dst.open("w") as fout:
                fout.write(description)

    @staticmethod
    def dump_code_snapshot(path: Union[str, Path]):
        path = Path(path)
        dst = (path / "snapshot").resolve()

        if dst.exists():
            raise ValueError("there already exists a code snapshot at %s" % dst)

        repo_base = Path.cwd()
        while not (repo_base / ".git").is_dir():
            repo_base = repo_base.parent

        repo = Repo(repo_base)

        def ignore(cur_dir: Union[str, Path], contents: Sequence[str]):
            cur_dir = Path(cur_dir)
            ans = set()
            if (cur_dir / dst.name).resolve() == dst:
                ans.add(dst.name)
            if cur_dir.resolve() == repo_base:
                ans.add(".git")
            ignoreds = repo.ignored([cur_dir / cont for cont in contents])
            ignoreds = {str(Path(ign).relative_to(cur_dir)) for ign in ignoreds}
            ans |= ignoreds
            assert ans.issubset(contents), (ans, contents)
            return ans

        shutil.copytree(repo_base, dst, symlinks=True, ignore=ignore)

        cwd = Path.cwd()
        os.chdir(repo_base)

        dst_githist = dst / ".githistory"
        if dst_githist.exists():
            raise ValueError("the snapshot already contains a '.githistory'")
        dst_githist.mkdir()
        os.system(
            "git log --oneline --no-decorate --no-abbrev-commit"
            " > %s" % (dst_githist / "gitlog.txt")
        )
        os.system("git remote -v > %s" % (dst_githist / "gitremotes.txt"))

        os.chdir(cwd)

    def get_cfg_path(self) -> Path:
        if self._initialized_path is None:
            raise ValueError(
                "you can only request the config path after you called"
                " 'initialize_cfg_path'"
            )
        return self._initialized_path

    def initialize_cfg_path(
        self,
        base_path: Union[str, Path],
        *,
        exist_ok: bool = True,
        timestamp: Union[str, bool] = False,
        dump_command: bool = True,
        dump_code: bool = False,
        verbose: bool = False,
        create_description_symlink: bool = True,
    ) -> Path:
        """Create and return path based on the hash of this config.
        Parameters
        ----------
        base_path : string
            Base path under which this directory should be constructed.
        Returns
        -------
        string
            Create the directory and returns its path. Also creates a file with
            the same name and '.cfg' as extension were all the parameters are
            listed in yaml format.
        """
        assert self._initialized_path is None
        self.finalize()
        hash_value = self.get_hash_value()
        base_path = Path(base_path)
        dirname = base_path / hash_value
        if timestamp is True:
            stamped_dirname = dirname / get_time_stamp(include_micros=True)
            while stamped_dirname.exists():
                stamped_dirname = dirname / get_time_stamp(include_micros=True)
        elif isinstance(timestamp, str):
            stamped_dirname = dirname / timestamp
        else:
            assert timestamp is False
            stamped_dirname = dirname
        dir_already_existed = False
        if stamped_dirname.exists():
            if stamped_dirname != dirname:
                raise EnvironmentError(
                    "could not create config directory, timestamp was already used and"
                    " '%s' already exists" % stamped_dirname
                )
            dir_already_existed = True
            if verbose:
                print("Config directory already exists:\t\t%s" % stamped_dirname)
        stamped_dirname.mkdir(parents=True, exist_ok=exist_ok)
        if not dir_already_existed and verbose:
            print("Config directory created:\t\t%s" % stamped_dirname)
        self.dump_cfg(dirname.with_suffix(".cfg"), exist_ok=exist_ok)
        if dump_command:
            Config.dump_command(stamped_dirname)
        if dump_code:
            Config.dump_code_snapshot(stamped_dirname)
        self.set_attribute("_initialized_path", stamped_dirname)
        if self._description is not None:
            if create_description_symlink:
                self.create_description_symlink(dirname, self._description)
            self.dump_description(dirname, self._description)
        return stamped_dirname

    def diff(self, other: Config) -> ConfigDiff:
        return ConfigDiff(self, other)

    def create_auto_label(
        self, base_cfgs: Config, start_cfg: Config = None, top_k: int = 5
    ):
        if start_cfg is None:
            start_cfg = Config()
        start_cfg_transform_resolved = deepcopy(start_cfg).resolve_transforms()
        sdiff = start_cfg_transform_resolved.diff(self)
        struct_diff, old_diff, new_diff = sdiff.diff_count()
        next_iter_cfgs = [
            (
                "",
                start_cfg,
                sdiff,
                (len(sdiff.create_diff_label()), struct_diff, new_diff, old_diff),
            )
        ]
        for bname, bcfg in base_cfgs.items():
            cfg = deepcopy(start_cfg)
            cfg.rupdate(bcfg)
            try:
                cfg_transform_resolved = deepcopy(cfg).resolve_transforms()
            except Exception as err:
                err_parts = str(err).split("'")
                if len(err_parts) != 3:
                    continue
                if err_parts[0] != "no transform named ":
                    continue
                if err_parts[2] != " is registered":
                    continue
                raise
            cdiff = cfg_transform_resolved.diff(self)
            struct_diff, old_diff, new_diff = cdiff.diff_count()
            next_iter_cfgs.append(
                (
                    bname,
                    cfg,
                    cdiff,
                    (len(cdiff.create_diff_label()), struct_diff, new_diff, old_diff),
                )
            )

        next_iter_cfgs = sorted(next_iter_cfgs, key=lambda x: (x[3], len(x[0]), x[0]))

        if next_iter_cfgs[0][0] == "":
            return next_iter_cfgs[0][2].create_diff_label()

        while next_iter_cfgs[-1][0] != "":
            del next_iter_cfgs[-1]
        del next_iter_cfgs[-1]

        next_iter_cfgs = next_iter_cfgs[:top_k]

        best_auto_label = None
        for bname, cfg, _cdiff, _diff_counts in next_iter_cfgs:
            sub_autolabel = self.create_auto_label(
                base_cfgs, start_cfg=cfg, top_k=top_k
            )
            auto_label = bname
            if len(sub_autolabel) > 0:
                auto_label += " " + sub_autolabel
            if best_auto_label is None:
                best_auto_label = auto_label
            if len(best_auto_label) > len(auto_label):
                best_auto_label = auto_label

        return best_auto_label


class ConfigDiff(Config):
    class Nothing:
        pass

    def __init__(self, cfg_old: Union[Config, Struct], cfg_new: Union[Config, Struct]):
        super().__init__()
        self.set_attribute("_ConfigDiff__leaf", False)

        if cfg_old is ConfigDiff.Nothing:
            if cfg_new is ConfigDiff.Nothing:
                return
            self.set_new(cfg_new)
            return

        if cfg_new is ConfigDiff.Nothing:
            self.set_old(cfg_old)
            return

        assert isinstance(cfg_old, Config) == isinstance(cfg_new, Config)

        if not isinstance(cfg_old, Config):
            if cfg_old == cfg_new:
                return
            self.set_old(cfg_old)
            self.set_new(cfg_new)
            return

        assert isinstance(cfg_old, Config)
        assert isinstance(cfg_new, Config)
        cfg_old = deepcopy(cfg_old).finalize()
        cfg_new = deepcopy(cfg_new).finalize()

        # create all_keys list in this manner to preserve order
        all_keys = list(cfg_old)
        for k in cfg_new:
            if k not in all_keys:
                all_keys.append(k)

        for k in all_keys:
            cfg_diff = ConfigDiff(
                cfg_old.get(k, ConfigDiff.Nothing), cfg_new.get(k, ConfigDiff.Nothing)
            )
            if cfg_diff.struct_count() > 0:
                self[k] = cfg_diff

    def _check_keyname_valid(self, key: str) -> None:
        if key == "<":
            return
        return super()._check_keyname_valid(key)

    def is_leaf(self) -> bool:
        return self.__leaf

    def set_old(self, value):
        self.set_attribute("_ConfigDiff__leaf", True)
        if isinstance(value, Config):
            value = value.todict()
        self["<"] = value

    def get_old(self):
        return self["<"]

    def set_new(self, value):
        self.set_attribute("_ConfigDiff__leaf", True)
        if isinstance(value, Config):
            value = value.todict()
        self["N"] = value

    def get_new(self):
        return self["N"]

    @staticmethod
    def scalars_in_struct(struct: Struct) -> int:
        assert get_origin(Scalar) is Union
        if isinstance(struct, get_args(Scalar)):
            return 1
        if is_mapping(struct):
            assert isinstance(struct, Mapping)
            return ConfigDiff.scalars_in_struct(list(struct.items()))
        if is_sequence(struct):
            assert isinstance(struct, Sequence)
            return sum(ConfigDiff.scalars_in_struct(s) for s in struct)
        raise ValueError(struct)

    def diff_count(self) -> Tuple[int, int, int]:
        if self.is_leaf():
            try:
                old_count = ConfigDiff.scalars_in_struct(self.get_old())
            except KeyError:
                old_count = 0
            try:
                new_count = ConfigDiff.scalars_in_struct(self.get_new())
            except KeyError:
                new_count = 0
            return (1, old_count, new_count)

        sub_counts = []
        for k in self:
            sub_counts.append(self[k].diff_count())

        return (
            sum(sc[0] for sc in sub_counts),
            sum(sc[1] for sc in sub_counts),
            sum(sc[2] for sc in sub_counts),
        )

    def struct_count(self) -> int:
        return self.diff_count()[0]

    def create_diff_label(self) -> str:
        setters = []
        unsetters = []

        for k in self.riter():
            assert k[-2:] in {".<", ".N"}
            if k[-1] == "<":
                diff = self[k[:-2]]
                if "N" not in diff:
                    unsetters.append(k[:-2])
            else:
                setters.append((k[:-2], str(self[k])))

        ans = []
        if len(setters):
            ans.append("-s")
            for s in setters:
                ans += list(s)
        if len(unsetters):
            ans.append("-u")
            for u in unsetters:
                ans.append(u)

        return " ".join(ans)
