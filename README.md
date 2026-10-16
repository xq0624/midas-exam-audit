# midas-exam-audit

MIDAS Civil 结构建模考核（上机考试）批量审核与评分工具包 —— 一个 Claude Code / WorkBuddy / CodeBuddy 等 AI 编程客户端的 Skill。

把一批考生提交的 `.mcb` / `.mct` 模型和计算书，变成一套**可追溯、有据可查**的评分依据：每个扣分点都能指到具体的节点坐标、截面名称、荷载数值或计算书原文。

## 覆盖能力

| 环节 | 脚本 | 说明 |
|---|---|---|
| MCT 文本解析 | `scripts/mct_parse.py` | 纯文本读模型全景（节点/单元/截面/边界/荷载/组合/移动荷载），编码自适应（UTF-16/GBK/UTF-8） |
| API 重分析提数 | `scripts/audit_models.py` | 经 MIDAS MOA API 打开副本、重跑分析、全表提取位移/内力结果 |
| 模型质量扫描 | `scripts/quality_check.py` | 悬浮节点、重复单元、重复坐标节点统计 |
| 图纸变量提取 | `scripts/dxf_dims.py` | 从 DWG 导出的 DXF 中找出所有含变量 n 的尺寸标注（`<>+n`、`6000+2n` 等） |
| 学号变量核验 | `scripts/verify_vars.py` | 按座位号算期望尺寸，与模型几何签名比对，判定"尺寸与学号对应" |
| 评分表生成 | `scripts/build_sheet.py` | 以官方模板为底，表头/公式/格式保持不动，仅填数据区并逐格校验 |

## 工作原理

### 学号变量核验（核心方法）

考试模型常含"变量 n"（如 `900-n`、`6000+2n`、`1300+n`），n 由座位号决定。核验思路：

1. **提取标注**：CAD 把 DWG 批量导出 DXF（ZWCAD 用 `/b` 脚本），解析 `DIMENSION` 实体的覆盖文字（group code 1）与测量值（code 42）
2. **定规则**：从试题说明取 n 规则（常见：座位 1-50 → n=座位×10；51-100 → n=(座位-50)×10）
3. **建签名**：把模型节点三轴坐标全集 + 两两差值集合（统一 mm）作为"几何签名"
4. **比对**：每项期望尺寸（±5mm 容差）在签名中找命中；半数以上命中判"是"

实测案例：某考生模型主桁架间距 6480mm，两组假设比对后确认是 `6000+2n` 取 n=240（应 190），
判定"尺寸与学号不对应"——同题另两名考生 6260=6000+2×130、6620=6000+2×310 均严格符合，判定确凿。

### API 组合结果表名坑

MIDAS Civil NX 不同版本组合结果的表名格式不同（`1(CB)` / `强度(max)` / `基本1` / `自重(all)`）。
稳妥做法：**不带 loadcase 参数全表 dump 后按第 3 列（工况名）分组**，避免逐个猜名。

### 评分表表头保护

以官方模板 xlsx 为底稿复制，脚本在修改前后**逐格比对表头单元格与 merged_cells 集合**，
确保表头（含说明行、三级"优/良/差"表头）一行未动；保留 `X=SUM(D:U)`、`Y=X*0.7+V` 公式。

## 安装

### 作为 AI 客户端 Skill

```bash
# Claude Code
git clone https://github.com/<your>/midas-exam-audit.git ~/.claude/skills/midas-exam-audit

# WorkBuddy / CodeBuddy
git clone https://github.com/<your>/midas-exam-audit.git ~/.workbuddy/skills/midas-exam-audit
```

### 依赖

- Python 3.9+
- `openpyxl`（仅 build_sheet.py 需要）
- MIDAS Civil NX（本机运行，供 API 重分析；或使用云端 MOA API）
- 一个能导出 DXF 的 CAD（中望 ZWCAD / AutoCAD；AcmeCADConverter 等第三方工具亦可）

### 配置 API Key

```bash
# 方式一：环境变量
export MIDAS_MAPI_KEY="your-key"

# 方式二：配置文件
cp config.example.json config.json
# 编辑 config.json 填入 mapi_key
```

> Key 从 MIDAS 官网（moa-engineers.midasit.cn）申请。**不要把真实 key 提交到公开仓库**（本仓库 `.gitignore` 已排除 `config.json`）。

## 快速开始

```bash
# 1. 解析一个 MCT（不需要 API）
python scripts/mct_parse.py 考生模型.mct out.json

# 2. 批量重分析（需 MIDAS 运行 + key）
cat > manifest.json << 'EOF'
[{"tag": "01_张三", "mcb": "D:/exam/01/模型.mcb"}]
EOF
python scripts/audit_models.py manifest.json outdir/ --tmp outdir/tmp_models

# 3. 质量扫描
python scripts/quality_check.py manifest.json

# 4. 图纸变量：先导出 DXF 再提取
#    (ZWCAD 脚本方式见 dxf_dims.py 头部注释)
python scripts/dxf_dims.py 图纸.dxf
python scripts/verify_vars.py 模型.mct --seat 26 --vars "900-n,3000+n,3600+n,5600+n,6000+n"

# 5. 评分表
python scripts/build_sheet.py 模板.xlsx scores.json 输出.xlsx
```

## 安全与合规

- 脚本**绝不直接打开考生原文件做分析**：先复制到临时目录再打开（API 分析会写回文件）
- 考生姓名、分数等个人数据属于敏感信息，请勿提交到公开仓库；本仓库只含工具与文档
- 变量核验只做几何比对（坐标差值），不涉及考生身份信息

## License

MIT
