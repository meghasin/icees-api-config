from dataclasses import dataclass
import os
from typing import Any, List, Optional, Union, Type
import yaml

from .config import get_config_path


@dataclass
class Feature:
    name: str 
    _type: Union[Type[int], Type[str], Type[float]]
    options: Optional[List[Any]]


with open(os.path.join(get_config_path(), 'all_features.yaml'), 'r') as f:
    features_dict = yaml.load(f, Loader=yaml.SafeLoader)


def dict_to_Feature(table, key, value):
    """Convert feature from dict form to tuple."""
    if value['type'] == 'integer':
        _type = int
        if 'minimum' in value and 'maximum' in value:
            options = list(range(value['minimum'], value['maximum'] + 1))
        else:
            options = None
    elif value['type'] == 'string':
        _type = str
        if 'enum' in value:
            options = value['enum']
        else:
            options = None
    elif value['type'] == 'number':
        _type = float
        options = None
    else:
        raise ValueError('Unsupported type {}'.format(value['type']))
    return Feature(key, _type, options)


features = {
    key0: [dict_to_Feature(key0, key1, value1) for key1, value1 in value0.items()]
    for key0, value0 in features_dict.items()
}
