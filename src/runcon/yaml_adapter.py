import re
from types import MappingProxyType

import yaml

from .runcon import Config, ConfigDiff

yaml.add_representer(
    Config,
    yaml.representer.SafeRepresenter.represent_dict,
    yaml.representer.SafeRepresenter,
)
yaml.add_representer(
    ConfigDiff,
    yaml.representer.SafeRepresenter.represent_dict,
    yaml.representer.SafeRepresenter,
)
yaml.add_representer(
    MappingProxyType,
    yaml.representer.SafeRepresenter.represent_dict,
    yaml.representer.SafeRepresenter,
)


def represent_complex(dumper, value):
    return dumper.represent_scalar("tag:yaml.org,2002:str", str(value)[1:-1])


yaml.add_representer(complex, represent_complex, yaml.representer.SafeRepresenter)


# HACK: insert blank lines between top-level objects
# inspired by https://github.com/yaml/pyyaml/issues/127#issuecomment-525800484
def write_line_break(self, data=None):
    super(yaml.SafeDumper, self).write_line_break(data)

    if len(self.indents) == 1:
        super(yaml.SafeDumper, self).write_line_break()


# see https://github.com/python/mypy/issues/2427
yaml.SafeDumper.write_line_break = write_line_break  # type: ignore[assignment]


# HACK: fix reading scientific notation as shown in
# https://stackoverflow.com/a/30462009/10220850
loader = yaml.SafeLoader
loader.add_implicit_resolver(
    "tag:yaml.org,2002:float",
    re.compile(
        """^(?:
     [-+]?(?:[0-9][0-9_]*)\\.[0-9_]*(?:[eE][-+]?[0-9]+)?
    |[-+]?(?:[0-9][0-9_]*)(?:[eE][-+]?[0-9]+)
    |\\.[0-9_]+(?:[eE][-+][0-9]+)?
    |[-+]?[0-9][0-9_]*(?::[0-5]?[0-9])+\\.[0-9_]*
    |[-+]?\\.(?:inf|Inf|INF)
    |\\.(?:nan|NaN|NAN))$""",
        re.X,
    ),
    list("-+0123456789."),
)
