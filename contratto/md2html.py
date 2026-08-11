# -*- coding: utf-8 -*-
"""Converte i .md del contratto in HTML autonomi, leggibili in Chrome e stampabili in PDF."""
import html
import re
import sys

CSS = """
:root{
  --ink:#1a1a1a; --muted:#5b6470; --line:#d8dde4; --bg:#ffffff;
  --accent:#8a6d3b; --note-bg:#fdf6e3; --note-line:#d9b96c;
  --ph-bg:#fff3b0; --ph-ink:#5c4700;
  --code-bg:#f4f6f8;
}
*{box-sizing:border-box}
body{
  margin:0; background:#eceff3; color:var(--ink);
  font-family:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif;
  font-size:16px; line-height:1.65;
}
.sheet{
  max-width:900px; margin:0 auto; background:var(--bg);
  padding:56px 64px 80px; box-shadow:0 0 0 1px rgba(0,0,0,.06),0 8px 32px rgba(0,0,0,.10);
}
h1{
  font-size:1.75rem; line-height:1.25; margin:2.4em 0 .6em;
  padding-bottom:.4em; border-bottom:2px solid var(--ink); letter-spacing:.01em;
}
h1:first-child{margin-top:0}
h2{font-size:1.28rem; margin:2em 0 .5em; padding-bottom:.25em; border-bottom:1px solid var(--line)}
h3{font-size:1.08rem; margin:1.7em 0 .4em; color:#111}
h4{font-size:1rem; margin:1.4em 0 .3em; color:var(--muted); text-transform:uppercase; letter-spacing:.05em}
p{margin:.7em 0}
ul,ol{margin:.7em 0; padding-left:1.5em}
li{margin:.3em 0}
hr{border:0; border-top:1px solid var(--line); margin:2.2em 0}
a{color:#0b5aa2}
strong{font-weight:700}
code{
  font-family:"Cascadia Mono",Consolas,"SF Mono",Menlo,monospace;
  font-size:.86em; background:var(--code-bg); padding:.12em .38em;
  border-radius:3px; border:1px solid var(--line);
}
pre{
  background:var(--code-bg); border:1px solid var(--line); border-radius:6px;
  padding:14px 16px; overflow-x:auto; font-size:.82rem; line-height:1.5;
  font-family:"Cascadia Mono",Consolas,"SF Mono",Menlo,monospace;
}
pre code{background:none; border:0; padding:0; font-size:1em}
table{border-collapse:collapse; width:100%; margin:1.1em 0; font-size:.92rem}
th,td{border:1px solid var(--line); padding:8px 11px; text-align:left; vertical-align:top}
th{background:#f2f5f8; font-weight:700}
tr:nth-child(even) td{background:#fafbfc}
blockquote{
  margin:1.2em 0; padding:12px 18px; background:var(--note-bg);
  border-left:4px solid var(--note-line); font-size:.94rem; color:#4a3e22;
}
blockquote p{margin:.35em 0}
.ph{background:var(--ph-bg); color:var(--ph-ink); padding:0 .25em; border-radius:2px; font-style:italic}
.toolbar{
  position:sticky; top:0; z-index:10; background:#fff; border-bottom:1px solid var(--line);
  padding:10px 16px; display:flex; gap:14px; align-items:center; justify-content:center;
  font-family:system-ui,-apple-system,"Segoe UI",sans-serif; font-size:.82rem; color:var(--muted);
}
.toolbar button{
  font:inherit; padding:5px 14px; border:1px solid var(--line); border-radius:5px;
  background:#f7f9fb; cursor:pointer; color:var(--ink);
}
.toolbar button:hover{background:#eef2f6}
.pagebreak{page-break-before:always; break-before:page}
@media print{
  body{background:#fff; font-size:10.5pt}
  .sheet{max-width:none; box-shadow:none; padding:0}
  .toolbar{display:none}
  h1,h2,h3{page-break-after:avoid; break-after:avoid}
  table,blockquote,pre{page-break-inside:avoid; break-inside:avoid}
  .ph{background:none; border-bottom:1px dotted #999; color:#000}
  @page{size:A4; margin:20mm 18mm}
}
"""

TOOLBAR = ('<div class="toolbar"><span>Documento locale &mdash; nessun dato esce dal computer</span>'
           '<button onclick="window.print()">Stampa / Salva come PDF</button></div>')


def inline(t):
    t = html.escape(t, quote=False)
    out, parts = [], re.split(r'(`[^`]+`)', t)
    for p in parts:
        if p.startswith('`') and p.endswith('`') and len(p) > 1:
            out.append('<code>' + p[1:-1] + '</code>')
            continue
        p = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', p)
        p = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', p)
        p = re.sub(r'(?<![\w*])\*([^*\n]+)\*(?![\w*])', r'<em>\1</em>', p)
        p = re.sub(r'&laquo;|«([^»]*)»', lambda m: '<span class="ph">&laquo;%s&raquo;</span>'
                   % (m.group(1) or ''), p)
        out.append(p)
    return ''.join(out)


def row(line):
    return [c.strip() for c in line.strip().strip('|').split('|')]


def convert(md):
    lines = md.split('\n')
    out, i, n = [], 0, len(lines)
    first_h1 = True
    while i < n:
        ln = lines[i]

        if ln.startswith('```'):                                    # blocco di codice
            i += 1
            buf = []
            while i < n and not lines[i].startswith('```'):
                buf.append(lines[i]); i += 1
            i += 1
            out.append('<pre><code>' + html.escape('\n'.join(buf)) + '</code></pre>')
            continue

        if re.match(r'^\s*$', ln):
            i += 1; continue

        if re.match(r'^---+\s*$', ln):                              # regola / interruzione pagina
            j = i
            while j < n and re.match(r'^---+\s*$', lines[j]):
                j += 1
            out.append('<div class="pagebreak"></div>' if j - i > 1 else '<hr>')
            i = j; continue

        m = re.match(r'^(#{1,6})\s+(.*)$', ln)                      # titoli
        if m:
            lvl, txt = len(m.group(1)), inline(m.group(2))
            cls = ''
            if lvl == 1 and not first_h1:
                cls = ' class="pagebreak"'
            if lvl == 1:
                first_h1 = False
            out.append(f'<h{lvl}{cls}>{txt}</h{lvl}>')
            i += 1; continue

        if ln.lstrip().startswith('|') and i + 1 < n and re.match(  # tabelle
                r'^\s*\|[\s:|-]+\|\s*$', lines[i + 1]):
            head = row(ln); i += 2
            body = []
            while i < n and lines[i].lstrip().startswith('|'):
                body.append(row(lines[i])); i += 1
            t = ['<table><thead><tr>']
            t += [f'<th>{inline(c)}</th>' for c in head]
            t.append('</tr></thead><tbody>')
            for r in body:
                t.append('<tr>' + ''.join(f'<td>{inline(c)}</td>' for c in r) + '</tr>')
            t.append('</tbody></table>')
            out.append(''.join(t)); continue

        if ln.startswith('>'):                                      # citazioni / note
            buf = []
            while i < n and lines[i].startswith('>'):
                buf.append(lines[i].lstrip('>').strip()); i += 1
            paras = [p.strip() for p in '\n'.join(buf).split('\n\n') if p.strip()]
            out.append('<blockquote>' +
                       ''.join(f'<p>{inline(p.replace(chr(10)," "))}</p>' for p in paras) +
                       '</blockquote>')
            continue

        m = re.match(r'^(\s*)([-*]|\d+[.)])\s+(.*)$', ln)           # elenchi
        if m:
            ordered = not m.group(2) in ('-', '*')
            tag = 'ol' if ordered else 'ul'
            items = []
            while i < n:
                mm = re.match(r'^(\s*)([-*]|\d+[.)])\s+(.*)$', lines[i])
                if not mm:
                    if items and lines[i].startswith('   ') and lines[i].strip():
                        items[-1] += ' ' + lines[i].strip(); i += 1; continue
                    break
                items.append(mm.group(3)); i += 1
            out.append(f'<{tag}>' + ''.join(f'<li>{inline(x)}</li>' for x in items) + f'</{tag}>')
            continue

        buf = []                                                    # paragrafo
        while i < n and lines[i].strip() and not re.match(
                r'^(#{1,6}\s|>|```|---+\s*$|\s*([-*]|\d+[.)])\s)', lines[i]) \
                and not lines[i].lstrip().startswith('|'):
            buf.append(lines[i].strip()); i += 1
        if buf:
            out.append('<p>' + inline(' '.join(buf)) + '</p>')
        else:
            i += 1
    return '\n'.join(out)


def build(src, dst, title):
    with open(src, encoding='utf-8') as f:
        md = f.read()
    body = convert(md)
    page = (f'<!doctype html>\n<html lang="it">\n<head>\n<meta charset="utf-8">\n'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">\n'
            f'<title>{html.escape(title)}</title>\n<style>{CSS}</style>\n</head>\n<body>\n'
            f'{TOOLBAR}\n<div class="sheet">\n{body}\n</div>\n</body>\n</html>\n')
    with open(dst, 'w', encoding='utf-8') as f:
        f.write(page)
    print(f'{dst}  ({len(page):,} byte)')


if __name__ == '__main__':
    base = sys.argv[1]
    build(base + r'\CONTRATTO_TOSCA.md', base + r'\CONTRATTO_TOSCA.html',
          'Contratto di licenza d\'uso e fornitura del servizio TOSCA')
    build(base + r'\FORM_ATTIVAZIONE.md', base + r'\FORM_ATTIVAZIONE.html',
          'Form di attivazione e firma contratto — progetto tecnico')
