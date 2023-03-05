import argparse
import datetime
import shutil
from pathlib import Path

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


html = f"""
<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <title>Home</title>
  </head>
  <body>
    <h1>Hello World!</h1>
    <p>{datetime.datetime.now()}</p>
  </body>
</html>
"""

post_html = """
<!doctype html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.1.0/github-markdown.min.css" integrity="sha512-KUoB3bZ1XRBYj1QcH4BHCQjurAZnCO3WdrswyLDtp7BMwCw7dPZngSLqILf68SGgvnWHTD5pPaYrXi6wiRJ65g==" crossorigin="anonymous" referrerpolicy="no-referrer" />
</head>
<style>
.markdown-body {
    box-sizing: border-box;
    min-width: 200px;
    max-width: 980px;
    margin: 0 auto;
    padding: 45px;
}

@media (max-width: 767px) {
    .markdown-body {
        padding: 15px;
    }
}
</style>
<article class="markdown-body">
%(article)s
</article>

<script src="https://utteranc.es/client.js"
        repo="hauntsaninja/blog_comments"
        issue-term="pathname"
        label="comment"
        theme="preferred-color-scheme"
        crossorigin="anonymous"
        async>
</script>

</html>
"""


def main():
    root = Path(__file__).parent.parent

    parser = argparse.ArgumentParser()
    parser.add_argument("--src", type=Path, default=root)
    parser.add_argument("--dst", type=Path, default=root / "_site")
    args = parser.parse_args()

    shutil.rmtree(args.dst, ignore_errors=True)
    args.dst.mkdir(parents=True)
    with open(args.dst / "index.html", "w") as f:
        f.write(html)

    posts_dir = args.src / "posts"
    for post in posts_dir.glob("*.md"):
        with open(post) as f:
            md_html = mistletoe.markdown(f, renderer=PygmentsRenderer)
        with open(args.dst / post.relative_to(posts_dir).with_suffix(".html").name, "w") as f:
            f.write(post_html % {"article": md_html})
