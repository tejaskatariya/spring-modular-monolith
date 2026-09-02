#!/usr/bin/env python3
"""onTransition hook (policy: block): move the Linear card to the lane named
after the state Juno is about to commit. Runs BEFORE the commit, so a failed
lane write leaves both Juno and the board at the old state.

Items without Linear metadata (for example from-file.py demo items) are a
no-op success, so the offline pipeline flows.
"""

import sys

from lib import fail, linear, require_context

context = require_context()
meta = context.get("meta") or {}
issue_id = meta.get("linearIssueId")
if not issue_id:
    print("no linear issue attached; skipping lane move")
    sys.exit(0)

to_state = context.get("toState")
if not to_state:
    fail("no toState in context")

state_id = (meta.get("linearStateIds") or {}).get(to_state)
if not state_id:
    fail('no Linear lane is named "' + to_state + '" on this team')

linear(
    """mutation Move($issueId: String!, $stateId: String!) {
    issueUpdate(id: $issueId, input: { stateId: $stateId }) { success }
  }""",
    {"issueId": issue_id, "stateId": state_id},
)
print("moved " + context["item"]["id"] + " to " + to_state)
