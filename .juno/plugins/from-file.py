#!/usr/bin/env python3
"""Trigger: reads examples/work-item.json so the whole workflow runs offline.

Contract: print one JSON object { cursor?, items: WorkItem[] } on stdout.
"""

import json
import os
import sys

path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "work-item.json")
with open(path, encoding="utf-8") as handle:
    document = json.load(handle)  # fail loudly on broken fixtures
sys.stdout.write(json.dumps(document, separators=(",", ":")))
