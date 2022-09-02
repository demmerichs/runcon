import re
from collections import abc

VARIABLE_NAME_PATTERN = re.compile("[a-zA-Z_][a-zA-Z_0-9]*")


def is_mapping(struct) -> bool:
    return isinstance(struct, abc.Mapping)


class AttrDict(dict):
    """An AttrDict with strings as keys can also be accessed through
    attrdict.key = value notation."""

    def _check_keyname_valid(self, key: str) -> None:
        if not isinstance(key, str):
            raise ValueError("a key of an AttrDict needs to be a string")

        match = VARIABLE_NAME_PATTERN.fullmatch(key)
        if match is None:
            raise ValueError(
                "a key of an AttrDict needs to conform to variable naming rules, and"
                " can not be %s" % key
            )

        try:
            super().__getattribute__(key)
            raise ValueError(
                "a key of an AttrDict can not have the same name as a member attribute"
                " of AttrDict %s" % key
            )
        except AttributeError:
            pass

    def __getattribute__(self, *args, **kwargs):
        try:
            return super().__getattribute__(*args, **kwargs)
        except AttributeError:
            if args[0] in self.keys():
                return super().__getitem__(*args, **kwargs)

            raise AttributeError("AttrDict has no key %s" % args[0])

    def __setattr__(self, key: str, value):
        self.__setitem__(key, value)

    def __setitem__(self, key: str, value):
        self._check_keyname_valid(key)
        super().__setitem__(key, value)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for key in self:
            self[key] = self._recursive_dict_conversion(self[key])

    @classmethod
    def _recursive_dict_conversion(cls, nested_struct):
        if is_mapping(nested_struct):
            return cls(nested_struct)
        else:
            return nested_struct

    def todict(nested_struct):
        if is_mapping(nested_struct):
            return {k: AttrDict.todict(v) for k, v in nested_struct.items()}
        else:
            return nested_struct
