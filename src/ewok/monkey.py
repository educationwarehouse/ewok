import traceback

import invoke
from invoke import task
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


def task_with_warning(*alternatives: str):
    def wrapper(*a, **kw):
        stack = traceback.extract_stack(limit=2)
        cprint(
            "WARN: `invoke.task` used instead of `ewok.task`; This could lead to issues due to missing features.",
            color="yellow",
        )

        alternative_tasks = " or ".join(f"`{alt}.task`" for alt in alternatives)
        cprint(f"HINT: Consider replacing with {alternative_tasks}", color="cyan")

        format_frame(stack[0])
        print()
        return task(*a, **kw)

    return wrapper


def monkeypatch_invoke(*alternatives: str):
    if not alternatives:
        alternatives = ["ewok"]

    invoke.task = task_with_warning(*alternatives)
