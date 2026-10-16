# -*- coding: utf-8 -*-
"""
变量 n 核验 — 按座位号计算期望尺寸，与模型几何签名比对，判定"尺寸与学号对应"
用法:
  python verify_vars.py 模型.mct --seat 26 --vars "900-n:1,3000+n:1,3600+n:1,5600+n:1,6000+n:1"
  python verify_vars.py 模型.mct --seat 13 --vars "2420+n,3000+n,6000+2n,3200-n,3850-n"

--vars 格式: 逗号分隔的变量表达式，可带 ":系数" 后缀（默认1）
判据: 每项在模型"三轴坐标 & 两两差值"全集里是否有命中（±tol mm），
命中数 ≥ 半数判"是"，明显低于且错 n 命中更多则判"否（n 取错）"。
"""
import sys, os, argparse, itertools
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mct_parse import read_text


def parse_nodes(path):
    t, enc = read_text(path)
    nodes = {}
    cur = None
    for ln in t.splitlines():
        s = ln.strip()
        if s.startswith('*'):
            cur = s.split(';')[0].strip().upper().lstrip('*').strip()
            continue
        if cur == 'NODE' and s and not s.startswith(';'):
            p = [x.strip() for x in s.split(',')]
            try:
                if len(p) >= 4:
                    nodes[int(p[0])] = (float(p[1]), float(p[2]), float(p[3]))
            except ValueError:
                pass
    return nodes


def build_signature(nodes):
    """三轴坐标全集 + （集合不大时）两两差值集合，单位 mm"""
    sig = set()
    for i in range(3):
        vals = sorted(set(round(v[i]) for v in nodes.values()))
        sig.update(vals)
        if len(vals) <= 300:
            for a, b in itertools.combinations(vals, 2):
                sig.add(abs(b - a))
    return sig


def eval_expr(expr, n):
    """'6000+2n' / '900-n' / '2420+n' → 数值（n 代入）"""
    e = expr.replace('＋', '+').replace('－', '-').replace('n', str(n), 1)
    if 'n' in e:
        e = e.replace('n', str(n))
    try:
        return int(eval(e))
    except Exception:
        return None


def check(model_path, seat, var_exprs, tol=5, rule=None):
    n = rule(seat) if rule else (seat * 10 if seat <= 50 else (seat - 50) * 10)
    nodes = parse_nodes(model_path)
    sig = build_signature(nodes)
    print(f'模型: {os.path.basename(model_path)}  座位号: {seat}  →  n = {n}')
    print(f'坐标签名规模: {len(sig)} 个值')
    hits = 0
    for expr in var_exprs:
        exp = eval_expr(expr, n)
        if exp is None:
            print(f'  {expr:10s} 表达式解析失败')
            continue
        m = [v for v in sig if abs(v - exp) <= tol]
        ok = bool(m)
        hits += ok
        print(f'  {expr:10s} = {exp:6d}  {"✓ 命中 " + str(sorted(m)[:3]) if ok else "✗ 未见"}')
    verdict = '是（尺寸与学号对应）' if hits >= len(var_exprs) / 2 else '否（未体现/取错变量）'
    print(f'→ {hits}/{len(var_exprs)} 命中，判定: {verdict}')
    return hits, len(var_exprs)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('model')
    ap.add_argument('--seat', type=int, required=True)
    ap.add_argument('--vars', required=True, help='如 "900-n,3000+n,3600+n"')
    ap.add_argument('--tol', type=int, default=5)
    args = ap.parse_args()
    exprs = [x.strip() for x in args.vars.replace('：', ':').split(',') if x.strip()]
    # 去掉 ":系数" 后缀（本工具暂只支持 1 倍；特殊倍数直接写进表达式，如 6000+2n）
    exprs = [re.sub(r':\d+$', '', x) for x in exprs]
    check(args.model, args.seat, exprs, tol=args.tol)
