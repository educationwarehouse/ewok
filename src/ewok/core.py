"""
# usage:
>>> from .improved_invoke import improved_task as task # noqa
>>> @task(flags={})
>>> def something(): ...
"""

import inspect
import typing as t
import warnings
from typing import Any, Callable, Iterable, Optional

import invoke
from docstring_parser import parse as parse_docstring
from fabric import Connection
from invoke import Argument, Collection
from invoke.context import Context
from invoke.tasks import task as invoke_task
from typing_extensions import Unpack

from .monkey import monkeypatch_invoke

type AnyDict = dict[str, Any]
type TaskFn = Callable[[Context], Any] | Callable[..., Any]

P = t.ParamSpec("P")
R = t.TypeVar("R")

monkeypatch_invoke()


def extract_arg_doc(docstring: str, arg_name: str):
    doc = parse_docstring(docstring)
    for param in doc.params:
        if param.arg_name != arg_name:
            continue

        return param.description

    return None


class TaskOptions(t.TypedDict, total=False):
    name: Optional[str]
    aliases: Iterable[str]
    positional: Optional[Iterable[str]]
    optional: Iterable[str]
    default: bool
    auto_shortflags: bool
    help: Optional[AnyDict]
    pre: Optional[list[TaskFn]]
    post: Optional[list[TaskFn]]
    autoprint: bool
    iterable: Optional[Iterable[str]]
    incrementable: Optional[Iterable[str]]
    flags: dict[str, Iterable[str]] | None
    hookable: Optional[bool]


class TaskCallable(t.Protocol):
    def __call__(
        self, **_: Unpack[TaskOptions]
    ) -> Callable[
        [Callable[P, R]],
        Callable[P, R],
    ]: ...


def tasks(ctx: Context) -> Collection:
    """
    Provides functionality to retrieve a collection of tasks associated with the
    application namespace from the given context. The function extracts the
    namespace details from the application configuration bound to the context
    and returns it.
    """
    app = ctx.config.app

    return app.namespace


def namespaces(ctx: Context):
    """
    Retrieve and return the namespace collections.

    This function takes a context object, typically used to manage the execution
    environment or configuration in a task management system. It retrieves a
    collection of tasks and returns the associated namespace collections.
    """
    collection = tasks(ctx)

    return collection.collections


def find_namespace(ctx: Context, about: str) -> Collection | None:
    """
    Finds and retrieves a namespace given a context and a specific identifier.

    This function looks up a namespace in the given context using the provided
    identifier. If the identifier is not found in the available namespaces,
    the function returns None.
    """

    return namespaces(ctx).get(about)


class Task(invoke.Task[TaskCallable]):
    """
    Improved version of Invoke Task where you can set custom flags for command line arguments.
    This allows you to specify aliases, rename (e.g. --json for 'as_json')  and custom short flags (--exclude = -x)
    """

    _flags: dict[str, list[str]]

    def __init__(
        self,
        body: TaskCallable,
        name: Optional[str] = None,
        aliases: Iterable[str] = (),
        positional: Optional[Iterable[str]] = None,
        optional: Iterable[str] = (),
        default: bool = False,
        auto_shortflags: bool = True,
        help: Optional[AnyDict] = None,  # noqa
        pre: Optional[list[TaskFn]] = None,
        post: Optional[list[TaskFn]] = None,
        autoprint: bool = False,
        iterable: Optional[Iterable[str]] = None,
        incrementable: Optional[Iterable[str]] = None,
        # new:
        flags: dict[str, Iterable[str]] | None = None,
        hookable: Optional[bool] = None,
    ):
        self._flags = flags or {}
        self.hookable = hookable

        super().__init__(
            body=body,
            name=name,
            aliases=tuple(aliases),
            positional=positional,
            optional=optional,
            default=default,
            auto_shortflags=auto_shortflags,
            help=help,
            pre=pre,  # type: ignore
            post=post,  # type: ignore
            autoprint=autoprint,
            iterable=iterable,
            incrementable=incrementable,
        )

    def arg_opts(self, name: str, default: str, taken_names: Iterable[str]) -> AnyDict:
        """Get argument options.

        Args:
            name (str): The name of the argument.
            default (str): The default value of the argument.
            taken_names (Iterable[str]): Names that have already been taken.

        Returns:
            AnyDict: A dictionary of argument options.
        """
        opts = super().arg_opts(
            name=name, default=default, taken_names=set(taken_names)
        )
        help_str = (
            self.help.pop(name, None)
            or opts.get("help")
            or extract_arg_doc(self.body.__doc__, name)
        )
        opts["help"] = opts.get("help") or help_str

        if flags := self._flags.get(name):
            opts["names"] = list(flags)
            for synonym in list(flags):
                self.help[synonym] = help_str

        return opts

    def get_arguments(
        self, ignore_unknown_help: Optional[bool] = None
    ) -> list[Argument]:
        return super().get_arguments(ignore_unknown_help=True)

    def _execute_subtask(self, ctx: Context, task: TaskFn, *args, **kwargs):
        """Execute a subtask with provided context and arguments.

        Args:
            ctx (Context): The context to pass to the task.
            task (TaskFn): The task function to execute.
            *args: Positional arguments for the task.
            **kwargs: Keyword arguments for the task.
        """
        sig = inspect.signature(task)
        task_args = [ctx]  # Start with the context
        task_kwargs = {}

        # Collect positional arguments
        param_names = list(sig.parameters.keys())
        for i, param in enumerate(param_names[1:], start=0):  # Skip 'ctx'
            if i < len(args):
                task_args.append(args[i])
            elif sig.parameters[param].default is sig.empty:
                raise ValueError(f"Missing required argument: {param}")

        # Collect keyword arguments
        for param in param_names[1:]:
            if param in kwargs:
                task_kwargs[param] = kwargs[param]

        # Call the task with the prepared arguments
        return task(*task_args, **task_kwargs)

    def find_task_across_namespaces(self, ctx: Context) -> dict[str, t.Self]:
        return {
            ns.name: task
            for ns in namespaces(ctx).values()
            if (task := ns.tasks.get(self.name))
        }

    def _run_hooks(self, ctx: Context, *args, **kwargs):
        """Run hooks for the current instance.

        Args:
            ctx (Context): The context to pass to the hooks.
            *args: Positional arguments for the hooks.
            **kwargs: Keyword arguments for the hooks.
        """
        for namespace, task in self.find_task_across_namespaces(ctx).items():
            if task is not self and getattr(task, "hookable", False) is not False:
                try:
                    subresult = self._execute_subtask(ctx, task, *args, **kwargs)
                except Exception as e:
                    warnings.warn(
                        f"Failed running subtask {namespace}.{task.name}: {e}.",
                        source=e,
                        category=RuntimeWarning,
                    )
                    continue

                if isinstance(ctx["result"], dict) and isinstance(subresult, dict):
                    ctx["result"].update(subresult)
                elif subresult is not None:
                    ctx["result"] = subresult

    def __call__(self, ctx: Context | Connection, *args, **kwargs):
        """Invoke the callable instance.

        Args:
            ctx (Context): The context to pass.
            *args: Positional arguments.
            **kwargs: Keyword arguments.

        Returns:
            The result of the superclass call.
        """
        # ctx.get works for Context but not for Connection!
        setattr(
            ctx, "result", getattr(ctx, "result", {})
        )  # ctx["result"] = ctx.get("result") or {}

        result = super().__call__(ctx, *args, **kwargs)

        if isinstance(ctx["result"], dict) and isinstance(result, dict):
            ctx["result"].update(result)
        elif result is not None:
            ctx["result"] = result

        if self.hookable:
            self._run_hooks(ctx, *args, **kwargs)

        return ctx["result"]


def task(*fn: Optional[TaskCallable], **options: Unpack[TaskOptions]) -> TaskCallable:
    """
    Marks wrapped callable object as a valid Invoke task.

    This function may be called without any parentheses if no extra options need to be
    specified. Otherwise, the following keyword arguments are allowed in the
    parenthesized form:

    Args:
        name (str): Default name to use when binding to a `.Collection`. Useful for
            avoiding Python namespace issues (i.e. when the desired CLI level name
            can't or shouldn't be used as the Python level name.)
        aliases (List[str]): Specify one or more aliases for this task, allowing it to be
            invoked as multiple different names. For example, a task named ``mytask``
            with a simple ``@task`` wrapper may only be invoked as ``"mytask"``.
            Changing the decorator to be ``@task(aliases=['myothertask'])`` allows
            invocation as ``"mytask"`` *or* ``"myothertask"``.
        positional (Iterable[str]): Iterable overriding the parser's automatic "args with no
            default value are considered positional" behavior. If a list of arg
            names, no args besides those named in this iterable will be considered
            positional. (This means that an empty list will force all arguments to be
            given as explicit flags.)
        optional (Iterable[str]): Iterable of argument names, declaring those args to
            have optional values. Such arguments may be
            given as value-taking options (e.g. ``--my-arg=myvalue``, wherein the
            task is given ``"myvalue"``) or as Boolean flags (``--my-arg``, resulting
            in ``True``).
        iterable (Iterable[str]): Iterable of argument names, declaring them to build
            iterable values.
        incrementable (Iterable[str]): Iterable of argument names, declaring them to
            increment their values.
        default (bool): Boolean option specifying whether this task should be its
            collection's default task (i.e. called if the collection's own name is
            given.)
        auto_shortflags (bool): Whether or not to automatically create short
            flags from task options; defaults to True.
        help (Dict[str, str]): Dict mapping argument names to their help strings. Will be
            displayed in ``--help`` output. For arguments containing underscores
            (which are transformed into dashes on the CLI by default), either the
            dashed or underscored version may be supplied here.
        pre (List[TaskCallable]): Lists of task objects to execute prior to the wrapped
            task whenever it is executed.
        post (List[TaskCallable]): Lists of task objects to execute after the wrapped
            task whenever it is executed.
        autoprint (bool): Boolean determining whether to automatically print this
            task's return value to standard output when invoked directly via the CLI.
            Defaults to False.
        flags (dict[str, list[str]]): Mapping of flag names that modify task behavior.
                               e.g. `@task(flags={'exclude': ['--exclude', '-x'], 'as_json': ['--json']})`
        hookable (Optional[bool]): Boolean option that controls whether the task can be hooked by plugins.
                                       - **True**: This setting is primarily used by core tasks. It allows the task to look for other tasks (from plugins or local definitions) with the same name and execute them after the main task completes. This enables a cascading execution of tasks, enhancing modularity and reusability.
                                       - **False**: This setting is typically used by local or plugin tasks to indicate that they do not want to be hooked by core tasks, even if they share the same name. This ensures that the task remains isolated and does not trigger any unintended behavior from cascading executions.
                                       - **None** (default): This represents the default behavior. For core tasks, it means that the task will not search for other tasks with the same name to execute. For local or plugin tasks, it allows them to be hooked by other tasks.
        fn (TaskCallable): when you use `@task` without parentheses, this is the function you're decorating.
                            Using `@task()` with parens is recommended for better type-hints.

    If any non-keyword arguments are given, they are taken as the value of the
    ``pre`` kwarg for convenience's sake. (It is an error to give both
    ``*args`` and ``pre`` at the same time.)
    """
    return invoke_task(*fn, **options, klass=Task)
