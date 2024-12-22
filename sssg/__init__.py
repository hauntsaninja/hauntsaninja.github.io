import argparse
import datetime
import shutil
import string
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path

import dateutil.parser
import mistletoe
from mistletoe import HTMLRenderer
from pygments import highlight
from pygments.formatters.html import HtmlFormatter
from pygments.lexers import get_lexer_by_name as get_lexer
from pygments.lexers import guess_lexer
from pygments.styles import get_style_by_name as get_style


class PygmentsRenderer(HTMLRenderer):
    formatter = HtmlFormatter()
    formatter.noclasses = True

    def __init__(self, *extras, style="default"):
        super().__init__(*extras)
        self.formatter.style = get_style(style)

    def render_block_code(self, token):
        code = token.children[0].content
        lexer = get_lexer(token.language) if token.language else guess_lexer(code)
        return highlight(code, lexer, self.formatter)


class Template(string.Template):
    delimiter = "$$$$"


GITHUB_MARKDOWN = """<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.1.0/github-markdown.min.css" integrity="sha512-KUoB3bZ1XRBYj1QcH4BHCQjurAZnCO3WdrswyLDtp7BMwCw7dPZngSLqILf68SGgvnWHTD5pPaYrXi6wiRJ65g==" crossorigin="anonymous" referrerpolicy="no-referrer" />"""

GITHUB_CSS = """
<style>
.body-sizing {
    box-sizing: border-box;
    min-width: 200px;
    max-width: 980px;
    margin: 0 auto;
}
.body-padding {
    padding: 45px;
}
@media (max-width: 767px) {
    .body-padding {
        padding: 15px;
    }
}
</style>
"""

GOAT_COUNTER = """
<script data-goatcounter="https://hauntsaninja.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script>
"""

HOME = Template(f"""
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="google-site-verification" content="NcC5nFv5YhOoK4HzZ04YD-OjQ-jKLzT9_AQK1NyT-9w" />
{GITHUB_MARKDOWN}
<link rel="alternate" type="application/atom+xml" title="Shantanu's Blog" href="/feed.xml">
<title>Shantanu</title>
{GITHUB_CSS}
</head>
<body class="markdown-body body-sizing body-padding">
$$$${{home}}
{GOAT_COUNTER}
</body>
</html>
""")

HEADER = """
<header class="markdown-body body-sizing">
<nav am-layout="horizontal">
<a href="/" style="padding-right: 10px">Home</a>
<a href="https://github.com/hauntsaninja" style="padding-right: 10px">Github</a>
<a href="https://twitter.com/hauntsaninja" style="padding-right: 10px">Twitter</a>
<a href="https://www.linkedin.com/in/shantanu-jain-yes-that-one/" style="padding-right: 10px">LinkedIn</a>
</nav>
</header>
"""

UTTERANCES = """
<script src="https://utteranc.es/client.js"
        repo="hauntsaninja/blog_comments"
        issue-term="pathname"
        label="comment"
        theme="preferred-color-scheme"
        crossorigin="anonymous"
        async>
</script>
"""

POST = Template(f"""
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{GITHUB_MARKDOWN}
<title>$$$${{title}}</title>
</head>
{GITHUB_CSS}
<body class="markdown-body body-sizing body-padding">
{HEADER}
<article>
$$$${{article}}
</article>
{UTTERANCES}
{GOAT_COUNTER}
</body>
</html>
""")


def main():
    root = Path(__file__).parent.parent

    parser = argparse.ArgumentParser()
    parser.add_argument("--src", type=Path, default=root)
    parser.add_argument("--dst", type=Path, default=root / "_site")
    args = parser.parse_args()

    shutil.rmtree(args.dst, ignore_errors=True)
    args.dst.mkdir(parents=True)

    post_infos = []
    posts_dir = args.src / "posts"
    for post in posts_dir.glob("*.md"):
        with open(post) as f:
            contents = f.readlines()

        assert contents[0] == "---\n"
        md_index = contents.index("---\n", 1)

        info = tomllib.loads("".join(contents[1:md_index]))
        info["slug"] = post.stem
        info["location"] = post.stem + ".html"
        info["dt"] = dateutil.parser.parse(info["date"]).replace(tzinfo=datetime.timezone.utc)
        post_infos.append(info)

        md_contents = [f"# {info['title']}\n\n", f"*{info['date']}*\n"] + contents[md_index + 1 :]
        md_html = mistletoe.markdown(md_contents, renderer=PygmentsRenderer)

        with open(args.dst / info["location"], "w") as f:
            f.write(POST.substitute(article=md_html, title=info["title"]))
    del post
    post_infos.sort(key=lambda info: info["dt"], reverse=True)

    home_markdown = """
# Hello!

I'm Shantanu. I can often be found under the username hauntsaninja — in particular, find me at:
- [Github](https://github.com/hauntsaninja)
- [Bluesky](https://bsky.app/profile/hauntsaninja.bsky.social) / [Twitter](https://twitter.com/hauntsaninja)
- [LinkedIn](https://www.linkedin.com/in/shantanu-jain-yes-that-one/)
- username at gmail dot com
- [RSS feed](/feed.xml)

I contribute to open source software, particularly in the Python and static type checking
ecosystems. I'm a maintainer of [mypy](https://github.com/python/mypy) and
[typeshed](https://github.com/python/typeshed), a [CPython](https://github.com/python/cpython)
core developer, and contributor to several other projects. Check out this fun
[Python CLI tool](https://github.com/hauntsaninja/pyp) I made.

I've worked on language models at [OpenAI](https://openai.com) since 2020, studying what data to feed them
and building infrastructure to train them. Prior to that, I worked at [Quora](https://www.quora.com/).

---

Here's a list of posts on this blog:
"""
    for info in post_infos:
        home_markdown += f"- [{info['title']}]({info['location']})\n"

    with open(args.dst / "index.html", "w") as f:
        f.write(HOME.substitute(home=mistletoe.markdown(home_markdown)))

    # Atom feed
    # https://validator.w3.org/feed/docs/atom.html
    root = ET.Element("feed", xmlns="http://www.w3.org/2005/Atom")
    ET.SubElement(root, "title").text = "Shantanu's blog"
    ET.SubElement(root, "id").text = "https://hauntsaninja.github.io/"
    ET.SubElement(root, "updated").text = max(info["dt"] for info in post_infos).isoformat("T")
    ET.SubElement(root, "link", href="https://hauntsaninja.github.io/feed.xml", rel="self")
    ET.SubElement(ET.SubElement(root, "author"), "name").text = "Shantanu"

    for info in post_infos:
        entry = ET.SubElement(root, "entry")
        # https://validator.w3.org/feed/docs/error/InvalidTAG.html
        ET.SubElement(entry, "id").text = f"tag:hauntsaninja.github.io,2024:{info["slug"]}"
        ET.SubElement(entry, "title").text = info["title"]
        ET.SubElement(entry, "updated").text = info["dt"].isoformat("T")
        ET.SubElement(ET.SubElement(entry, "author"), "name").text = "Shantanu"
        ET.SubElement(entry, "link", href=f"https://hauntsaninja.github.io/{info['location']}", rel="alternate")
        if "summary" in info:
            ET.SubElement(entry, "summary").text = info["summary"]

    with open(args.dst / "feed.xml", "wb") as f:
        f.write(ET.tostring(root, xml_declaration=True, encoding="utf-8"))

    # Sitemap
    root = ET.Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
    for info in post_infos:
        url = ET.SubElement(root, "url")
        ET.SubElement(url, "loc").text = f"https://hauntsaninja.github.io/{info['location']}"
        ET.SubElement(url, "lastmod").text = info["dt"].isoformat()
    with open(args.dst / "sitemap.xml", "wb") as f:
        f.write(ET.tostring(root, xml_declaration=True, encoding="utf-8"))

    # robots.txt
    with open(args.dst / "robots.txt", "w") as f:
        f.write("User-agent: *\nAllow: /\nSitemap: https://hauntsaninja.github.io/sitemap.xml")
