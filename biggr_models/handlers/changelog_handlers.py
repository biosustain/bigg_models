"""Handler for the /changelog page, rendered from biggr_models/CHANGELOG.md."""

import re
from os import path

import markdown

from biggr_models.handlers import utils

CHANGELOG_PATH = path.join(path.dirname(path.dirname(__file__)), "CHANGELOG.md")

# "## 0.1.0 - 2026-10-28 - Pre-release" (the label part is optional)
RELEASE_HEADING = re.compile(
    r"^##\s+(?P<version>\d+\.\d+\.\d+\S*)\s+-\s+(?P<date>\d{4}-\d{2}-\d{2})"
    r"(?:\s+-\s+(?P<label>.+?))?\s*$"
)


def parse_changelog(text):
    """Split the changelog into releases.

    Returns a list of dicts with version, date, label and the release body
    rendered to HTML, newest first (in file order). Everything before the
    first release heading is the preamble and is not shown on the page.
    """
    releases = []
    current = None
    for line in text.splitlines():
        match = RELEASE_HEADING.match(line)
        if match:
            current = {**match.groupdict(), "lines": []}
            releases.append(current)
        elif line.startswith("## "):
            raise ValueError(f"Malformed release heading in CHANGELOG.md: {line!r}")
        elif current is not None:
            current["lines"].append(line)

    for release in releases:
        body = "\n".join(release.pop("lines"))
        release["html"] = markdown.markdown(body)
    return releases


def load_changelog():
    with open(CHANGELOG_PATH, encoding="utf-8") as f:
        return parse_changelog(f.read())


class ChangelogHandler(utils.BaseHandler):
    template = utils.env.get_template("changelog.html")

    def get(self):
        self.return_result({"releases": load_changelog()})
