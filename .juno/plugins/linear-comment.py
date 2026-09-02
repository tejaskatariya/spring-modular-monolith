#!/usr/bin/env python3
"""afterStep hook (policy: ignore): leave a progress comment on the Linear
issue. Best-effort by design; the workflow never waits on a comment.
"""

import sys

from lib import linear, read_context

context = read_context()
issue_id = ((context or {}).get("meta") or {}).get("linearIssueId")
if not issue_id:
    print("no linear issue attached; skipping comment")
    sys.exit(0)

score = "no score" if context["score"] is None else "score " + str(context["score"])
body = (
    "Juno: step `"
    + str(context["stepId"])
    + "` round "
    + str(context["round"])
    + " finished ("
    + score
    + ")."
)
linear(
    """mutation Comment($issueId: String!, $body: String!) {
    commentCreate(input: { issueId: $issueId, body: $body }) { success }
  }""",
    {"issueId": issue_id, "body": body},
)
print("commented")
