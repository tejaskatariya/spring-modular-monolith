#!/usr/bin/env python3
"""A deterministic evaluator: no model, no rubric, just rules.

Juno passes the deliverable under evaluation as $JUNO_OUTPUT. Exit 0 means the
round converged; any other exit fails it, and this script's stdout becomes the
findings handed to the next generator round. Printing JSON with a `findings`
array gives Juno one finding per problem instead of a blob.
"""

import json
import os
import sys

from lib import load_yaml

path = os.environ.get("JUNO_OUTPUT")
if not path:
    print("JUNO_OUTPUT is not set", file=sys.stderr)
    sys.exit(1)


def reject(findings):
    print(json.dumps({"findings": findings}, separators=(",", ":")))
    sys.exit(1)


try:
    with open(path, encoding="utf-8") as handle:
        document = load_yaml(handle.read(), path)
except OSError as error:
    reject([path + " cannot be read: " + str(error)])
except Exception as error:  # noqa: BLE001 - any parse failure is one finding
    reject([path + " is not valid YAML: " + str(error)])

stories = (document or {}).get("stories")
if not isinstance(stories, list) or not stories:
    reject([path + ' has no "stories" list.'])

findings = []
titles = set()
for index, story in enumerate(stories):
    story = story or {}
    title = story.get("title")
    label = '"' + str(title) + '"' if title else "story " + str(index + 1)
    if not title:
        findings.append(label + " has no title.")
    elif title in titles:
        findings.append(label + " is duplicated.")
    else:
        titles.add(title)

    criteria = story.get("acceptanceCriteria")
    if not isinstance(criteria, list) or not criteria:
        findings.append(label + " has no acceptance criteria.")
    estimate = story.get("estimate")
    if estimate and estimate not in ("S", "M", "L"):
        findings.append(label + ' has estimate "' + str(estimate) + '"; use S, M or L.')

# Dependencies must name real stories and must not form a cycle.
by_title = {story["title"]: story for story in stories if (story or {}).get("title")}
for story in by_title.values():
    for dependency in story.get("dependsOn") or []:
        if dependency not in by_title:
            findings.append(
                '"'
                + story["title"]
                + '" depends on "'
                + str(dependency)
                + '", which is not a story here.'
            )

state = {}


def walk(title, trail):
    if state.get(title) == "done":
        return
    if state.get(title) == "visiting":
        findings.append("Dependency cycle: " + " -> ".join(trail + [title]) + ".")
        return
    state[title] = "visiting"
    for dependency in by_title.get(title, {}).get("dependsOn") or []:
        if dependency in by_title:
            walk(dependency, trail + [title])
    state[title] = "done"


for title in list(by_title):
    walk(title, [])

if findings:
    reject(findings)
print(str(len(stories)) + " stories check out.")
