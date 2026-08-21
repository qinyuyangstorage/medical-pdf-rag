## medrag（医疗 PDF → 高质量 RAG 知识库原型）

这个目录提供一套**可运行的端到端原型**，用于把医疗 PDF 自动处理为可追溯的 RAG 知识库数据（chunk JSONL），并提供一个轻量检索/问答接口骨架。

### 目录结构

- `src/medrag/`: 核心代码
- `scripts/`: 本地运行脚本
- `secrets/`: **本地密钥目录（不进 git）**

### 安装

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### MinerU 官方云端（A 路线：Precision Extract）

`mineru-open-sdk` 需要 **Python >= 3.10**。你这台机器通常可以用 Homebrew 的 `python3.13` 单独建 venv：

```bash
cd medical-pdf-rag
/opt/homebrew/bin/python3.13 -m venv .venv-mineru-cloud
source .venv-mineru-cloud/bin/activate
pip install -U pip
pip install mineru-open-sdk tqdm
```

把 token 放到这个文件（**你只需要编辑这一处**）：

`secrets/mineru_token.env`

内容一行：

```
MINERU_TOKEN=你的token
```

然后批量跑样例 PDF（输出每个 PDF 一个子目录）：

```bash
cd medical-pdf-rag
source .venv-mineru-cloud/bin/activate
python scripts/mineru_cloud_batch.py \
  --input_dir "./samples" \
  --out_dir "./mineru_cloud_out" \
  --model vlm \
  --language ch \
  --ocr --formula --table
```

### 快速开始（基于样例 PDF 生成 chunks）

```bash
python -m medrag.cli ingest \
  --input_dir "./samples" \
  --out_dir "./out"
```

输出：
- `out/docir/*.json`: 统一中间表示（DocIR）
- `out/chunks/*.jsonl`: 语义切片后的 chunk（可直接用于向量库/检索）

### 设计要点（后续接 MinerU）

当前默认解析器使用 PyMuPDF 做“可用性优先”的版面文本抽取，并保留 `page/bbox` 以做溯源。
如果你们已有 MinerU 的 JSON 输出，只需要实现 `medrag/parsers/mineru_adapter.py` 中的 `parse_mineru_json()`，把 MinerU JSON 映射到 `DocIR`，后续切片与入库逻辑无需改动。
