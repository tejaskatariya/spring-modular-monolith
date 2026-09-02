#!/usr/bin/env python3
"""Script step: read the story decomposition the decompose step produced and
create one Linear sub-issue per story. Prints a JSON outcome so the created
ids land in meta for later scripts.

Demo items with no Linear metadata succeed without creating anything, so the
offline pipeline flows end to end.
"""

import json
import sys

from lib import fail, linear, load_yaml, require_context

context = require_context()
path = "artifacts/" + context["item"]["id"] + "/stories.yaml"

try:
    with open(path, encoding="utf-8") as handle:
        document = load_yaml(handle.read(), path)
except OSError as error:
    document = None
    fail("cannot read " + path + ": " + str(error))

stories = (document or {}).get("stories")
if not isinstance(stories, list) or not stories:
    fail(path + " contains no stories")

meta = context.get("meta") or {}
issue_id = meta.get("linearIssueId")
if not issue_id:
    print(
        json.dumps(
            {
                "outcome": "success",
                "storyIds": [],
                "note": "offline: no linear issue attached",
            },
            separators=(",", ":"),
        )
    )
    sys.exit(0)

story_ids = []
for story in stories:
    criteria = story.get("acceptanceCriteria") or []
    description = "\n".join(
        [story.get("description") or "", "", "## Acceptance criteria"]
        + ["- " + str(criterion) for criterion in criteria]
    )
    data = linear(
        """mutation Create($input: IssueCreateInput!) {
      issueCreate(input: $input) { success issue { id identifier } }
    }""",
        {
            "input": {
                "teamId": meta.get("linearTeamId"),
                "parentId": issue_id,
                "title": story.get("title"),
                "description": description,
            }
        },
    )
    story_ids.append(data["issueCreate"]["issue"]["identifier"])

print(json.dumps({"outcome": "success", "storyIds": story_ids}, separators=(",", ":")))
