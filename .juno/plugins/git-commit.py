#!/usr/bin/env python3
"""afterStep hook: commit whatever the round produced under artifacts/<item>.

No changes is a normal outcome, not a failure.
"""

import sys

from lib import git, require_context, try_git

context = require_context()
directory = "artifacts/" + context["item"]["id"]

try_git("add", "--", directory)
if try_git("diff", "--cached", "--quiet") is not None:
    print("nothing to commit under " + directory)
    sys.exit(0)

step = context.get("stepId") or "step"
rounds = context.get("round")
label = "?" if rounds is None else str(rounds)
git("commit", "-m", context["item"]["id"] + ": " + step + " round " + label)
print("committed " + directory)
