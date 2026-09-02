#!/usr/bin/env python3
"""onComplete hook: ask a model why this item took the rounds it did, and write
the answer into feedback.md below Juno's sentinel (ADR-0016).

Juno renders the facts: which dimensions stayed weak, which findings repeated,
and which files each step read. It never says what to change in those files.
This fills that in, once, when the item is finished.

Everything above the sentinel is Juno's and is rewritten after every step.
Everything below it is preserved, which is why this appends there rather than
rewriting the file.
"""

import json
import os
import subprocess
import sys

from lib import require_context

SENTINEL = "<!-- juno:analysis -->"

# The model gets the rendered reports and nothing else: no tools, no filesystem,
# one turn. It is summarising what it was handed, not investigating.
CLAUDE_ARGS = ["--allowedTools", "", "--max-turns", "1"]

PROMPT = """You are reviewing one work item that has just finished running \
through an automated pipeline. Below are two machine-generated reports about it.

Write a short analysis, at most six sentences, for the engineer who owns the \
prompts and rubrics this pipeline runs on. Say why you think the steps that \
took several rounds struggled, and what you would change in the named files to \
make them converge sooner. Be specific about which file and what edit. If the \
reports do not give you enough to say anything useful, say that instead of \
guessing.

Do not repeat the numbers back; the reader has them directly above what you \
write.

# report.md

{report}

# feedback.md

{feedback}
"""


def read(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read()
    except OSError:
        return ""


def multi_round_steps(root):
    """Steps with more than one round directory.

    Read from the directory names rather than from the rendered markdown, so a
    change to the report's wording cannot silently switch this off.
    """
    counts = {}
    try:
        steps = os.listdir(root)
    except OSError:
        return []
    for step in steps:
        step_dir = os.path.join(root, step)
        if not os.path.isdir(step_dir):
            continue
        rounds = [name for name in os.listdir(step_dir) if name.startswith("round-")]
        if len(rounds) > 1:
            counts[step] = len(rounds)
    return sorted(counts)


def succeed(**fields):
    print(json.dumps(dict(outcome="success", **fields), separators=(",", ":")))
    sys.exit(0)


context = require_context()
run_dir = os.environ.get("JUNO_RUN_DIR", "")
if not run_dir:
    succeed(note="no JUNO_RUN_DIR; nothing to analyse")

# An item hook's run directory is .juno/runs/<item>/<hookPoint>, so the item's
# run root, where the reports live, is its parent.
root = os.path.dirname(run_dir)
feedback_path = os.path.join(root, "feedback.md")
feedback = read(feedback_path)

if SENTINEL not in feedback:
    # Either the file is not there or it predates ADR-0016. Appending without
    # the sentinel would put the analysis somewhere the next rewrite erases.
    succeed(note="feedback.md has no analysis marker; nothing written")

if not multi_round_steps(root):
    # Every step converged first time. The rendered file already says there is
    # nothing to tune, and paying for a model call to agree is waste.
    succeed(note="every step converged on its first round; no analysis needed")

prompt = PROMPT.format(report=read(os.path.join(root, "report.md")), feedback=feedback)
try:
    result = subprocess.run(
        ["claude", "-p", prompt, *CLAUDE_ARGS],
        capture_output=True,
        encoding="utf-8",
        check=False,
    )
except OSError as error:
    # No CLI on this machine. The hook is wired onFailure: ignore, but saying so
    # in the outcome is more use than a stack trace.
    succeed(note="claude CLI not available: " + str(error))

analysis = result.stdout.strip()
if result.returncode != 0 or not analysis:
    print(result.stderr.strip()[:500], file=sys.stderr)
    succeed(note="claude exited " + str(result.returncode) + " with no analysis")

head, _, _tail = feedback.partition(SENTINEL)
with open(feedback_path, "w", encoding="utf-8") as handle:
    handle.write(head + SENTINEL + "\n\n## Analysis\n\n" + analysis + "\n")

succeed(analysedSteps=multi_round_steps(root))
