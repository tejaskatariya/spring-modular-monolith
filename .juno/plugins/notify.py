#!/usr/bin/env python3
"""Per-step hook sample: prints a one-line progress message and nothing else.

Attach it to a single step's `hooks:` block when only that step should carry
the attachment; the workflow-level hooks run around every step.
"""

import sys

from lib import read_context

context = read_context()
if context is None:
    print("[notify] no context")
    sys.exit(0)

rounds = "" if context.get("round") is None else " round " + str(context["round"])
score = "" if context.get("score") is None else " (score " + str(context["score"]) + ")"
print("[notify] " + context["item"]["id"] + ": " + (context.get("stepId") or "?") + rounds + score)
