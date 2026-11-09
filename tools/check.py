# -*- coding: utf-8 -*-
"""静态自检：id 交叉引用、标签闭合、CSS 括号、JS 语法。"""
import re
import pathlib
import subprocess
import sys
from html.parser import HTMLParser

ROOT = pathlib.Path(__file__).resolve().parent.parent
html_path = ROOT / "web" / "index.html"
html = html_path.read_text(encoding="utf-8")

blocks = re.findall(r"<script>(.*?)</script>", html, re.S)
if not blocks:
    sys.exit("找不到 <script> 块")
js = "\n;\n".join(blocks)
js_file = ROOT / "_check.js"
js_file.write_text(js, encoding="utf-8")

html_ids = set(re.findall(r'id="([^"]+)"', html))
used = set(re.findall(r'\$\("([^"]+)"\)', js))
problems = []

print(f"HTML id 数量: {len(html_ids)}   JS 引用: {len(used)}")
missing = sorted(used - html_ids)
if missing:
    problems.append(f"JS 引用了不存在的 id: {missing}")

css = re.search(r"<style>(.*?)</style>", html, re.S).group(1)
if css.count("{") != css.count("}"):
    problems.append(f"CSS 括号不平衡 {{={css.count('{')} }}={css.count('}')}")

# 服务端要在首页把加速令牌注入进来，占位符不能丢
if "__BOOST_TOKEN__" not in html:
    problems.append("页面里缺少 __BOOST_TOKEN__ 占位符，加速接口的令牌无法注入")

# 栅格区域一致性：每张卡片的 grid-area 必须在 grid-template-areas 里出现过
tpl_areas = set()
for blk in re.findall(r"grid-template-areas:(.*?);", css, re.S):
    for row in re.findall(r'"([^"]*)"', blk):
        tpl_areas.update(row.split())
card_areas = dict(re.findall(r"\.(card-[a-z]+)\{grid-area:([a-z]+)\}", css))
if not card_areas:
    problems.append("没找到卡片 grid-area 定义")
for cls, area in card_areas.items():
    if area not in tpl_areas:
        problems.append(f"{cls} 的 grid-area『{area}』不在任何 grid-template-areas 里")
# 每种布局的模板都要覆盖全部卡片（只检查页面级模板，卡片内部还有自己的子栅格）
for i, blk in enumerate(re.findall(r"grid-template-areas:(.*?);", css, re.S)):
    names = set()
    for row in re.findall(r'"([^"]*)"', blk):
        names.update(row.split())
    if "hdr" not in names:
        continue
    miss = sorted(set(card_areas.values()) - names)
    if miss:
        problems.append(f"第 {i + 1} 套 grid-template-areas 缺少区域: {miss}")

# 主题变量完整性：页面用到的每个 --token，每套皮肤都必须定义（否则那套皮肤下会掉色）
base_tokens = set()
root_blk = re.search(r":root\{(.*?)\}", css, re.S)
if root_blk:
    base_tokens = set(re.findall(r"(--[a-z0-9-]+)\s*:", root_blk.group(1)))

theme_blocks = re.findall(r'html\[data-theme="([a-z]+)"\]\{([^}]*)\}', css, re.S)
if not theme_blocks:
    problems.append("没找到任何皮肤定义 html[data-theme=...]")
else:
    # 把皮肤定义块本身剔除后再统计"用到了哪些变量"
    css_without_themes = css
    for _name, body in theme_blocks:
        css_without_themes = css_without_themes.replace(body, "")
    used_tokens = set(re.findall(r"var\((--[a-z0-9-]+)", css_without_themes))
    # --eh/--ew 由 JS 在运行时写入（CSS 里只是 var(--eh, 默认值)），不需要皮肤声明
    used_tokens -= {"--eh", "--ew"}
    for name, body in theme_blocks:
        declared = set(re.findall(r"(--[a-z0-9-]+)\s*:", body))
        miss = sorted(used_tokens - base_tokens - declared)
        if miss:
            problems.append(f"皮肤『{name}』缺少变量: {miss}")

for tag in ("div", "section", "header", "span", "b", "i", "button", "canvas", "svg"):
    opens = len(re.findall(rf"<{tag}[\s>]", html))
    closes = len(re.findall(rf"</{tag}>", html))
    if opens != closes:
        problems.append(f"<{tag}> 开合不匹配 open={opens} close={closes}")


VOID = {"meta", "link", "br", "img", "input", "hr", "source"}


class Checker(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.err = []

    def handle_starttag(self, tag, attrs):
        if tag not in VOID:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        pass

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if self.stack and self.stack[-1] == tag:
            self.stack.pop()
        else:
            self.err.append((tag, self.stack[-4:]))


c = Checker()
c.feed(html)
if c.stack:
    problems.append(f"未闭合标签: {c.stack}")
if c.err:
    problems.append(f"标签错配: {c.err}")

node = pathlib.Path(
    r"C:\Users\25235\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\node\bin\node.exe"
)
res = subprocess.run([str(node), "--check", str(js_file)], capture_output=True, text=True)
if res.returncode != 0:
    problems.append("JS 语法错误:\n" + res.stderr.strip())

print("JS 语法: " + ("OK" if res.returncode == 0 else "ERROR"))
print("结果: " + ("全部通过 ✓" if not problems else "发现问题"))
for p in problems:
    print("  ✗ " + p)
js_file.unlink(missing_ok=True)
