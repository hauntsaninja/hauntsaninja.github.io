import argparse
import shutil
import string
from pathlib import Path

import mistletoe
import tomli
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
{GITHUB_MARKDOWN}
<title>Shantanu</title>
</head>
{GITHUB_CSS}
<body class="markdown-body body-sizing body-padding">
$$$${{home}}
{GOAT_COUNTER}
</body>
</html>
""")

HEADER = f"""
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

        info = tomli.loads("".join(contents[1:md_index]))
        info["url"] = post.with_suffix(".html").name
        post_infos.append(info)

        md_contents = [f"# {info['title']}\n\n", f"*{info['date']}*\n"] + contents[md_index + 1 :]
        md_html = mistletoe.markdown(md_contents, renderer=PygmentsRenderer)

        with open(args.dst / info["url"], "w") as f:
            f.write(POST.substitute(article=md_html, title=info["title"]))

    home_markdown = """
# Hello!

I'm Shantanu. I can often be found under the username hauntsaninja — in particular, find me at:
- [Github](https://github.com/hauntsaninja)
- [Twitter](https://twitter.com/hauntsaninja)
- [LinkedIn](https://www.linkedin.com/in/shantanu-jain-yes-that-one/)
- username at gmail dot com

I contribute to open source software, particularly in the Python and static type checking
ecosystems. I'm a maintainer of [mypy](https://github.com/python/mypy) and
[typeshed](https://github.com/python/typeshed), a [CPython](https://github.com/python/cpython)
core developer, and contributor to several other projects. Check out this fun
[Python CLI tool](https://github.com/hauntsaninja/pyp) I made.

I currently work on language models at [OpenAI](https://openai.com), studying what data to feed them
and building infrastructure to train them. Prior to that, I worked at [Quora](https://www.quora.com/).

---

Here's a list of posts on this blog:
"""
    for info in post_infos:
        home_markdown += f"- [{info['title']}]({info['url']})\n"

    with open(args.dst / "index.html", "w") as f:
        f.write(HOME.substitute(home=mistletoe.markdown(home_markdown)))
