# -*- coding: utf-8 -*-
"""
模型质量扫描：悬浮节点 / 重复单元 / 重复坐标节点 / 自由体提示
用法: python quality_check.py 模型清单.json
清单格式: [{"tag":"01_张三","mct":"路径.mct"}, ...]  或  {"mcb": ...} 会自动换扩展名
"""
import sys, os, json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mct_parse import read_text


def parse_full(path):
    t, enc = read_text(path)
    lines = t.splitlines()
    nodes = {}
    elems = []
    cur = None
    for ln in lines:
        s = ln.strip()
        if s.startswith('*'):
            cur = s.split(';')[0].strip().upper().lstrip('*').strip()
            continue
        if not s or s.startswith(';'):
            continue
        p = [x.strip() for x in s.split(',')]
        if cur == 'NODE':
            try:
                if len(p) >= 4:
                    nodes[int(p[0])] = (float(p[1]), float(p[2]), float(p[3]))
            except ValueError:
                pass
        elif cur == 'ELEMENT':
            try:
                if len(p) >= 6:
                    elems.append({'id': int(p[0]), 'type': p[1], 'sect': p[3],
                                  'nodes': [int(x) for x in p[4:] if x]})
            except ValueError:
                pass
    return nodes, elems


def scan_one(path):
    nodes, elems = parse_full(path)
    used = set()
    for e in elems:
        used.update(e['nodes'])
    floating = [n for n in nodes if n not in used]

    seen = {}
    dup_elem = 0
    for e in elems:
        key = tuple(sorted(e['nodes']))
        if key in seen:
            dup_elem += 1
        seen[key] = e['id']

    coord = {}
    for n, v in nodes.items():
        k = (round(v[0], 1), round(v[1], 1), round(v[2], 1))
        coord.setdefault(k, []).append(n)
    dup_node_coord = sum(len(v) - 1 for v in coord.values() if len(v) > 1)

    return {
        'n_node': len(nodes), 'n_elem': len(elems),
        'floating': len(floating),
        'floating_ratio': round(100 * len(floating) / max(len(nodes), 1), 1),
        'floating_ids': floating[:20],
        'dup_elem': dup_elem,
        'dup_node_coord': dup_node_coord,
    }


if __name__ == '__main__':
    models = json.load(open(sys.argv[1], encoding='utf-8'))
    print(f'{"模型":20s} {"总节点":>7s} {"悬浮":>7s} {"悬浮率":>7s} {"重复单元":>8s} {"重复坐标":>8s}')
    for m in models:
        tag = m.get('tag', os.path.basename(m.get('mct') or m.get('mcb', '?')))
        path = m.get('mct') or os.path.splitext(m.get('mcb', ''))[0] + '.mct'
        if not os.path.isfile(path):
            print(f'{tag:20s} 文件不存在: {path}')
            continue
        r = scan_one(path)
        flag = ''
        if r['floating_ratio'] > 15:
            flag = ' ⚠悬浮多'
        if r['dup_elem'] > 50:
            flag += ' ⚠重复单元多'
        print(f'{tag:20s} {r["n_node"]:7d} {r["floating"]:7d} {r["floating_ratio"]:6.1f}% '
              f'{r["dup_elem"]:8d} {r["dup_node_coord"]:8d}{flag}')
