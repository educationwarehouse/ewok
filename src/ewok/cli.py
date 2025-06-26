import importlib
import importlib.util
import os
import sys
import typing as t
import warnings
from importlib.metadata import entry_points
from pathlib import Path
from types import ModuleType as Module

from fabric import Config, Executor
from fabric.main import Fab
from invoke import Argument, Call, Collection
from invoke.loader import Loader
from termcolor import cprint

# https://docs.pyinvoke.org/en/stable/concepts/library.html


### extra's tasks ###
def include_plugins(collection: Collection, entrypoint: str) -> None:
    try:
        discovered_plugins = entry_points(group=entrypoint)
    except Exception as e:
        warnings.warn(f"Error locating plugins: {e}")
        return

    try:
        for plugin in discovered_plugins:
            try:
                plugin_module = plugin.load()
            except Exception as e:
                print(f"Error loading plugin {plugin.name}: {e}", file=sys.stderr)
                continue

            plugin_collection = Collection.from_module(plugin_module)
            collection.add_collection(plugin_collection, plugin.name)
    except Exception as e:
        warnings.warn(f"Error loading plugins: {e}")


### included 'plugins' in edwh/local_tasks ###
def include_packaged_plugins(
    collection: Collection,
    package: str,
    local_tasks: Module,
    selection: t.Collection[str] = None,
) -> None:
    # should somehow be defined in the child package

    tasks_dir = Path(local_tasks.__file__).parent
    discovered_plugins = os.listdir(tasks_dir)
    discovered_plugins = [
        _.removesuffix(".py") for _ in discovered_plugins if not _.startswith("_")
    ]
    if selection is not None:
        discovered_plugins = [_ for _ in discovered_plugins if _ in selection]

    for plugin in discovered_plugins:
        # module = importlib.import_module(f".local_tasks.{plugin}", package=package)
        module = importlib.import_module(
            f"{local_tasks.__package__}.{plugin}", package=package
        )
        plugin_collection = Collection.from_module(module)
        collection.add_collection(plugin_collection, plugin)


### tasks in user cwd ###
def include_cwd_tasks(collection: Collection) -> None:
    old_path = sys.path[:]

    for _path in [".", "..", "../.."]:
        path = Path(_path)
        sys.path = [str(path), *old_path]
        try:
            import tasks as local_tasks

            local = Collection.from_module(local_tasks)
            collection.add_collection(local, "local")
            break
        except ImportError as e:
            if "No module named 'tasks'" not in str(e):
                warnings.warn(
                    f"\nWARN: Could not import local tasks.py: `{e}`",
                    # ImportWarning, # <- will be ignored by most Python installations!
                    source=e,
                )
                print(file=sys.stderr)  # 1 newline padding before actual stdout content

    sys.path = old_path


def collection_from_abs_path(path: str, name: str) -> t.Optional[Collection]:
    try:
        if spec := importlib.util.spec_from_file_location(name, path):
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return Collection.from_module(module)
        else:
            return None

    except Exception as e:
        cprint(
            f"Failed to include personal plugin {name}: {e}",
            file=sys.stderr,
            color="yellow",
        )
        return None


### custom ~/.config/edwh/tasks.py and ~/.config/edwh/namespace.tasks.py commands
def include_personal_tasks(collection: Collection, config: Path) -> None:
    config.mkdir(exist_ok=True, parents=True)

    # tasks.py - special case, add to global namespace!
    if any(config.glob("*.py")):
        config_path = str(config)
        if config_path not in sys.path:
            sys.path.append(config_path)

    personal_tasks = config / "tasks.py"
    if personal_tasks.exists() and (
        personal_collection := collection_from_abs_path(
            str(personal_tasks), "_personal_"
        )
    ):
        collection.tasks |= personal_collection.tasks

    # namespace.tasks.py:
    for path in set(config.glob("*.tasks.py")):
        prefix = path.stem.split(".")[0]

        if plugin_collection := collection_from_abs_path(str(path), prefix):
            collection.add_collection(plugin_collection, prefix)


def include_other_project_tasks(collection: Collection) -> None:
    for file in Path().glob("*.tasks.py"):
        namespace = file.stem.split(".")[0]

        spec = importlib.util.spec_from_file_location(
            name=namespace,  # note that ".test" is not a valid module name
            location=file,
        )

        if not (spec and spec.loader):
            continue

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # module = importlib.import_module(file, package="edwh")
        plugin_collection = Collection.from_module(module)
        collection.add_collection(plugin_collection, namespace)


class EwokExecutor(Executor):  # type: ignore
    def expand_calls(self, calls: list[Call], apply_hosts: bool = True) -> list[Call]:
        # always apply hosts (so pre and post are also executed remotely)
        apply_hosts = True
        return t.cast(list[Call], super().expand_calls(calls, apply_hosts))


class App(Fab):
    # = Program

    # Define all the no-flags in one place for reuse
    CUSTOM_FLAGS = {
        "no-local": "Skip importing ./tasks.py",
        "no-plugins": "Skip importing plugins from entry points",
        "no-packaged": "Skip importing packaged plugins from edwh/local_tasks",
        "no-personal": "Skip importing personal tasks from ~/.config/edwh",
        "no-project": "Skip importing *.tasks.py files from the current project",
        "no-ewok": "Skip importing ewok builtin namespaces (plugin.)",
    }

    def __init__(
        self,
        # from invoke, required:
        name: str,
        version: str,
        core_module: Module | Collection,
        # from ewok, optional:
        extra_modules: t.Collection[Module] = (),
        plugin_entrypoint: str | t.Collection[str] | None = (),
        config_dir: str | Path | None = "",
        include_project: bool = True,
        include_local: bool = True,
        ewok_modules: bool | t.Collection[str] = True,
        # from invoke, optional:
        binary: t.Optional[str] = None,
        loader_class: t.Optional[t.Type[Loader]] = None,
        binary_names: t.Optional[list[str]] = None,
        # fron invoke, dangerous to overwrite because of custom logic:
        config_class: t.Optional[t.Type[Config]] = None,
        executor_class: t.Optional[t.Type[Executor]] = None,
    ):
        super().__init__(
            version=version,
            executor_class=executor_class or EwokExecutor,
            config_class=config_class or EwokConfig,
            namespace=core_module
            if isinstance(core_module, Collection)
            else Collection.from_module(core_module),
            name=name,
            binary=binary,
            loader_class=loader_class,
            binary_names=binary_names,
        )

        self.extra_modules = extra_modules

        if plugin_entrypoint is None:
            self.plugin_entrypoints = ()
        elif not plugin_entrypoint:
            # empty but not None, default to 'name'
            self.plugin_entrypoints = [name]
        else:
            self.plugin_entrypoints = (
                [plugin_entrypoint]
                if isinstance(plugin_entrypoint, str)
                else plugin_entrypoint
            )

        if config_dir is None:
            self.config_dir = None
        elif isinstance(config_dir, Path):
            self.config_dir = config_dir
        else:
            self.config_dir = Path.home() / ".config" / (config_dir or name)

        self.include_project = include_project
        self.include_local = include_local
        self.ewok_modules = ewok_modules

    def create_config(self):
        super().create_config()
        self.config.app = self

    def core_args(self):
        return super().core_args() + [
            Argument(
                names=(name,),
                kind=bool,
                help=help_text,
            )
            for name, help_text in self.CUSTOM_FLAGS.items()
        ]

    def print_task_help(self, name: str):
        for flag, arg in self.parser.contexts[name].flags.items():
            # invoke's help uses arg.attr_name instead of flag (key) so patch here:
            arg.attr_name = flag.strip("-")
        return super().print_task_help(name)

    def parse_collection(self):
        import_ewok = self.ewok_modules and not self.args["no-ewok"].value
        import_local = self.include_local and not self.args["no-local"].value
        import_plugins = self.plugin_entrypoints and not self.args["no-plugins"].value
        import_packaged = self.extra_modules and not self.args["no-packaged"].value
        import_project = self.include_project and not self.args["no-project"].value
        import_personal = self.config_dir and not self.args["no-personal"].value

        if import_ewok:
            from . import local_tasks

            # None means all, otherwise the options are filtered.
            selection = (
                None if isinstance(self.ewok_modules, bool) else self.ewok_modules
            )
            include_packaged_plugins(self.namespace, "ewok", local_tasks, selection)

        if import_plugins:
            # pip plugins
            for entrypoint in self.plugin_entrypoints:
                include_plugins(self.namespace, entrypoint)

        if import_packaged:
            # from src.edwh.local_tasks
            for module in self.extra_modules:
                include_packaged_plugins(self.namespace, self.name, module)

        if import_local:
            # from tasks.py and ../tasks.py etc.
            include_cwd_tasks(self.namespace)

        if import_project:
            # *.tasks.py in current project
            include_other_project_tasks(self.namespace)

        if import_personal:
            # ~/.config/edwh/personal.py
            include_personal_tasks(self.namespace, self.config_dir)

        return super().parse_collection()

    def __call__(self, argv: t.Optional[list[str]] = None, exit: bool = True) -> None:
        return self.run(argv=argv, exit=exit)

    def __repr__(self):
        plugin_info = (
            f", plugin entrypoints: {self.plugin_entrypoints}"
            if self.plugin_entrypoints
            else ""
        )
        modules_info = (
            f", extra modules: {len(self.extra_modules)}" if self.extra_modules else ""
        )
        config_info = f", config dir: {self.config_dir}" if self.config_dir else ""
        project_info = f", include project: {self.include_project}"
        local_info = f", include local: {self.include_local}"
        ewok_info = f", ewok modules: {self.ewok_modules}"

        return f"<App '{self.name}' v{self.version}{plugin_info}{modules_info}{config_info}{project_info}{local_info}{ewok_info}>"


class EwokConfig(Config):
    app: App
