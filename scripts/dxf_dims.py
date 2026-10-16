# -*- coding: utf-8 -*-
"""
DXF 变量标注提取器 — 从 CAD 图纸导出的 DXF 中找出含变量 n 的尺寸标注
用法: python dxf_dims.py 图纸.dxf [--all]

输出每处变量标注：覆盖文字（如 <>+n、6000+2n、900-n）与期望值提示。

导出 DXF 的方法（无 AutoCAD 时用中望 ZWCAD）：
  1. 写脚本文件 dxfout.scr:
       FILEDIA
       0
       _DXFOUT
       C:/temp/output.dxf
       16
       (空行)
  2. 执行: "ZWCAD.exe" "图纸.dwg" /b "dxfout.scr"
     （等待 CAD 自动打开、导出、可加 QSAVE 后退出）
"""
import sys, re


def load_blocks(path):
    """把 DXF 按 (0, TYPE) 切成实体块 [(type, [(code, value), ...]), ...]"""
    t = open(path, encoding='utf-8', errors='replace').read()
    lines = t.splitlines()
    blocks = []
    cur_type = None
    cur_data = []
    i = 0
    while i < len(lines) - 1:
        code = lines[i].strip()
        val = lines[i + 1].rstrip('\n')
        if code == '0':
            if cur_type:
                blocks.append((cur_type, cur_data))
            cur_type = val.strip()
            cur_data = []
        else:
            cur_data.append((code, val.strip()))
        i += 2
    if cur_type:
        blocks.append((cur_type, cur_data))
    return blocks


def gv(data, code):
    return [v for c, v in data if c == code]


def clean_text(s):
    """去掉 MTEXT 格式控制码"""
    s = re.sub(r'\\[A-Za-z][^;]*;', '', s)   # \A1; \W0.7; 等
    s = s.replace('\\P', ' ').replace('{', '').replace('}', '')
    return s.strip()


def find_n_dims(path, show_all=False):
    blocks = load_blocks(path)
    found = []
    for etype, data in blocks:
        if etype not in ('DIMENSION', 'TEXT', 'MTEXT'):
            continue
        tx = gv(data, '1')
        if not tx:
            continue
        raw = tx[0]
        s = clean_text(raw)
        if not s:
            continue
        # 变量特征：含 n 且形式像标注（+n/-n/数字+n 组合）
        is_var = bool(re.search(r'[+\-＋－]?\s*n\b', s, re.I)) or '＜＞' in s or '<>' in s
        if not (is_var or show_all):
            continue
        if etype == 'DIMENSION':
            val = gv(data, '42')
            p13 = gv(data, '13'); p23 = gv(data, '23')
            p14 = gv(data, '14'); p24 = gv(data, '24')
            info = {'kind': 'DIMENSION', 'text': s, 'measure': val[0] if val else None}
            if p13 and p23 and p14 and p24:
                x1, y1 = float(p13[0]), float(p23[0])
                x2, y2 = float(p14[0]), float(p24[0])
                dx, dy = abs(x2 - x1), abs(y2 - y1)
                info['orientation'] = 'X' if dx > dy else 'Y'
            found.append(info)
        elif len(s) < 40:
            found.append({'kind': etype, 'text': s, 'measure': None})
    return found


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    path = sys.argv[1]
    show_all = '--all' in sys.argv
    found = find_n_dims(path, show_all)
    print(f'共 {len(found)} 处变量标注:')
    for f in found:
        extra = f' measure={f["measure"]}' if f.get('measure') else ''
        orient = f' [{f["orientation"]}向]' if f.get('orientation') else ''
        print(f'  [{f["kind"]:9s}] {f["text"]!r}{extra}{orient}')
    # 汇总模板
    templates = sorted(set(f['text'] for f in found if f['kind'] == 'DIMENSION'))
    print()
    print('变量模板汇总（供 verify_vars.py 使用）:')
    for t in templates:
        print(f'  {t}')


if __name__ == '__main__':
    main()
