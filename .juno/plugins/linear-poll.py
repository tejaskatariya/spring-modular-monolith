#!/usr/bin/env python3
"""Trigger: emits Linear issues sitting in the intake lane with the marker label.

Environment (all read here, never by Juno):
  LINEAR_API_KEY    required
  LINEAR_TEAM_KEY   required, e.g. "ENG"
  JUNO_TRIGGER_LANE lane (workflow state name) that starts work, default "Specifying"
  JUNO_MARKER_LABEL label that opts an issue in, default "juno"
  JUNO_CURSOR       set by Juno: the cursor this script last emitted

Board convention: the team's Linear lanes are named after Juno's states, so an
issue's lane name is a valid Juno state and later scripts can move cards by name.
"""

import json
import os
import sys

from lib import fail, linear

team_key = os.environ.get("LINEAR_TEAM_KEY")
if not team_key:
    fail("LINEAR_TEAM_KEY is not set")
lane = os.environ.get("JUNO_TRIGGER_LANE") or "Specifying"
label = os.environ.get("JUNO_MARKER_LABEL") or "juno"
raw_cursor = os.environ.get("JUNO_CURSOR")
cursor = json.loads(raw_cursor) if raw_cursor else None

issue_filter = {
    "team": {"key": {"eq": team_key}},
    "state": {"name": {"eq": lane}},
    "labels": {"name": {"eq": label}},
}
if isinstance(cursor, dict) and cursor.get("updatedAfter"):
    issue_filter["updatedAt"] = {"gt": cursor["updatedAfter"]}

data = linear(
    """query Poll($filter: IssueFilter) {
    issues(filter: $filter, first: 50, orderBy: updatedAt) {
      nodes {
        id identifier title description updatedAt
        state { name }
        team { id states { nodes { id name } } }
        labels { nodes { name } }
      }
    }
  }""",
    {"filter": issue_filter},
)

nodes = data["issues"]["nodes"]
items = []
for issue in nodes:
    items.append(
        {
            "id": issue["identifier"],
            "title": issue["title"],
            "body": issue["description"] or "",
            "state": issue["state"]["name"],
            "labels": [entry["name"] for entry in issue["labels"]["nodes"]],
            "dependsOn": [],
            # Everything a later script needs travels in meta, opaque to Juno.
            "meta": {
                "linearIssueId": issue["id"],
                "linearTeamId": issue["team"]["id"],
                "linearStateIds": {
                    state["name"]: state["id"] for state in issue["team"]["states"]["nodes"]
                },
            },
        }
    )

output = {}
timestamps = sorted(issue["updatedAt"] for issue in nodes)
if timestamps:
    output["cursor"] = {"updatedAfter": timestamps[-1]}
output["items"] = items
sys.stdout.write(json.dumps(output, separators=(",", ":")))
