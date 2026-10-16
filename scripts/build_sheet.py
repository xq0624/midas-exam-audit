# -*- coding: utf-8 -*-
"""
评分表生成 — 以官方模板 xlsx 为底稿，保留表头/公式/格式，仅填数据区
用法: python build_sheet.py 模板.xlsx 评分数据.json 输出.xlsx

评分数据.json 格式:
{
  "sheet": "附件5 ",            // 可选，模板内的工作表名；默认取第一个非空表
  "start_row": 6,               // 数据起始行
  "keep_sheets": ["附件5 "],     // 只保留的工作表（可选）
  "print_area": "A1:Z19",       // 可选，写打印区域（官方模板常预设小范围）
  "students": [
    {
      "seat": "13", "name": "张三", "match": "是",
      "scores": {"D": 11, "H": 7, "J": 11, "M": 12, "Q": 10, "T": 15},
      "book": 21,               // 计算书得分 -> V 列
      "note": "评分概述文字"     // -> Z 列
    }, ...
  ]
}

用法要点：
- 表头（第 1~5 行）保持不动；脚本会在修改前后逐格校验表头与合并单元格
- X/Y 列保留 =SUM(D:U) / =X*0.7+V 公式
"""
import sys, os, json, shutil, argparse
import openpyxl
from openpyxl.styles import Alignment


def build(template, data, out):
    shutil.copy2(template, out)
    wb = openpyxl.load_workbook(out)
    sheet_name = data.get('sheet') or wb.sheetnames[0]
    ws = wb[sheet_name]

    # 记录表头（1~5行）与合并
    merges_before = sorted(str(m) for m in ws.merged_cells.ranges)
    head_before = {}
    for r in range(1, 6):
        for c in range(1, 27):
            v = ws.cell(row=r, column=c).value
            if v is not None:
                head_before[(r, c)] = v

    # 只保留指定工作表
    keep = data.get('keep_sheets')
    if keep:
        for nm in list(wb.sheetnames):
            if nm not in keep:
                del wb[nm]

    start_row = data.get('start_row', 6)
    n = len(data['students'])
    end_row = start_row + n - 1

    # 清空数据区（保留格式）
    for r in range(start_row, max(end_row + 5, start_row + 34)):
        for c in range(1, 27):
            ws.cell(row=r, column=c).value = None

    # 填数据
    for i, stu in enumerate(data['students']):
        r = start_row + i
        ws.cell(row=r, column=1).value = stu.get('seat')
        ws.cell(row=r, column=2).value = stu.get('name')
        ws.cell(row=r, column=3).value = stu.get('match', '')
        for col, val in stu.get('scores', {}).items():
            ws[f'{col}{r}'].value = val
        ws[f'V{r}'].value = stu.get('book', 0)
        ws[f'X{r}'].value = f'=SUM(D{r}:U{r})'
        ws[f'Y{r}'].value = f'=X{r}*0.7+V{r}'
        note = stu.get('note', '')
        if note:
            zc = ws[f'Z{r}']
            zc.value = note
            zc.alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)
            lines = max(3, len(note) // 38 + (1 if len(note) % 38 else 0))
            ws.row_dimensions[r].height = max(70, min(170, lines * 15 + 12))

    if data.get('print_area'):
        ws.print_area = data['print_area']
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 1
        try:
            ws.sheet_properties.pageSetUpPr.fitToPage = True
        except Exception:
            pass

    wb.active = 0
    wb.save(out)

    # ---- 校验 ----
    wb2 = openpyxl.load_workbook(out)
    ws2 = wb2[sheet_name]
    merges_after = sorted(str(m) for m in ws2.merged_cells.ranges)
    bad = 0
    for (r, c), v in head_before.items():
        if ws2.cell(row=r, column=c).value != v:
            bad += 1
    print('=== 校验 ===')
    print('合并单元格一致:', set(merges_before) == set(merges_after))
    print('表头逐格一致:', '是' if bad == 0 else f'否（{bad}处差异）')
    ok = True
    for i, stu in enumerate(data['students']):
        r = start_row + i
        ms = sum(stu.get('scores', {}).values())
        total = round(ms * 0.7 + stu.get('book', 0), 1)
        for col, val in stu.get('scores', {}).items():
            if ws2[f'{col}{r}'].value != val:
                ok = False
        print(f'  行{r} {stu.get("name")}: 模型分={ms} 计算书={stu.get("book")} → 总分={total}')
    print('数据全部正确:', ok)
    return ok


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('template')
    ap.add_argument('data', help='评分数据 JSON')
    ap.add_argument('out')
    args = ap.parse_args()
    d = json.load(open(args.data, encoding='utf-8'))
    build(args.template, d, args.out)
    print('saved:', args.out)
