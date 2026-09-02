#!/usr/bin/env python3
"""Script step: fetch the external documents this item needs and write them to
artifacts/<id>/context/external.md, which the spec step then reads through its
`context:` list (ADR-0011).

Which pages to fetch comes from meta.confluencePageIds when the trigger put them
there (a different page per item) and from CONFLUENCE_PAGE_IDS otherwise (the
same page for every item).

Items with no Confluence configured still get a file, so the offline pipeline
flows end to end and the spec step's pre-flight gate passes.
"""

import json
import os
import sys

from lib import confluence, fail, require_context

OUTPUT_TEMPLATE = "artifacts/{0}/context/external.md"


def wanted_page_ids(context):
    """Per-item ids from the tracker win; the environment is the fixed-document
    fallback. Both are lists of Confluence page ids.
    """
    meta = context.get("meta") or {}
    from_meta = meta.get("confluencePageIds")
    if isinstance(from_meta, list) and from_meta:
        return [str(page_id) for page_id in from_meta]
    configured = os.environ.get("CONFLUENCE_PAGE_IDS", "")
    return [part.strip() for part in configured.split(",") if part.strip()]


def page_to_markdown(page):
    """The title as a heading and the body beneath it. Confluence returns
    storage-format HTML; this keeps it as-is rather than half-converting it,
    because the model reads it either way and a lossy conversion would hide
    content.
    """
    title = page.get("title") or page.get("id") or "untitled"
    body = ((page.get("body") or {}).get("storage") or {}).get("value") or ""
    return "## " + str(title) + "\n\n" + body


def write(path, text):
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def succeed(**fields):
    print(json.dumps(dict(outcome="success", **fields), separators=(",", ":")))
    sys.exit(0)


context = require_context()
output_path = OUTPUT_TEMPLATE.format(context["item"]["id"])

# Pinned per item (ADR-0011 Decision 4): the documents are fetched once and read
# unchanged from then on, so a re-run of this pass must not fetch again.
if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
    succeed(contextPages=[], note="already fetched")

page_ids = wanted_page_ids(context)
sections = []
fetched = []
for page_id in page_ids:
    page = confluence("/wiki/api/v2/pages/" + page_id + "?body-format=storage")
    if page is None:
        # No CONFLUENCE_BASE_URL: stop here and take the offline path below.
        sections = []
        fetched = []
        break
    sections.append(page_to_markdown(page))
    fetched.append(page_id)

if fetched:
    write(output_path, "# External context\n\n" + "\n\n".join(sections) + "\n")
    succeed(contextPages=fetched)

# Nothing was fetched, either because no pages are configured or because no
# Confluence is. Write the reason rather than an empty file: pre-flight treats a
# blank file as absent, and the next step's model should see why it has nothing.
if not os.environ.get("CONFLUENCE_BASE_URL"):
    reason = "CONFLUENCE_BASE_URL is not set, so no external documents were fetched."
elif not page_ids:
    reason = (
        "No pages were requested for this item: the trigger set no "
        "meta.confluencePageIds and CONFLUENCE_PAGE_IDS is empty."
    )
else:
    fail("no pages were fetched for " + context["item"]["id"])
    reason = ""  # unreachable; fail() exits

write(output_path, "# External context\n\n" + reason + "\n")
succeed(contextPages=[], note=reason)
