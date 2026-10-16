# -*- coding: utf-8 -*-
"""
MIDAS Civil MOA API 客户端（审核专用）
用法：from midas_api import MidasAPI
Key 读取顺序：环境变量 MIDAS_MAPI_KEY > 同目录 config.json 的 mapi_key
"""
import sys, json, time, os
import urllib.request
import urllib.error

DEFAULT_BASE = "https://moa-engineers.midasit.cn:443/civil"


def load_key():
    key = os.environ.get('MIDAS_MAPI_KEY', '').strip()
    if key:
        return key
    cfg = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
    if os.path.isfile(cfg):
        try:
            return json.load(open(cfg, encoding='utf-8')).get('mapi_key', '').strip()
        except Exception:
            pass
    return ''


class MidasAPI:
    def __init__(self, key=None, base=None):
        self.key = key or load_key()
        self.base = base or os.environ.get('MIDAS_API_BASE', DEFAULT_BASE)
        if not self.key:
            raise RuntimeError(
                '未找到 API Key。请设置环境变量 MIDAS_MAPI_KEY，'
                '或将 key 写入 config.json（{"mapi_key": "..."}）。')

    def call(self, method, ep, body=None, timeout=300, retries=2):
        url = self.base + ep
        data = json.dumps(body).encode('utf-8') if body is not None else None
        last_err = None
        for _ in range(retries + 1):
            req = urllib.request.Request(url, data=data, method=method)
            req.add_header('MAPI-Key', self.key)
            req.add_header('Content-Type', 'application/json')
            try:
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    return r.status, json.loads(r.read().decode('utf-8', errors='replace'))
            except urllib.error.HTTPError as e:
                txt = e.read().decode('utf-8', errors='replace')
                try:
                    return e.code, json.loads(txt)
                except Exception:
                    return e.code, txt
            except Exception as e:
                last_err = e
                time.sleep(2)
        return -1, str(last_err)

    # ---- 文档 ----
    def open(self, path):
        return self.call('POST', '/doc/open', {"Argument": path}, timeout=300)

    def anal(self):
        return self.call('POST', '/doc/anal', {}, timeout=900)

    def new(self):
        return self.call('POST', '/doc/new', {}, timeout=180)

    def save(self, path):
        return self.call('POST', '/doc/saveas', {"Argument": path}, timeout=300)

    # ---- 数据库 ----
    def get_db(self, table, body=None):
        return self.call('GET', f'/db/{table}', body, timeout=180)

    def status(self):
        return self.call('GET', '/ope/PROJECTSTATUS', None, timeout=120)

    # ---- 结果表 ----
    def table(self, table_type, loadcase=None, keys=None, components=None):
        """table_type: DISPLACEMENTG / BEAMFORCE / REACTIONG / STRESSG ...
        不传 loadcase = 返回全表（所有工况），最稳妥。"""
        arg = {
            "TABLE_NAME": "SS_Table",
            "TABLE_TYPE": table_type,
            "STYLES": {"FORMAT": "Fixed", "PLACE": 3},
        }
        if loadcase:
            arg["LOAD_CASE_NAMES"] = loadcase
        if keys:
            arg["NODE_ELEMS"] = {"KEYS": keys}
        if components:
            arg["COMPONENTS"] = components
        return self.call('POST', '/post/TABLE', {"Argument": arg}, timeout=300)


# 审核用的数据表清单
AUDIT_TABLES = ['UNIT', 'MATL', 'SECT', 'NODE', 'ELEM', 'CONS', 'ELNK',
                'STLD', 'BODF', 'CNLD', 'bmld', 'PRES', 'FBLD', 'sdsp',
                'LLAN', 'MVCD', 'MVHL', 'SMLC', 'PNLD',
                'LCOM-STEEL', 'LCOM-CONC', 'LCOM-SRC', 'LCOM-SEISMIC']
