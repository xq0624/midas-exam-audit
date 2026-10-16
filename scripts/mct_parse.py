# -*- coding: utf-8 -*-
"""
MCT 解析器 — 提取 MIDAS Civil Text (.mct) 文件的关键建模信息
用法: python mct_parse.py <mct文件> [输出json]

编码自适应：UTF-16 BOM / 无 BOM UTF-16LE / UTF-8 / GB18030
"""
import sys, os, json
from collections import OrderedDict


def read_text(path):
    raw = open(path, 'rb').read()
    if raw[:2] == b'\xff\xfe':
        return raw.decode('utf-16-le', errors='replace'), 'utf-16le'
    if raw[:2] == b'\xfe\xff':
        return raw.decode('utf-16-be', errors='replace'), 'utf-16be'
    if b'\x00' in raw[:4000]:
        try:
            t = raw.decode('utf-16-le', errors='replace')
            if t.count('\ufffd') < 20:
                return t, 'utf-16le(nobom)'
        except UnicodeDecodeError:
            pass
    for enc in ('utf-8', 'gb18030'):
        try:
            t = raw.decode(enc)
            if t.count('\ufffd') < 10:
                return t, enc
        except UnicodeDecodeError:
            continue
    return raw.decode('gb18030', errors='replace'), 'gb18030?'


def parse_mct(path):
    text, enc = read_text(path)
    lines = text.splitlines()
    info = {'file': path, 'encoding': enc}

    # 把所有 *BLOCK 分段
    blocks = OrderedDict()
    cur = None
    for ln in lines:
        s = ln.strip()
        if s.startswith('*'):
            name = s.split(';')[0].strip().upper().lstrip('*').strip()
            cur = name
            blocks.setdefault(cur, [])
        elif cur is not None:
            blocks[cur].append(ln)

    def datalines(name):
        out = []
        for ln in blocks.get(name, []):
            t = ln.strip()
            if t and not t.startswith(';'):
                out.append(t)
        return out

    # UNIT
    for ln in blocks.get('UNIT', []):
        t = ln.strip()
        if t and not t.startswith(';'):
            info['unit'] = t
            break

    # NODE
    nodes = OrderedDict()
    for ln in datalines('NODE'):
        parts = [p.strip() for p in ln.split(',')]
        if len(parts) >= 4:
            try:
                nodes[int(parts[0])] = (float(parts[1]), float(parts[2]), float(parts[3]))
            except ValueError:
                pass
    info['n_node'] = len(nodes)

    # ELEMENT
    elems = []
    for ln in datalines('ELEMENT'):
        parts = [p.strip() for p in ln.split(',')]
        if len(parts) >= 5:
            try:
                elems.append({'id': int(parts[0]), 'type': parts[1],
                              'n1': int(parts[2]), 'n2': int(parts[3]), 'sect': parts[4]})
            except ValueError:
                pass
    info['n_elem'] = len(elems)

    if nodes:
        xs = [v[0] for v in nodes.values()]
        ys = [v[1] for v in nodes.values()]
        zs = [v[2] for v in nodes.values()]
        info['bbox'] = {'x': (min(xs), max(xs)), 'y': (min(ys), max(ys)), 'z': (min(zs), max(zs))}

    # SECTION
    sects = []
    for ln in datalines('SECTION'):
        parts = [p.strip() for p in ln.split(',')]
        if len(parts) >= 8:
            try:
                sid = int(parts[0])
            except ValueError:
                continue
            stype = parts[1]
            sname = parts[2]
            shape = parts[6] if len(parts) > 6 else ''
            db_name = ''
            if 'DBUSER' in stype.upper():
                for p in parts[7:]:
                    if p and p not in ('1', '2') and not p.replace('.', '').isdigit():
                        if any(k in p for k in ('GB', 'JT', 'JC', 'AISC')):
                            db_name = p
                for i, p in enumerate(parts):
                    if db_name and p == db_name and i + 1 < len(parts):
                        db_name = p + ' ' + parts[i + 1]
                        break
            sects.append({'id': sid, 'type': stype, 'name': sname, 'shape': shape,
                          'db': db_name, 'raw': parts[1:10]})
    info['sections'] = sects

    # SECT-PSCVALUE（VALUE 自定义截面的详细属性）
    psv = []
    for ln in datalines('SECT-PSCVALUE'):
        parts = [p.strip() for p in ln.split(',')]
        if len(parts) >= 8:
            try:
                sid = int(parts[0])
            except ValueError:
                continue
            psv.append({'id': sid, 'type': parts[1], 'name': parts[2],
                        'shape': parts[6] if len(parts) > 6 else '', 'raw': parts})
    if psv:
        info['sect_pscvalue'] = psv

    # STLDCASE
    stld = []
    for ln in datalines('STLDCASE'):
        parts = [p.strip() for p in ln.split(',')]
        if len(parts) >= 2:
            stld.append({'name': parts[0], 'type': parts[1],
                         'desc': parts[2] if len(parts) > 2 else ''})
    info['stldcase'] = stld

    # CONSTRAINT
    cons = []
    for ln in datalines('CONSTRAINT'):
        parts = [p.strip() for p in ln.split(',')]
        if len(parts) >= 2:
            cons.append({'nodes': parts[0], 'const': parts[1],
                         'group': parts[2] if len(parts) > 2 else ''})
    info['constraints'] = cons

    # SELFWEIGHT
    sw = []
    for ln in datalines('SELFWEIGHT'):
        parts = [p.strip() for p in ln.split(',')]
        if parts:
            sw.append({'raw': parts})
    info['selfweight'] = sw

    # BEAMLOAD（按 *USE-STLD,xxx 分组）
    beamloads = []
    cur_stld = None
    cur_grp = None
    for ln in lines:
        s = ln.strip()
        if s.startswith('*'):
            head = s.split(';')[0].strip()
            if head.upper().startswith('*USE-STLD'):
                cur_stld = head.split(',', 1)[1].strip() if ',' in head else head
                cur_grp = None
            elif head.upper().startswith('*BEAMLOAD'):
                cur_grp = {'lc': cur_stld, 'lines': []}
                beamloads.append(cur_grp)
            else:
                cur_grp = None
        elif cur_grp is not None:
            t = ln.strip()
            if t and not t.startswith(';'):
                cur_grp['lines'].append(t)
    info['beamload_groups'] = beamloads

    # LOADCOMB
    combs = []
    lines_lc = datalines('LOADCOMB')
    i = 0
    while i < len(lines_lc):
        ln = lines_lc[i]
        if ln.startswith('NAME='):
            body = []
            j = i + 1
            while j < len(lines_lc) and not lines_lc[j].startswith('NAME='):
                body.append(lines_lc[j])
                j += 1
            combs.append({'head': ln, 'body': body})
            i = j
        else:
            i += 1
    info['loadcomb'] = combs

    # ELASTICLINK
    ell = []
    for ln in datalines('ELASTICLINK'):
        parts = [p.strip() for p in ln.split(',')]
        if len(parts) >= 6:
            try:
                ell.append({'id': int(parts[0]), 'n1': int(parts[1]),
                            'n2': int(parts[2]), 'link': parts[3]})
            except ValueError:
                pass
    info['elasticlink'] = {'n': len(ell), 'types': list(set(e['link'] for e in ell))}

    # 移动荷载
    veh = [ln.strip()[:120] for ln in datalines('VEHICLE') if ln.strip()]
    info['vehicle'] = veh[:5]
    mvld = [ln.strip()[:150] for ln in datalines('MVLDCASE(CH)') if ln.strip()]
    info['mvldcase'] = mvld[:5]
    surf = [ln.strip()[:150] for ln in datalines('SURFLANE(CH)') if ln.strip()]
    info['surflane'] = surf[:5]

    # 板厚与板荷载
    thick = [ln.strip()[:100] for ln in datalines('THICKNESS') if ln.strip()]
    info['thickness'] = thick[:10]
    pres = [ln.strip()[:150] for ln in datalines('PRESSURE') if ln.strip()]
    info['pressure'] = pres[:10]

    info['blocks'] = list(blocks.keys())

    # 单元-截面使用统计
    sect_use = {}
    for e in elems:
        sect_use[e['sect']] = sect_use.get(e['sect'], 0) + 1
    info['sect_use'] = sect_use

    return info


if __name__ == '__main__':
    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) > 2 else None
    r = parse_mct(src)
    if dst:
        os.makedirs(os.path.dirname(dst) or '.', exist_ok=True)
        json.dump(r, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('saved', dst)
    else:
        print(json.dumps(r, ensure_ascii=False, indent=1)[:4000])
