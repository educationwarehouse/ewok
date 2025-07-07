import traceback
import typing

import fabric
import invoke
from fabric import task as fabric_task
from invoke import task as invoke_task
from termcolor import cprint


def format_frame(frame: traceback.FrameSummary):
    """
    Formats and prints details of a traceback frame.

    This function takes a traceback frame and prints its details including the file name,
    line number, function name, and the actual line of code. The output is styled with
    colored text for better readability.

    Args:
        frame (traceback.FrameSummary): The traceback frame to format and print.
    """
    cprint(
        f'  File "{frame.filename}", line {frame.lineno}, in {frame.name}', color="blue"
    )
    cprint(f"    {frame.line}", color="blue")  # actual code


def task_with_warning(
    to_replace: tuple[str, typing.Callable],
    *alternatives: str,
    exceptions: tuple[str, ...] = (),
):
    old_name, old_fn = to_replace

    # only show error once per file:
    files_seen = set()

    def wrapper(*a, **kw):
        stack = traceback.extract_stack(limit=2)
        call_frame = stack[0]
        call_file = call_frame.filename

        # exceptions:
        if not (call_file in files_seen or call_file.endswith(exceptions)):
            files_seen.add(call_file)
            cprint(
                f"WARN: `{old_name}.task` used instead of `ewok.task`; "
                f"This could lead to issues due to missing features.",
                color="yellow",
            )

            alternative_tasks = " or ".join(f"`{alt}.task`" for alt in alternatives)
            cprint(f"HINT: Consider replacing with {alternative_tasks}", color="cyan")

            format_frame(call_frame)
            print()

        return old_fn(*a, **kw)

    return wrapper


def monkeypatch_invoke(
    *alternatives: str,
    patch_invoke: bool = True,
    patch_fabric: bool = True,
    exceptions: tuple[str, ...] = (
        "/site-packages/invoke/tasks.py",
        "/site-packages/fabric/tasks.py",
    ),
):
    if not alternatives:
        alternatives = ["ewok"]

    if patch_invoke:
        invoke.task = task_with_warning(
            ("invoke", invoke_task), *alternatives, exceptions=exceptions
        )
    if patch_fabric:
        fabric.task = task_with_warning(
            ("fabric", fabric_task), *alternatives, exceptions=exceptions
        )
