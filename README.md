# Ewok - Education Warehouse Octopus Kit

![Ewok Logo](https://github.com/educationwarehouse/ewok/blob/master/docs/logo.png?raw=true)

[![PyPI version](https://img.shields.io/pypi/v/ewok.svg)](https://pypi.org/project/ewok/)
[![Python versions](https://img.shields.io/pypi/pyversions/ewok.svg)](https://pypi.org/project/ewok/)
[![License](https://img.shields.io/pypi/l/ewok.svg)](https://github.com/educationwarehouse/ewok/blob/main/LICENSE.txt)

**Ewok** (Education Warehouse Octopus Kit) is a powerful CLI framework built on top
of [Invoke](https://www.pyinvoke.org/) and [Fabric](https://www.fabfile.org/). It extends them with features for
plugin-based, composable command-line tools.

---

## Quick Start

Follow these steps to create a basic Ewok-powered CLI.

### 1. Example Project structure

```

my_project/
├── src/
│   └── my_package/
│       ├── __init__.py
│       └── tasks.py
├── pyproject.toml

````

You can merge your CLI into `__init__.py` for simplicity.

### 2. Define your Ewok app

```python
# src/my_package/__init__.py
from ewok import App
from . import tasks

app = App(
    name="myapp",
    version="0.1.0",
    core_module=tasks,
)
````

### 3. Define a task

```python
# src/my_package/tasks.py
from ewok import task, Context
# you can also import Context from invoke instead; ewok.Context is an alias


@task
def hello(c: Context, name: str = "world"):
    """Print a friendly greeting"""
    print(f"Hello, {name}!")
```

### 4. Configure `pyproject.toml`

```toml
[project]
name = "my-project"
version = "0.1.0"
dependencies = [
    "ewok>=0.1.0",
    # other dependencies...
]

[project.scripts]
myapp = "my_package:app"
```

> `myapp` will be installed as an executable that runs the `app` object.

### 5. Install in development mode

```bash
#  The `-e` flag performs an editable install — useful while developing.
uv pip install -e .
```

Then try your CLI:

```bash
myapp hello --name Alice
```

```
Hello, Alice!
```

---

## Features

* **Multi-source Task Integration**:

    * Core tasks from your package
    * Plugin tasks via entry points (namespaced)
    * Personal tasks from `~/.config/<name>/tasks.py`
    * Project-local `tasks.py` (namespaced as `local.`)
    * Extra namespaced modules like `dev.tasks.py` → `dev.taskname`

* **Plugin System**: Discover and load tasks from external packages

* **Flexible Namespacing**: Mix-and-match functionality per project, plugin, and personal

* **Invoke/Fabric Compatible**: Supports all base task features

---

## Creating an Ewok App

Ewok’s `App` class wraps and extends Invoke’s CLI system.

### Ewok-specific arguments

These options extend the default behavior of Invoke/Fabric:

| Parameter           | Description                                                           | Default            |
|---------------------|-----------------------------------------------------------------------|--------------------|
| `name`              | Name of your CLI tool (used in help/version)                          | **Required**       |
| `version`           | App version string                                                    | **Required**       |
| `core_module`       | Your main task module                                                 | **Required**       |
| `extra_modules`     | Tuple of additional task modules (each auto-namespaced)               | `()`               |
| `plugin_entrypoint` | Entry point group(s) for plugin discovery                             | `name`             |
| `config_dir`        | Where to look for personal tasks (e.g. `~/.config/<name>`)            | `~/.config/{name}` |
| `include_project`   | Load project-specific `*.tasks.py` modules                            | `True`             |
| `include_local`     | Load `tasks.py` from the current directory (under `local.` namespace) | `True`             |
| `ewok_modules`      | Include Ewok's own internal modules (not in use yet)                  | `True`             |

### Ewok extensions to `@task()`

In addition to the standard `@task()` parameters from Invoke/Fabric, Ewok supports:

| Parameter  | Type                   | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
|------------|------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `flags`    | `dict[str, list[str]]` | Adds extra CLI flags for boolean-style behavior. Example:<br> `@task(flags={'exclude': ['--exclude', '-x'], 'as_json': ['--json']})` enables calling your task like:<br> `myapp mytask --exclude --json`.                                                                                                                                                                                                                                                                              |
| `hookable` | `Optional[bool]`       | Controls whether the task can participate in "hook" chaining behavior:<ul><li>`True` → This is a *core* task that can trigger other tasks with the same name (e.g., from plugins or local modules) **after** it runs.</li><li>`False` → This task should *not* be hooked, even if another with the same name exists. Typically used in plugins or local overrides.</li><li>`None` (default) → Default behavior: core tasks don't hook; plugin/local tasks **can** be hooked.</li></ul> |

---

## Plugin System

Ewok supports plugin discovery via Python entry points.

### Example: Add a plugin

1. Create a plugin package with its own `tasks.py`.
2. In the plugin’s `pyproject.toml`:

```toml
[project.entry-points.myapp] # 'myapp' matches your app name
demo = "my_plugin.tasks"     # 'demo' becomes the namespace
```

This exposes the plugin’s tasks as `demo.taskname`.

### Discovering under multiple entry point names

```python
app = App(
    name="myapp",
    version="1.0.0",
    core_module=tasks,
    plugin_entrypoint=("myapp", "myapp.plugins"),
)
```

---

## Command Organization

Task sources and their namespaces:

| Source                      | Example Call           | Namespace |
|-----------------------------|------------------------|-----------|
| Core task module            | `myapp hello`          | *global*  |
| Plugin via entry point      | `myapp demo.taskname`  | `demo.`   |
| Project-local `tasks.py`    | `myapp local.taskname` | `local.`  |
| Namespaced `dev.tasks.py`   | `myapp dev.taskname`   | `dev.`    |
| Personal `~/.config/myapp/` | `myapp taskname`       | *global*  |

---

## CLI Flags

Control which task sources are loaded at runtime:

| Flag            | Description                                 |
|-----------------|---------------------------------------------|
| `--no-local`    | Skip `tasks.py` in the current directory    |
| `--no-project`  | Skip namespaced `*.tasks.py` in the project |
| `--no-personal` | Skip `~/.config/<name>/tasks.py`            |
| `--no-plugins`  | Skip plugin discovery entirely              |
| `--no-packaged` | Skip installed plugin packages              |
| `--no-ewok`     | Skip Ewok’s own built-in modules            |

---

## Full Example

```python
# src/my_package/__init__.py
from pathlib import Path
from ewok import App
from . import tasks, extra, slow
from .__about__ import __version__

app = App(
    name="my-app",
    version=__version__,
    core_module=tasks,  # not namespaced
    extra_modules=(extra, slow),  # namespaced as `extra.` and `slow.`
    plugin_entrypoint=("my-app", "myapp_plugins"),
    # only if it differs from 'name', can also be multiple or None to disable
    config_dir=Path("~/custom-config/my-app"),  # only if it differs from 'name', can also be a Path or None to disable
    include_project=True,  # to include project-specific tasks.py and <namespace>.tasks.py files
    include_local=True,  # to include tasks.py in the local cwd and up your file tree (../tasks.py etc.)
)
```

---

## Examples & Resources

* 🧪 Minimal template: [ewok-example](https://github.com/educationwarehouse/ewok-example)
* 🧰 Real-world usage: [edwh](https://github.com/educationwarehouse/edwh)

---

## License

[MIT License](LICENSE.txt)
