"""robots.txt parsing.

The previous implementation was a substring scan. These cases are the ones it
got wrong, in both directions, and each one changed a report's score by up to
55 points because a critical verdict here caps the whole report.
"""
import pytest

from app.seo.robots import RobotsTxt, path_of

BLOCK_ALL = "User-agent: *\nDisallow: /\n"


@pytest.mark.parametrize(
    "label,text",
    [
        ("lf line endings", "User-agent: *\nDisallow: /\n"),
        ("crlf line endings", "User-agent: *\r\nDisallow: /\r\n"),
        ("trailing whitespace", "User-agent: *\nDisallow: / \n"),
        ("no space after colon", "User-agent:*\nDisallow:/\n"),
        ("comments and blank lines", "# note\n\nUser-agent: *  # all\nDisallow: /  # root\n"),
        ("no trailing newline", "User-agent: *\nDisallow: /"),
    ],
)
def test_site_wide_block_is_detected_however_it_is_written(label, text):
    robots = RobotsTxt.parse(text)
    assert robots.blocks_entire_site("*") is True
    assert robots.allows("/", "*") is False


@pytest.mark.parametrize(
    "label,text",
    [
        (
            "blocks one seo crawler",
            "User-agent: *\nAllow: /\n\nUser-agent: AhrefsBot\nDisallow: /\n",
        ),
        (
            "blocks an ai crawler",
            "User-agent: *\nDisallow: /admin\n\nUser-agent: GPTBot\nDisallow: /\n",
        ),
        (
            "wordpress default",
            "User-agent: *\nDisallow: /wp-admin/\nAllow: /wp-admin/admin-ajax.php\n",
        ),
        ("empty disallow means allow all", "User-agent: *\nDisallow:\n"),
    ],
)
def test_healthy_files_are_not_treated_as_site_wide_blocks(label, text):
    """Blocking named scrapers is routine and must never cap a report."""
    robots = RobotsTxt.parse(text)
    assert robots.blocks_entire_site("*") is False
    assert robots.allows("/", "*") is True


def test_named_agent_blocks_are_reported_without_affecting_the_wildcard_group():
    robots = RobotsTxt.parse(
        "User-agent: *\nAllow: /\n\nUser-agent: AhrefsBot\nDisallow: /\n"
        "\nUser-agent: GPTBot\nDisallow: /\n"
    )
    assert robots.blocked_agents() == ["ahrefsbot", "gptbot"]
    assert robots.allows("/", "AhrefsBot") is False


def test_longest_matching_rule_wins():
    robots = RobotsTxt.parse(
        "User-agent: *\nDisallow: /wp-admin/\nAllow: /wp-admin/admin-ajax.php\n"
    )
    assert robots.allows("/wp-admin/admin-ajax.php") is True
    assert robots.allows("/wp-admin/options.php") is False


def test_allow_beats_disallow_on_an_exact_tie():
    robots = RobotsTxt.parse("User-agent: *\nDisallow: /x\nAllow: /x\n")
    assert robots.allows("/x") is True


def test_carve_out_means_the_site_is_not_fully_blocked():
    robots = RobotsTxt.parse("User-agent: *\nDisallow: /\nAllow: /public\n")
    assert robots.blocks_entire_site("*") is False
    assert robots.allows("/public/page") is True
    assert robots.allows("/private") is False


def test_wildcards_and_end_anchors():
    robots = RobotsTxt.parse("User-agent: *\nDisallow: /*.pdf$\n")
    assert robots.allows("/docs/manual.pdf") is False
    assert robots.allows("/docs/manual.html") is True


def test_agent_specific_group_wins_over_the_wildcard():
    robots = RobotsTxt.parse(
        "User-agent: *\nAllow: /\n\nUser-agent: Googlebot\nDisallow: /\n"
    )
    assert robots.allows("/", "Googlebot/2.1") is False
    assert robots.allows("/", "SomeOtherBot") is True


def test_consecutive_agent_lines_share_one_group():
    robots = RobotsTxt.parse(
        "User-agent: Googlebot\nUser-agent: Bingbot\nDisallow: /private\n"
    )
    assert robots.allows("/private", "Googlebot") is False
    assert robots.allows("/private", "Bingbot") is False
    assert robots.allows("/private", "DuckDuckBot") is True


def test_sitemaps_are_collected():
    robots = RobotsTxt.parse(
        BLOCK_ALL + "Sitemap: https://example.com/sitemap.xml\n"
        "Sitemap: https://example.com/news.xml\n"
    )
    assert robots.sitemaps == [
        "https://example.com/sitemap.xml",
        "https://example.com/news.xml",
    ]


def test_empty_and_missing_files_allow_everything():
    assert RobotsTxt.parse("").allows("/") is True
    assert RobotsTxt.parse("").blocks_entire_site() is False


def test_path_of_includes_the_query_string():
    assert path_of("https://example.com/a/b?x=1#frag") == "/a/b?x=1"
    assert path_of("https://example.com") == "/"
