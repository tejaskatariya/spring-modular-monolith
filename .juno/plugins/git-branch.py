#!/usr/bin/env python3
"""beforeStep hook (round 1 only, via `when`): put the working tree on the
item's branch, creating it from the current HEAD the first time.
"""

from lib import git, require_context, try_git

context = require_context()
branch = "juno/" + context["item"]["id"]

if try_git("rev-parse", "--verify", branch) is not None:
    git("checkout", branch)
else:
    git("checkout", "-b", branch)
print("on branch " + branch)
