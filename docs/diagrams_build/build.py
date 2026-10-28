# -*- coding: utf-8 -*-
"""构建单个 PDF：封面 + 目录 + 每功能「明细页(A3) + 流程图页(A1)」。"""
import html
import re
import subprocess
import sys
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from content import SECTIONS

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "pdf_parts"
BUILD.mkdir(exist_ok=True)
EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")

FONT = '"Microsoft YaHei","Segoe UI",sans-serif'


def svg_size(name):
    text = (ROOT / "svg" / name).read_text(encoding="utf-8", errors="ignore")
    m = re.search(r'viewBox="([\d.\-]+) ([\d.\-]+) ([\d.]+) ([\d.]+)"', text)
    if not m:
        raise RuntimeError(f"no viewBox: {name}")
    return float(m.group(3)), float(m.group(4))


def render(name, body, page_css, extra_css=""):
    doc = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>{html.escape(name)}</title><style>
@page {{ {page_css} }}
* {{ box-sizing: border-box; }}
html, body {{ margin: 0; padding: 0; }}
body {{ font-family: {FONT}; color: #1a2433; -webkit-print-color-adjust: exact; }}
.page {{ padding: 14mm 16mm 12mm; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 0.6pt solid #c9d3df; padding: 3.2pt 5pt; vertical-align: top; }}
thead th {{ background: #e8eef7; font-size: 8.6pt; color: #20344d; text-align: left; }}
thead {{ display: table-header-group; }}
tr {{ break-inside: avoid; }}
{extra_css}
</style></head><body>{body}</body></html>"""
    html_path = BUILD / f"{name}.html"
    pdf_path = BUILD / f"{name}.pdf"
    html_path.write_text(doc, encoding="utf-8")
    profile = BUILD / f"_edge_profile_{name}"
    subprocess.run(
        [str(EDGE), "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
         "--no-first-run", "--disable-extensions",
         f"--user-data-dir={profile}", f"--print-to-pdf={pdf_path}",
         html_path.as_uri()],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=180,
    )
    return pdf_path


def esc(s):
    return html.escape(s, quote=False)


TEXT_CSS = """
h1 { font-size: 20pt; margin: 0 0 2mm; color: #14263d; letter-spacing: .5px; }
.kicker { font-size: 8.5pt; color: #5b7089; letter-spacing: 2px; margin-bottom: 3mm; }
.summary { font-size: 9.6pt; line-height: 1.65; color: #2c3e52; margin: 0 0 4mm;
           background: #f4f7fb; border-left: 3pt solid #4a6fa5; padding: 4mm 5mm; }
h2 { font-size: 10.5pt; margin: 4mm 0 2mm; color: #20344d; }
table.node-table td:nth-child(1) { width: 15mm; font-size: 8.2pt; color: #45607e; }
table.node-table td:nth-child(2) { width: 78mm; font-family: Consolas, "Courier New", monospace;
                                   font-size: 7.8pt; word-break: break-all; }
table.node-table td:nth-child(3) { width: 58mm; font-size: 8.4pt; font-weight: 600; }
table.node-table td:nth-child(4) { font-size: 8.4pt; line-height: 1.45; }
table.branch-table td:nth-child(1) { width: 55mm; font-size: 8.4pt; }
table.branch-table td:nth-child(2) { width: 82mm; font-family: Consolas, "Courier New", monospace;
                                     font-size: 7.8pt; word-break: break-all; }
table.branch-table td:nth-child(3) { font-size: 8.4pt; }
.compact table.node-table td, .compact table.branch-table td { padding: 1.9pt 4pt; }
.compact table.node-table td:nth-child(1) { font-size: 7.6pt; }
.compact table.node-table td:nth-child(2) { font-size: 7.1pt; }
.compact table.node-table td:nth-child(3) { font-size: 7.7pt; }
.compact table.node-table td:nth-child(4) { font-size: 7.7pt; line-height: 1.3; }
.compact table.branch-table td:nth-child(1) { font-size: 7.7pt; }
.compact table.branch-table td:nth-child(2) { font-size: 7.1pt; }
.compact table.branch-table td:nth-child(3) { font-size: 7.7pt; }
.compact .summary { font-size: 8.9pt; line-height: 1.5; padding: 3mm 4mm; margin-bottom: 2.5mm; }
.compact h2 { margin: 2.5mm 0 1.5mm; }
.compact h1 { font-size: 18pt; }
.foot { position: absolute; bottom: 8mm; left: 16mm; right: 16mm; font-size: 7.5pt;
        color: #8a99aa; display: flex; justify-content: space-between; }
.badge { display: inline-block; font-size: 8pt; background: #e8eef7; color: #2b4a70;
         border-radius: 3pt; padding: 1pt 5pt; margin-right: 6pt; }
"""


def section_text(s):
    rows = "".join(
        f"<tr><td>{esc(a)}</td><td>{esc(b)}</td><td>{esc(c)}</td><td>{esc(d)}</td></tr>"
        for a, b, c, d in s["nodes"]
    )
    brows = "".join(
        f"<tr><td>{esc(a)}</td><td>{esc(b)}</td><td>{esc(c)}</td></tr>"
        for a, b, c in s["branches"]
    )
    body = f"""<div class="page{' compact' if len(s['nodes']) >= 24 else ''}">
  <div class="kicker">功能流程图 · 第 {s['num']} 节</div>
  <h1>{esc(s['title'])}</h1>
  <div><span class="badge">{esc(s['feature'])}</span><span class="badge">前端 → 后端 → 数据</span></div>
  <p class="summary">{esc(s['summary'])}</p>
  <h2>分层调用链（函数 / 文件 / 行号）</h2>
  <table class="node-table">
    <thead><tr><th>层级</th><th>文件 : 行号</th><th>函数 / 组件 / 方法</th><th>职责</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
  <h2>关键分支与边界</h2>
  <table class="branch-table">
    <thead><tr><th>分支 / 边界</th><th>代码位置</th><th>行为</th></tr></thead>
    <tbody>{brows}</tbody>
  </table>
  <div class="foot"><span>英语默写练习平台 · 函数级功能流程图</span><span>{esc(s['num'])} · {esc(s['title'])}</span></div>
</div>"""
    return render(f"s{s['num']}_text", body, "size: 297mm 420mm; margin: 0;", TEXT_CSS)


def section_diagram(s):
    w, h = svg_size(s["diagram"])
    # 内容区：560mm x 772mm（A1 纵向，扣除标题、图例与页边距）
    scale = min(560.0 / (w * 0.264583), 772.0 / (h * 0.264583)) * 0.985
    iw = w * 0.264583 * scale
    ih = h * 0.264583 * scale
    css = """
h1 { font-size: 15pt; margin: 0; color: #14263d; }
.sub { font-size: 8.5pt; color: #5b7089; margin: 2mm 0 5mm; }
.dwrap { text-align: center; height: 772mm; display: flex; align-items: center; justify-content: center; }
.dwrap img { width: %(iw).2fmm; height: %(ih).2fmm; display: block; }
.legend { margin-top: 2mm; font-size: 7.1pt; color: #5b7089; }
""" % {"iw": iw, "ih": ih}
    body = f"""<div class="page">
  <h1>{esc(s['num'])} · {esc(s['title'])}</h1>
  <div class="sub">函数级流程图 · 节点内标注「文件 / 函数 / 行号」 · 颜色区分前端、API、后端路由、服务、数据层</div>
  <div class="dwrap"><img src="../svg/{s['diagram']}"></div>
  <div class="legend">蓝=前端视图/状态　绿=前端 API/请求　橙=后端路由　紫=后端服务/Agent　灰=数据模型　红=异常分支　黄=判定</div>
</div>"""
    return render(f"s{s['num']}_diagram", body, "size: 594mm 841mm; margin: 0;", css)


def cover():
    total_nodes = sum(len(s["nodes"]) for s in SECTIONS)
    body = f"""<div class="page">
  <div style="height:340mm;display:flex;flex-direction:column;justify-content:center">
    <div class="kicker">ENGLISH PRACTICE PLATFORM · REBUILD_VUE</div>
    <h1 style="font-size:38pt;line-height:1.25">英语默写练习平台<br>函数级功能流程图</h1>
    <div style="margin-top:9mm;font-size:13pt;color:#33475f;line-height:2">
      从 Vue 页面到 FastAPI 路由、服务、模型与数据库<br>
      每张图精确到文件、函数与行号
    </div>
    <div style="margin-top:18mm;font-size:10pt;color:#5b7089;line-height:1.9">
      仓库：D:\\A-Guide\\english_practice_vue　分支：rebuild_vue<br>
      功能条目：{len(SECTIONS)} 节 · 函数级节点：{total_nodes} 个 · 流程图：18 张<br>
      生成日期：2026-10-28
    </div>
    <div style="margin-top:18mm;font-size:9pt;color:#6b7f94;line-height:1.9;border-top:1pt solid #cfd9e4;padding-top:5mm">
      阅读方式：每个功能先给出分层调用链明细表，随后是全页流程图。流程图页为大开本（A1），便于放大查看；<br>
      颜色：蓝=前端视图/状态　绿=前端 API　橙=后端路由　紫=后端服务　灰=数据模型　红=异常　黄=判定。
    </div>
  </div>
</div>"""
    css = """
h1 { color:#14263d; margin:0; }
.kicker { font-size:9pt; letter-spacing:3px; color:#4a6fa5; margin-bottom:6mm; }
"""
    return render("00_cover", body, "size: 297mm 420mm; margin: 0;", css)


def toc(page_map):
    rows = "".join(
        f"<tr><td style='width:14mm;color:#4a6fa5;font-weight:600'>{s['num']}</td>"
        f"<td style='font-size:10pt'>{esc(s['title'])}</td>"
        f"<td style='width:46mm;font-size:8.5pt;color:#5b7089'>{esc(s['feature'])}</td>"
        f"<td style='width:16mm;text-align:right;font-size:10pt'>{page_map.get(s['num'], '')}</td></tr>"
        for s in SECTIONS
    )
    body = f"""<div class="page">
  <div class="kicker">目录 · CONTENTS</div>
  <h1 style="font-size:22pt;margin-bottom:6mm">功能索引</h1>
  <table style="width:100%;border-collapse:collapse">
    <thead><tr><th style="width:14mm">编号</th><th>功能</th><th>对应功能点</th><th style="text-align:right">起始页</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
  <div style="margin-top:8mm;font-size:8.2pt;color:#6b7f94;line-height:1.8">
    说明：每一节包含「分层调用链表」与「函数级流程图」两部分。行号以当前 rebuild_vue 分支代码为准。<br>
    全局约定：所有请求经 frontend/src/api/request.js 统一注入 Bearer 并解包 {{code, message, data}}；
    后端统一由 backend/app/core/deps.py 校验身份，由 backend/app/core/exception_handlers.py 输出错误。
  </div>
</div>"""
    css = """
h1 { font-size:22pt; color:#14263d; margin:0; }
.kicker { font-size:9pt; letter-spacing:3px; color:#4a6fa5; margin-bottom:4mm; }
table td { padding:3.6pt 5pt; border-bottom:0.5pt solid #dbe3ec; }
thead th { background:#eef3f9; border-bottom:1pt solid #b9c8d9; }
"""
    return render("01_toc", body, "size: 297mm 420mm; margin: 0;", css)


def main():
    def log(*a):
        print(*a, flush=True)

    cover_pdf = cover()
    log("cover", len(PdfReader(cover_pdf).pages))

    text_pdfs, diag_pdfs = {}, {}
    for s in SECTIONS:
        text_pdfs[s["num"]] = section_text(s)
        diag_pdfs[s["num"]] = section_diagram(s)
        log("section", s["num"], "text", len(PdfReader(text_pdfs[s["num"]]).pages),
            "diagram", len(PdfReader(diag_pdfs[s["num"]]).pages))

    cover_pages = len(PdfReader(cover_pdf).pages)
    # 目录先按占位生成，得到目录页数
    toc_pdf = toc({})
    toc_pages = len(PdfReader(toc_pdf).pages)

    page_map = {}
    cur = cover_pages + toc_pages + 1
    for s in SECTIONS:
        page_map[s["num"]] = cur
        cur += len(PdfReader(text_pdfs[s["num"]]).pages) + len(PdfReader(diag_pdfs[s["num"]]).pages)

    toc_pdf = toc(page_map)
    toc_pages = len(PdfReader(toc_pdf).pages)
    if cover_pages + toc_pages + 1 != page_map[SECTIONS[0]["num"]]:
        page_map = {}
        cur = cover_pages + toc_pages + 1
        for s in SECTIONS:
            page_map[s["num"]] = cur
            cur += len(PdfReader(text_pdfs[s["num"]]).pages) + len(PdfReader(diag_pdfs[s["num"]]).pages)
        toc_pdf = toc(page_map)

    writer = PdfWriter()
    for pdf in [cover_pdf, toc_pdf]:
        for page in PdfReader(pdf).pages:
            writer.add_page(page)
    for s in SECTIONS:
        for page in PdfReader(text_pdfs[s["num"]]).pages:
            writer.add_page(page)
        for page in PdfReader(diag_pdfs[s["num"]]).pages:
            writer.add_page(page)

    out = ROOT.parent / "功能流程图-函数级-全量.pdf"
    with open(out, "wb") as f:
        writer.write(f)
    print("OUTPUT", out, "pages", len(writer.pages), "size_mb", round(out.stat().st_size / 1024 / 1024, 2))


if __name__ == "__main__":
    sys.exit(main())
