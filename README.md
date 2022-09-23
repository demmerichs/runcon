[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI Stats: downloads](https://img.shields.io/pypi/dm/runcon.svg)](https://pypi.org/project/runcon)
[![pre-commit](https://github.com/demmerichs/runcon/actions/workflows/pre-commit.yml/badge.svg)](https://github.com/demmerichs/runcon/actions/workflows/pre-commit.yml)
[![Python Version](https://img.shields.io/pypi/pyversions/runcon)](https://github.com/demmerichs/runcon)
[![Package Version](https://img.shields.io/pypi/v/runcon)](https://pypi.org/project/runcon)
[![Package Status](https://img.shields.io/pypi/status/runcon)](https://github.com/demmerichs/runcon)
[![Tests](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/demmerichs/7e5c41da825c828d7db05e41cdaf5bc2/raw/test_badge.json)](https://github.com/demmerichs/runcon/actions/workflows/test_coverage.yml)
[![Coverage](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/demmerichs/7e5c41da825c828d7db05e41cdaf5bc2/raw/coverage_badge.json)](https://github.com/demmerichs/runcon/actions/workflows/test_coverage.yml)

# runcon <!-- omit in toc -->

runcon is an MIT-licensed package that provides a `Config` class with a lot of functionality that helps and simplifies organizing many, differently configured runs (hence the name **Run** **Con**figuration). Its main target audience are scientists and researchers who run many different experiments either in the real world or a computer-simulated environment and want to control the runs through a base configuration as well as save each run's settings in configuration files. The `Config` class helps creating differently configured runs through user-configurable hierarchical configuration layouts, it automatically creates paths for each run which can be used to save results, and it helps in comparing the config files of each run during the step of analyzing and comparing different runs.

This package was developed with Deep Learning experiments in mind. These usually consist of large and complex configurations and will therefore also be the basis for the upcoming examples of usage.

<a id="toc"></a>
- [Installation](#installation)
- [Basic Usage](#basic-usage)
  - [Loading configurations](#loading-configurations)
  - [Accessing configuration values](#accessing-configuration-values)
  - [Creating runs](#creating-runs)
  - [Organizing runs](#organizing-runs)

# Installation<a id="installation"></a> [`↩`](#toc)

runcon is in PyPI, so it can be installed directly using:
```bash
pip install runcon
```

Or from GitHub:
```bash
git clone https://github.com/demmerichs/runcon.git
cd runcon
pip install .
```

# Basic Usage<a id="basic-usage"></a> [`↩`](#toc)

This package builts upon `PyYAML` as a parser for loading and saving configuration files, therefor you should adhere to the YAML-Syntax when writing your configuration.

## Loading configurations<a id="loading-configurations"></a> [`↩`](#toc)

You can load from a single file:
<!--phmdoctest-share-names-->
```python
from runcon import Config

cfg = Config.from_file("cfgs/file_example.cfg")
print(cfg, end="")
```
produces
```
_CFG_ID: 1d4d313eedb05ae00c98ac8cb0a34946

top_level:
  more_levels:
    deep_level_list:
    - list_value
    - null
    - 3+4j
    - 3.14
    - true
```

Or you can load from a directory, in which case the filenames will become the toplevel keys. The following layout
```bash
cfgs
├── dir_example
│   ├── forest.cfg
│   └── garden.cfg
```
with the following code
```python
cfg = Config.from_dir("cfgs/dir_example", file_ending=".cfg")
print(cfg, end="")
```
produces
```
_CFG_ID: 705951e95af9b1f6cf314e0f96835349

forest:
  trees: 1000
  animals: 20

garden:
  trees: 2
  animals: 0
```

Another way to load multiple configuration files at once is by specifying all the files and their corresponding keys manually.

```python
key_file_dict = {
    "black_forest": "cfgs/dir_example/forest.cfg",
    "random_values": "cfgs/file_example.cfg",
}
cfg = Config.from_key_file_dict(key_file_dict)
print(cfg, end="")
```
produces
```
_CFG_ID: 60b454fb7619eb972cec13e99ff6addf

black_forest:
  trees: 1000
  animals: 20

random_values:
  top_level:
    more_levels:
      deep_level_list:
      - list_value
      - null
      - 3+4j
      - 3.14
      - true
```

## Accessing configuration values<a id="accessing-configuration-values"></a> [`↩`](#toc)

The `Config` object inherets `AttrDict` (a support class by `runcon`). Therefore, values can either be accessed the same way as in a `dict`, or via attribute-access.
Additionally, `Config` supports access via string-concatenation of the keys using a dot as delimiter, e.g.

```python
>>> from runcon import Config
>>> cfg = Config({
...     "top": {
...         "middle": {"bottom": 3.14},
...         "cfg": "value",
...     }
... })
>>> print(cfg.top.middle["bottom"])
3.14
>>> print(cfg["top"].cfg)
value
>>> print(cfg["top.middle.bottom"])
3.14
```

## Creating runs<a id="creating-runs"></a> [`↩`](#toc)

Most projects managing multiple runs do this by manually labeling different configuration setups for each run. The main drawbacks of this approach for a larger set of runs are:
- non-deterministic: Different people might label the same configuration differently or different configurations the same way. Even the same person might not remember after a week which settings exactly were changed based on their labeling.
- non-descriptive: In complex configurations a short label cannot capture all setting changes. Finding these via a diff-view can become daunting and unstructured, making it complicated to easliy grasp all the changes made.

Together with this package we propose an alternate way of structuring runs and configurations and trading of slightly longer "labels" for the removal of the above drawbacks.

Most projects start with a single default configuration, and going from there apply one or more change of settings to produce differently configured runs.
We suggest moving all this information into one or multiple configuration files, e.g. a single default configuration, and multiple named setting changes:
```yaml
# dl_example.cfg
default:
  model:
    name: ResNet
    layers: 50
  batchsize: 16
  optimizer:
    name: Adam
    learningrate: 1e-3
  loss: MSE

small_net:
  model:
    layers: 5

large_net:
  model:
    layers: 100

alex:
  model:
    name: AlexNet
  optimizer:
    name: SGD

large_bs:
  batchsize: 64
  optimizer:
    learningrate: 4e-3
```

You could now create in code your run configuration like this (but not miss the shortcut after this example):

```python
from copy import deepcopy

base_cfgs = Config.from_file("cfgs/dl_example.cfg")
cfg = deepcopy(base_cfgs.default)
# rupdate works similar to dict.update, but recursivly updates lower layers
cfg.rupdate(base_cfgs.large_net)
cfg.rupdate(base_cfgs.alex)
cfg.loss = "SmoothL1"
cfg.optimizer.learningrate = 1e-4
print(cfg, end="")
```
produces
```
_CFG_ID: be99468b9911c12ccba140ae5d9f487a

model:
  name: AlexNet
  layers: 100

batchsize: 16

optimizer:
  name: SGD
  learningrate: 0.0001
  weightdecay: 1.0e-06

loss: SmoothL1
```

As this pattern of stacking/merging configurations and possibly modifying a few single values is very common or at least the intended way for using this package, there is a simple shortcut function which operates on string input such that a CLI parser can easily pass values to this function.

For example, you might want to run a script specifying the above constructed configuration like this:
```
python your_runner_script.py \
    --cfg default large_net alex \
    --set \
        loss SmoothL1 \
        optimizer.learningrate 1e-4
```
The details of how your CLI interface should look and how you want to parse the values is left to you, (e.g. you could leave out `default` if you have only a single default configuration and just add it inside your code after CLI invocation), but parsing the above command options into the following all-strings variables
<!--phmdoctest-share-names-->
```python
cfg_chain = ["default", "large_net", "alex"]
set_values = [
    "loss", "SmoothL1",
    "optimizer.learningrate", "1e-4",
]
```
would allow you to call
<!--phmdoctest-share-names-->
```python
base_cfgs = Config.from_file("cfgs/dl_example.cfg")
cfg = base_cfgs.create(cfg_chain, kv=set_values)
print(cfg, end="")
```
and produces (using internally `ast.literal_eval` to parse non-string values, like booleans or floats, in this example `1e-4`)
```
_CFG_ID: be99468b9911c12ccba140ae5d9f487a

model:
  name: AlexNet
  layers: 100

batchsize: 16

optimizer:
  name: SGD
  learningrate: 0.0001
  weightdecay: 1.0e-06

loss: SmoothL1
```

The resulting label for this configuration would then consist of the configuration chain and the single key-value pairs, and can be automatically reconstructed from the base configs, e.g.
```python
print(cfg.create_auto_label(base_cfgs))
```
produces
```
default alex large_net -s optimizer.learningrate 0.0001 loss SmoothL1
```
Given the run configuration and the set of base configurations, this label can always deterministically be created, and making it shorter is just a matter of wrapping more key-value pairs or base configs into meta configurations.

For the above example this could mean just adding a `smoothl1` sub config which also changes the learning rate, e.g.
```python
base_cfgs.smoothl1 = Config({"loss": "SmoothL1", "optimizer": {"learningrate": 0.0001}})
print(cfg.create_auto_label(base_cfgs))
```
produces
```
default smoothl1 alex large_net
```

This approach mitigates both drawbacks mentioned earlier. The labels are deterministic, and based on the labels, it is quite easy to read of the changes made to the default configuration, as the label itself describes hierarchical changes and the base configurations modifying the default configuration are considered to be minimalistic.

## Organizing runs<a id="organizing-runs"></a> [`↩`](#toc)

After creating your run configuration in your script, it is time to create a directory for your new run, and using it to dump your results from that run.

<!--phmdoctest-share-names-->
```python
cfg_dir = cfg.initialize_cfg_path(base_path="/tmp/Config_test", timestamp=False)
print(type(cfg_dir), cfg_dir)
```
produces
```
<class 'pathlib.PosixPath'> /tmp/Config_test/8614010d20024c05f815cc8edcc8982f
```

The path mainly consists of two parts, a time stamp allowing you to store multiple runs with the same configuration (if you specify `timestampe=True`), and a hash produced by the configuration. Assuming hash collisions are too rare to be ever a problem, two configurations that differ somehow, will always produce different hashes. The hash is used, as it only depends on the configuration, whereas the automatic labeling depends also on the base configuration. The previous section demonstrated, how a change in the base configurations can produce a change in the automatic label. The `initialize_cfg_path` routine also produces a `description` folder next to the configuration folders, where symlinks are stored to the configuration folders, but with the automatic labels. This ensures, that the symlinks can easily be recreated based on a changed configuration, without the need to touch the actual run directories.

Another thing that happens during the path initialization is a call to `cfg.finalize()`. This should mimic the behavior of making all values constant and ensures that the configuration file that was created on disk actually represents all values used during the run execution, and accidental in-place value changes can be mostly ruled out.

```python
try:
  cfg.loss = "new loss"
except ValueError as e:
  print(e)
print(cfg.loss)
cfg.unfinalize()
cfg.loss = "new loss"
print(cfg.loss)
```
produces
```
This Config was already finalized! Setting attribute or item with name loss to value new loss failed!
SmoothL1
new loss
```

# License <!-- omit in toc -->
runcon is released under a MIT license.
