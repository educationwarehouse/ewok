# Ewok - Education Warehouse Octopus Kit

![Ewok Logo](https://github.com/educationwarehouse/ewok/blob/master/docs/logo.png?raw=true)


[![PyPI version](https://img.shields.io/pypi/v/ewok.svg)](https://pypi.org/project/ewok/)
[![Python versions](https://img.shields.io/pypi/pyversions/ewok.svg)](https://pypi.org/project/ewok/)
[![License](https://img.shields.io/pypi/l/ewok.svg)](https://github.com/educationwarehouse/ewok/blob/main/LICENSE)

Ewok (Education Warehouse Octopus Kit) is a powerful CLI framework built on top of [Invoke](https://www.pyinvoke.org/) and [Fabric](https://www.fabfile.org/) that extends their capabilities with additional features for composable command-line tools.

## Features

- **Multi-source Command Integration**: Like an octopus with many arms, Ewok pulls in commands from multiple sources:
  - Core commands from your main package
  - Plugin commands with their own namespaces
  - Machine-specific commands from `~/.config` directories
  - Project-specific commands from a project's `tasks.py` (namespaced with `local.`)
  - Extra namespaced project-specific commands in `namespace.tasks.py`

- **Plugin System**: Easily extend functionality through a plugin architecture
- **Namespace Management**: Organize commands into logical namespaces
- **Configuration Handling**: Manage application configuration across different locations
- **Task Discovery**: Automatically discover and load tasks from various sources

## Installation
```bash
pip install ewok
```
## Quick Start

Here's a minimal example of creating an Ewok application:
```python
import ewok
from . import tasks

app = ewok.App(
    "myapp",
    version="0.1.0",
    core_module=tasks
)

if __name__ == "__main__":
    app.run()
```
## Creating an Ewok App

The `App` class is the main entry point for creating an Ewok application. It accepts the following parameters:

### Required Parameters

- `name`: The name of your application
- `version`: The version of your application
- `core_module`: The module containing your core tasks

### Optional Parameters

- `extra_modules`: Additional modules containing tasks (default: `()`)
- `plugin_entrypoint`: Entry point(s) for discovering plugins (default: same as `name`)
- `config_dir`: Directory for user-specific configuration (default: `~/.config/{name}`)
- `include_project`: Whether to include project-specific tasks (default: `True`)
- `include_local`: Whether to include local tasks from `tasks.py` (default: `True`)
- `ewok_modules`: Whether to include Ewok built-in modules (default: `True`)

### Example
```python
from ewok import App
from . import tasks, extra, slow  # from tasks.py, extra.py, slow.py
from .__about__ import __version__

app = App(
    name="my-app",
    version=__version__,
    core_module=tasks,           # not namespaced
    extra_modules=(extra, slow), # namespaced as `extra.` and `slow.`
    plugin_entrypoint="myapp", # only if it differs from 'name', can also be multiple or None to disable
    config_dir="myapp",        # only if it differs from 'name', can also be a Path or None to disable
    include_project=True,      # to include project-specific tasks.py and <namespace>.tasks.py files
    include_local=True,        # to include tasks.py in the local cwd and up your file tree (../tasks.py etc.)
)

if __name__ == "__main__":
    app()
```
## Plugin System

Ewok's plugin system allows you to extend your application with additional functionality. 
Plugins are discovered through entry points defined in your project's setup configuration.

### Defining a Plugin

To create a plugin for an Ewok application, you need to:

1. Create a Python package with your plugin's functionality
2. Define an entry point in your `pyproject.toml` file

#### Entry Point Format in `pyproject.toml`
```
toml
[project.entry-points.your-app-name]
plugin_namespace = "your_plugin_package.tasks"
```
For example, for the `my-app` tool defined above:
```
toml
[project.entry-points.myapp]
demo = "myapp_some_plugin.tasks"
```
In this example:
- `myapp` is the plugin entrypoint of the `App()` instance
- `demo` is the plugin's namespace (meaning all commands in the plugin are available as `demo.<somecommand>`)
- `myapp_some_plugin.tasks` is the module path containing the plugin tasks

### Multiple Entry Point Names

You can define multiple entry point names for your application by providing a collection of names to the `plugin_entrypoint` parameter:
```
python
app = App(
    name="myapp",
    version="1.0.0",
    core_module=tasks,
    plugin_entrypoint=("myapp", "myapp.plugins")
)
```
This will look for plugins defined under both the `myapp` and `myapp.plugins` entry points.

## Command Organization

Ewok organizes commands into namespaces:

- **Global namespace**: Commands defined in your core module (-> no namespace)
- **Plugin namespaces**: Commands from plugins (e.g., `demo.command`)
- **Local namespace**: Commands from `tasks.py` in the current directory (e.g., `local.command`)
- **Project namespaces**: Commands from `<namespace>.tasks.py` files (e.g., `<namespace>.command`)

## Example Implementations

### Minimal

For a minimal implementation and template repo, check out the [ewok-example](https://github.com/educationwarehouse/ewok-example) repository.

### Real-World Usage

Ewok is the foundation of the [edwh](https://github.com/educationwarehouse/edwh) tool, which has a comprehensive suite of plugins for various tasks.

## Task Decorators

Define tasks in your modules using the `@task` decorator:
```python
from ewok import task, Context

@task
def hello(c: Context, name: str = "world"):
    """Say hello to someone"""
    print(f"Hello, {name}!")
```

For more information, checkout the documentation of [Invoke](https://docs.pyinvoke.org/en/stable/concepts/invoking-tasks.html) and [Fabric](https://docs.fabfile.org/en/1.10/usage/tasks.html).

## Command-Line Flags

Ewok provides several core command-line flags to control which task sources are loaded:

- `--no-local`: Skip importing `./tasks.py`
- `--no-plugins`: Skip importing plugins from entry points
- `--no-packaged`: Skip importing packaged plugins
- `--no-personal`: Skip importing personal tasks from config directory
- `--no-project`: Skip importing `*.tasks.py` files from the current project
- `--no-ewok`: Skip importing ewok built-in namespaces

## License

[MIT License](LICENSE.txt)
