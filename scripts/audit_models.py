# -*- coding: utf-8 -*-
"""
批量审核 MIDAS 模型：打开副本 → 读 DB → 重分析 → 全表提取结果
用法: python audit_models.py 模型清单.json 输出目录/ [--tmp 临时目录]

模型清单.json 格式:
[
  {"tag": "01_张三", "mcb": "D:/exam/01/模型.mcb"},
  ...
]

安全说明：脚本会把每个 .mcb 先复制到临时目录再打开（分析会写回文件）。
"""
import sys, os, json, time, shutil, argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from midas_api import MidasAPI, AUDIT_TABLES


def audit_one(api, mcb_path, tag, tmp_dir):
    os.makedirs(tmp_dir, exist_ok=True)
    tmp_mcb = os.path.join(tmp_dir, f'{tag}.mcb')
    shutil.copy2(mcb_path, tmp_mcb)
    mct_src = os.path.splitext(mcb_path)[0] + '.mct'
    if os.path.isfile(mct_src):
        shutil.copy2(mct_src, os.path.join(tmp_dir, f'{tag}.mct'))

    result = {'file': mcb_path, 'tag': tag}

    api.new()
    st, resp = api.open(tmp_mcb)
    result['open'] = {'status': st, 'resp': str(resp)[:200]}
    print(f'  open: {st}', flush=True)
    if st != 200:
        return result

    # 读 DB 表
    data = {}
    for t in AUDIT_TABLES:
        st, resp = api.get_db(t)
        if st == 200 and isinstance(resp, dict):
            s = json.dumps(resp, ensure_ascii=False)
            if s not in ('{"message": ""}', '{}'):
                data[t] = resp
    result['db'] = data
    print(f'  db: {len(data)}/{len(AUDIT_TABLES)} 有数据', flush=True)

    # 分析
    t0 = time.time()
    st, resp = api.anal()
    result['anal'] = {'status': st, 'resp': str(resp)[:300]}
    result['anal_elapsed'] = round(time.time() - t0, 1)
    print(f'  anal: {st} {str(resp)[:80]} ({result["anal_elapsed"]}s)', flush=True)
    if 'not allowed' in str(resp) or 'error' in str(resp).lower():
        result['results'] = {}
        return result

    # 全表 dump + 按工况名分组统计
    results = {}
    for tt, cols in [('DISPLACEMENTG', [3, 4, 5]), ('BEAMFORCE', [4, 5, 6, 7, 8, 9]),
                     ('REACTIONG', [2, 3, 4, 5, 6, 7])]:
        st, resp = api.table(tt)
        if st == 200 and isinstance(resp, dict) and 'SS_Table' in resp:
            rows = resp['SS_Table'].get('DATA', [])
            groups = {}
            for r in rows:
                if len(r) > 2:
                    groups.setdefault(r[2], []).append(r)
            for nm, sub in groups.items():
                vals = []
                for r in sub:
                    for c in cols:
                        if c < len(r):
                            try:
                                vals.append(float(r[c]))
                            except ValueError:
                                pass
                if vals:
                    results[f'{nm}|{tt}'] = {
                        'max': round(max(vals), 4), 'min': round(min(vals), 4),
                        'amax': round(max(abs(v) for v in vals), 4)}
    result['results'] = results
    print(f'  results: {len(results)} 组工况结果', flush=True)
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('manifest', help='模型清单 JSON')
    ap.add_argument('outdir', help='输出目录')
    ap.add_argument('--tmp', default=None, help='临时目录（默认 outdir/tmp_models）')
    args = ap.parse_args()

    models = json.load(open(args.manifest, encoding='utf-8'))
    tmp_dir = args.tmp or os.path.join(args.outdir, 'tmp_models')
    os.makedirs(args.outdir, exist_ok=True)

    api = MidasAPI()
    for m in models:
        tag, path = m['tag'], m['mcb']
        print('=' * 60)
        print(f'[{tag}] {os.path.basename(path)}', flush=True)
        if not os.path.isfile(path):
            print('  !! 文件不存在，跳过')
            continue
        try:
            r = audit_one(api, path, tag, tmp_dir)
            with open(os.path.join(args.outdir, f'{tag}.json'), 'w', encoding='utf-8') as f:
                json.dump(r, f, ensure_ascii=False, indent=1)
        except Exception as e:
            print(f'  !! 失败: {e}')
    print('\n批量审核结束')


if __name__ == '__main__':
    main()
