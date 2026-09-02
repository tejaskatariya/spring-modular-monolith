#!/usr/bin/env python3
"""Script step: push the item's branch and open a pull request for the
documents. Uses the gh CLI, which reads GITHUB_TOKEN itself.

Exit 0 -> success route; JSON stdout may carry meta for later scripts.
"""

import json
import subprocess
import sys

from lib import fail, git, require_context

context = require_context()
item = context["item"]
branch = "juno/" + item["id"]

git("push", "--set-upstream", "origin", branch)

body = (
    "Documents produced by Juno for " + item["id"] + ".\n\n"
    "Spec, tech spec, and story decomposition are under artifacts/" + item["id"] + "/."
)
result = subprocess.run(
    [
        "gh",
        "pr",
        "create",
        "--head",
        branch,
        "--title",
        item["id"] + ": " + item["title"],
        "--body",
        body,
    ],
    stdout=subprocess.PIPE,
    encoding="utf-8",
    check=False,
)
if result.returncode != 0:
    fail("gh pr create exited " + str(result.returncode))

lines = [line for line in result.stdout.strip().split("\n") if line]
pr_url = lines[-1] if lines else None
sys.stdout.write(json.dumps({"outcome": "success", "prUrl": pr_url}, separators=(",", ":")))
