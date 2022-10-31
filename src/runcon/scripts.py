import importlib
from pathlib import Path

import click

from .runcon import Config, ast_parse
from .utils import sanitize_filename


@click.group()
def main():
    pass


@main.command()
@click.option("-c", "--configs", type=str, default=[], multiple=True)
@click.option("-s", "--set", "setters", type=(str, str), default=[], multiple=True)
@click.option("-u", "--unset", "unsetters", type=str, default=[], multiple=True)
def create(configs, setters, unsetters):
    ans = Config()

    for c in configs:
        if ":" in c:
            assert c.count(":") == 1
            path, key = c.split(":")
        else:
            path = c
            key = None
        path = Path(path)
        assert path.exists()
        if path.is_dir():
            assert key is None
            config = Config.from_dir(path)
        else:
            config = Config.from_file(path)
        if key is not None:
            config = config[key]

        ans.rupdate(config)

    for sk, sv in setters:
        ans[sk] = ast_parse(sv)

    for uk in unsetters:
        del ans[uk]

    print(ans)


@main.command()
@click.argument("cfg1", type=click.Path(exists=True))
@click.argument("cfg2", type=click.Path(exists=True))
def diff(cfg1, cfg2):
    print(Config.from_file(cfg1).diff(Config.from_file(cfg2)))


@main.group()
def symlink():
    pass


@symlink.command()
@click.option("-p", "--path", type=click.Path(exists=True), default=None)
def description(path):
    if path is None:
        path = Path.cwd()
    else:
        path = Path(path)
    for cfg_file in path.glob("*.cfg"):
        cfg_path = cfg_file.with_suffix("")
        desc_file = cfg_path / "description.txt"
        if not desc_file.exists():
            continue
        with desc_file.open("r") as fin:
            desc = fin.read().strip()
        Config.create_description_symlink(cfg_path, desc)


@symlink.command()
@click.option("-p", "--path", type=click.Path(exists=True), default=None)
@click.option("-b", "--base_config", type=click.Path(exists=True), default=None)
@click.option("-t", "--transforms", type=click.Path(exists=True), default=None)
def auto(path, base_config, transforms):
    if path is None:
        path = Path.cwd()
    else:
        path = Path(path)

    if base_config is None:
        base_cfg = Config()
    else:
        base_cfg = Config.from_file(base_config)

    if transforms is not None:
        transforms = Path(transforms).absolute()
        assert transforms.suffix == ".py"
        assert transforms.is_relative_to(Path.cwd())
        transforms = transforms.relative_to(Path.cwd())
        package_notation = str(transforms.with_suffix("")).replace("/", ".")
        importlib.import_module(package_notation)

    for cfg_file in path.glob("*.cfg"):
        cfg_path = cfg_file.with_suffix("")
        desc = Config.from_file(cfg_file).create_auto_label(base_cfg)
        desc = sanitize_filename(desc)
        Config.create_description_symlink(cfg_path, desc, name="auto")
