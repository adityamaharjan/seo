"""A real robots.txt parser, following RFC 9309.

The previous implementation was a substring scan for ``"disallow: /\\n"``
anywhere in the file. That is wrong in both directions: it flagged any site
that blocks a single scraper in its own group (``User-agent: AhrefsBot`` /
``Disallow: /``) as blocking everyone, and it missed a genuine site-wide block
served with CRLF line endings, a trailing space, or no space after the colon.
Since a critical verdict here caps the whole report, a false positive costs the
user most of their score.

Rules are therefore grouped by user-agent the way the standard describes, and
matched with the longest-rule-wins precedence Google implements.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import unquote, urlparse

# Directives we care about. Anything else (crawl-delay, host, ...) is ignored
# rather than treated as a rule.
_RULE_DIRECTIVES = {"allow", "disallow"}


@dataclass(frozen=True)
class Rule:
    """One Allow/Disallow line, pre-compiled for matching."""

    allow: bool
    path: str
    pattern: re.Pattern[str]

    @property
    def specificity(self) -> int:
        """Length of the rule path, which decides precedence between rules."""
        return len(self.path)


@dataclass
class Group:
    """A block of rules sharing one or more user-agent lines."""

    agents: list[str] = field(default_factory=list)
    rules: list[Rule] = field(default_factory=list)

    @property
    def is_wildcard(self) -> bool:
        return "*" in self.agents


def _compile(path: str) -> re.Pattern[str]:
    """Translate a robots path pattern into a regex.

    Only ``*`` (any run of characters) and a trailing ``$`` (end anchor) are
    special; everything else is literal. Matching is a prefix match unless the
    pattern is ``$``-anchored.
    """
    anchored = path.endswith("$")
    body = path[:-1] if anchored else path
    regex = "".join(".*" if ch == "*" else re.escape(ch) for ch in body)
    return re.compile("^" + regex + ("$" if anchored else ""))


def _split_directive(line: str) -> tuple[str, str] | None:
    """Split ``Name: value`` tolerantly, or return None for a non-directive.

    Comments are stripped, the name is lowercased, and a missing space after
    the colon is fine — ``Disallow:/`` is as valid as ``Disallow: /``.
    """
    line = line.split("#", 1)[0].strip()
    if not line or ":" not in line:
        return None
    name, _, value = line.partition(":")
    return name.strip().lower(), value.strip()


class RobotsTxt:
    """Parsed robots.txt, queryable per user-agent."""

    def __init__(self, groups: list[Group], sitemaps: list[str]) -> None:
        self.groups = groups
        self.sitemaps = sitemaps

    @classmethod
    def parse(cls, text: str) -> "RobotsTxt":
        groups: list[Group] = []
        sitemaps: list[str] = []
        current: Group | None = None
        # Consecutive User-agent lines share the rules that follow them, so a
        # new agent line only starts a new group if rules have been seen since.
        accepting_agents = False

        # splitlines() handles LF, CRLF and CR alike, which the old scan did not.
        for raw in text.splitlines():
            directive = _split_directive(raw)
            if directive is None:
                continue
            name, value = directive

            if name == "user-agent":
                if current is None or not accepting_agents:
                    current = Group()
                    groups.append(current)
                    accepting_agents = True
                current.agents.append(value.lower())
            elif name in _RULE_DIRECTIVES:
                if current is None:
                    # Rules before any user-agent line are not valid, but are
                    # common enough in the wild to be worth treating as global.
                    current = Group(agents=["*"])
                    groups.append(current)
                accepting_agents = False
                # An empty Disallow means "nothing is disallowed" and carries no
                # rule; an empty Allow is likewise a no-op.
                if value:
                    current.rules.append(
                        Rule(allow=(name == "allow"), path=value, pattern=_compile(value))
                    )
            elif name == "sitemap" and value:
                sitemaps.append(value)

        return cls(groups, sitemaps)

    def group_for(self, agent: str) -> Group | None:
        """The group that applies to ``agent``: most specific name, else ``*``.

        Agent matching is a case-insensitive substring test on the product
        token, which is how crawlers identify their own group.
        """
        agent = agent.lower()
        best: tuple[int, Group] | None = None
        wildcard: Group | None = None
        for group in self.groups:
            for name in group.agents:
                if name == "*":
                    if wildcard is None:
                        wildcard = group
                elif name in agent and (best is None or len(name) > best[0]):
                    best = (len(name), group)
        return best[1] if best else wildcard

    def allows(self, path: str, agent: str = "*") -> bool:
        """Whether ``agent`` may crawl ``path``.

        Precedence follows Google's implementation: the longest matching rule
        wins, and Allow beats Disallow on an exact tie. With no group and no
        matching rule, crawling is permitted.
        """
        group = self.group_for(agent)
        if group is None or not group.rules:
            return True

        path = unquote(path) or "/"
        winner: Rule | None = None
        for rule in group.rules:
            if not rule.pattern.match(path):
                continue
            if (
                winner is None
                or rule.specificity > winner.specificity
                # Tie goes to Allow, so Allow: /x and Disallow: /x permits.
                or (rule.specificity == winner.specificity and rule.allow)
            ):
                winner = rule
        return winner.allow if winner else True

    def blocks_entire_site(self, agent: str = "*") -> bool:
        """Whether ``agent`` is shut out of the whole site, not just some paths.

        A bare ``Disallow: /`` blocks everything, but an accompanying ``Allow``
        carves out an exception, so the site is only fully closed when no Allow
        rule applies to this group.
        """
        group = self.group_for(agent)
        if group is None or not group.rules:
            return False
        if any(rule.allow for rule in group.rules):
            return False
        return any(
            not rule.allow and rule.path.rstrip("*").rstrip() == "/"
            for rule in group.rules
        )

    def blocked_agents(self) -> list[str]:
        """Named agents (never ``*``) that are blocked from the entire site.

        Blocking scrapers and AI crawlers by name is routine and healthy; it is
        reported as context so a user can see why their file mentions the
        directive at all, but it never affects the score.
        """
        blocked: list[str] = []
        for group in self.groups:
            if group.is_wildcard or any(rule.allow for rule in group.rules):
                continue
            if any(
                not rule.allow and rule.path.rstrip("*").rstrip() == "/"
                for rule in group.rules
            ):
                blocked.extend(a for a in group.agents if a != "*")
        return sorted(set(blocked))


def path_of(url: str) -> str:
    """The path-and-query a robots rule is matched against."""
    parts = urlparse(url)
    return (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
