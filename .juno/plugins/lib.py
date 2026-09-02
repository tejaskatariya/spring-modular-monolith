"""Shared helpers for the example plugins.

Juno knows nothing about this file: it invokes each plugin as a command, and
the plugins share code the way any scripts would. Standard library only, and
conservative syntax, so the system python3 can run them (ADR-0004 Decision 7).
"""

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

_ENV_LINE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$")
_QUOTED = re.compile(r"^(['\"])(.*)\1$")


def _load_env_file():
    """Load the sibling .env file (.juno/.env in a scaffolded repo, examples/.env
    here) so plugin credentials can live next to the config. Variables already
    set in the environment always win, and Juno itself never reads this file.
    """
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if line.strip().startswith("#"):
                continue
            match = _ENV_LINE.match(line)
            if match is None:
                continue
            key, raw = match.group(1), match.group(2)
            if key not in os.environ:
                unquoted = _QUOTED.match(raw)
                os.environ[key] = unquoted.group(2) if unquoted else raw


_load_env_file()


def read_context():
    """The JUNO_CONTEXT payload: item, step id, round, score, states, runDir, meta."""
    path = os.environ.get("JUNO_CONTEXT")
    if not path:
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def fail(message):
    print(message, file=sys.stderr)
    sys.exit(1)


def require_context():
    """The context every hook and script step expects; exits when it is absent."""
    context = read_context()
    if context is None:
        fail("JUNO_CONTEXT is not set")
    return context


def linear(query, variables=None):
    """One Linear GraphQL request. Uses LINEAR_API_KEY from the environment;
    Juno never reads it.
    """
    key = os.environ.get("LINEAR_API_KEY")
    if not key:
        fail("LINEAR_API_KEY is not set")
    payload = json.dumps({"query": query, "variables": variables or {}}).encode("utf-8")
    request = urllib.request.Request(
        "https://api.linear.app/graphql",
        data=payload,
        headers={"content-type": "application/json", "authorization": key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        fail("Linear API error: HTTP " + str(error.code))
    except urllib.error.URLError as error:
        fail("Linear API error: " + str(error.reason))
    if body.get("errors"):
        fail("Linear API error: " + json.dumps(body["errors"]))
    return body["data"]


def confluence(path):
    """One Confluence REST GET. Uses CONFLUENCE_BASE_URL and
    CONFLUENCE_API_TOKEN from the environment; Juno never reads either.

    Returns None when no base URL is configured, so a plugin can degrade to an
    offline path instead of failing the step.
    """
    base = os.environ.get("CONFLUENCE_BASE_URL")
    if not base:
        return None
    token = os.environ.get("CONFLUENCE_API_TOKEN")
    if not token:
        fail("CONFLUENCE_BASE_URL is set but CONFLUENCE_API_TOKEN is not")
    request = urllib.request.Request(
        base.rstrip("/") + path,
        headers={"accept": "application/json", "authorization": "Bearer " + token},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        fail("Confluence API error: HTTP " + str(error.code) + " for " + path)
    except urllib.error.URLError as error:
        fail("Confluence API error: " + str(error.reason))


def git(*args):
    """Run a git command, inheriting stderr; returns stdout. Exits non-zero on failure."""
    result = subprocess.run(
        ["git"] + list(args), stdout=subprocess.PIPE, encoding="utf-8", check=False
    )
    if result.returncode != 0:
        fail("git " + " ".join(args) + " exited " + str(result.returncode))
    return result.stdout.strip()


def try_git(*args):
    """Like git(), but returns None instead of exiting when the command fails."""
    result = subprocess.run(
        ["git"] + list(args), capture_output=True, encoding="utf-8", check=False
    )
    return result.stdout.strip() if result.returncode == 0 else None


def load_yaml(text, path):
    """Parse a YAML document.

    The standard library has no YAML parser, so this uses whichever of PyYAML
    or ruamel.yaml is installed for the interpreter running the plugin. Both
    read YAML 1.2 here: PyYAML through its safe loader and ruamel through
    typ="safe". If neither is present the plugin fails with a message naming
    the fix, rather than guessing at the document's meaning.
    """
    try:
        import yaml  # type: ignore[import-not-found]

        return yaml.safe_load(text)
    except ImportError:
        pass
    try:
        from ruamel.yaml import YAML  # type: ignore[import-not-found]

        return YAML(typ="safe").load(text)
    except ImportError:
        fail(
            "cannot read " + path + ": no YAML parser is available. "
            "Install one for this interpreter, for example `pip install PyYAML`."
        )
