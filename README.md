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

In addition to the standard `@task()` parameters from Invoke/Fabric, Ewok supports two additional parameters:

#### The `flags` Parameter

**Type**: `dict[str, list[str]]`

The `flags` parameter allows you to define additional CLI flags that map to boolean function parameters:

```python
@task(flags={'exclude': ['--exclude', '-x'], 'as_json': ['--json']})
def deploy(c: Context, exclude: bool = False, as_json: bool = False):
    """Deploy with optional exclusions and JSON output"""
    if exclude:
        print("Excluding test files...")
    c.run("echo 'some shell command'")
    if as_json:
        return {"status": "deployed"}
    print("Deployment complete!")
```

This enables calling your task with the defined flags:

```bash
myapp deploy --exclude --json
# or using the short form:
myapp deploy -x --json
```

#### The `hookable` Parameter

**Type**: `Optional[bool]`

Controls whether the task can participate in "hook" chaining behavior:

- **`True`** → This is a *core* task that can trigger other tasks with the same name (e.g., from plugins or local modules) **after** it runs.
- **`False`** → This task should *not* be hooked, even if another with the same name exists. Typically used in plugins or local overrides.
- **`None` (default)** → Default behavior: core tasks don't hook; plugin/local tasks **can** be hooked.

##### Example

Here's a concrete example showing how the hook system works with a `setup` task:

**Core module** (`tasks.py`):
```python
@task(hookable=True)
def setup(c: Context):
    """Core setup - runs first, triggers other setup tasks"""
    print("🔧 Core setup: Creating docker-compose.yml and .env files...")
    # Create essential config files that every project needs
    create_docker_compose()
    create_env_template()
```

**Local tasks** (`tasks.py` in project directory):
```python
@task  # hookable=None (default) - will be called after core
def setup(c: Context):
    """Project-specific setup questions"""
    print("🏠 Local setup: Configuring project settings...")
    check_env(
        key="DOMAIN",
        default="localhost",
        comment="The hosting domain for this project"
    )
    set_file_permissions()
```

**Plugin** (backup plugin):
```python
@task  # hookable=None (default) - will be called after core  
def setup(c: Context):
    """Backup plugin setup"""
    print("💾 Backup setup: Configuring backup storage...")
    check_env(
        key="BACKUP_PATH",
        default=get_default_backup_path(),
        comment="Where backups should be stored"
    )
```

**Plugin with non-hookable task (e.g. `nuke.tasks.py`)**:
```python
@task(hookable=False)  # This will NOT run automatically
def setup(c: Context):
    """Destructive setup - only run when explicitly called"""
    print("💣 Nuclear setup: This will destroy existing config!")
    # Only runs when called as: myapp nuke.setup
```

**Execution flow** for this example when you run `myapp setup`:

1. **Core setup** runs first (creates base files)
2. **Plugin setup** runs next (configures backup storage)  
3. **Local setup** runs last (asks project-specific questions)
4. **`setup` with `hookable=False` does NOT run** (because it's explicitly excluded from the hook chain)

This allows you to build layered functionality where each level can extend the setup process, but dangerous or unrelated operations require explicit invocation.

---

## Plugin System

Ewok supports plugin discovery via Python entry points, allowing you to extend your CLI with external packages.

### Example: Creating a Plugin

1. **Create a plugin package** with its own `tasks.py`:

```python
# my_plugin/tasks.py
from ewok import task

@task
def greet(c):
    """Plugin greeting task"""
    print("Hello from the demo plugin!")

@task
def status(c):
    """Show plugin status"""
    print("Demo plugin is active")
```

2. **Register the plugin** in the plugin's `pyproject.toml`:

```toml
[project.entry-points.myapp]  # Must match your main app's name
demo = "my_plugin.tasks"      # 'demo' becomes the namespace prefix
```

The entry point name (`demo` in this example) determines the namespace. Tasks from this plugin will be accessible as `demo.greet`, `demo.status`, etc.

3. **Install and use the plugin**:

```bash
# Install the plugin package
uv pip install my-plugin-package

# Use the plugin tasks
myapp demo.greet   # Calls the greet task from the demo namespace
myapp demo.status  # Calls the status task from the demo namespace
```

### Discovering under multiple entry point names

You can configure your app to discover plugins from multiple entry point groups:

```python
app = App(
    name="myapp",
    version="1.0.0",
    core_module=tasks,
    plugin_entrypoint=("myapp", "myapp_plugins"),  # Search both groups
)
```

This allows plugin authors to register under either `myapp` or `myapp_plugins` entry points.

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
