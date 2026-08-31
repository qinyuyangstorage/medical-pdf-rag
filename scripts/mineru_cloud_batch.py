from __future__ import annotations

import argparse
import os
from pathlib import Path

from tqdm import tqdm


def _load_dotenv_file(path: Path) -> None:
    """
    Minimal KEY=VALUE loader (no dependency on python-dotenv).
    - ignores blank lines and comments
    - does not override existing env vars
    """
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip("'").strip('"')
        if not k:
            continue
        os.environ.setdefault(k, v)


def _iter_inputs(input_dir: Path, exts: tuple[str, ...]) -> list[Path]:
    files: list[Path] = []
    for ext in exts:
        files.extend(sorted([p for p in input_dir.rglob(f"*{ext}") if p.is_file()]))
    # stable unique
    return sorted({p.resolve() for p in files}, key=lambda p: str(p))


def main() -> int:
    p = argparse.ArgumentParser(description="MinerU 官方云端 Precision Extract：批量解析目录内 PDF（A 路线）")
    p.add_argument("--input_dir", required=True, help="输入目录（递归扫描）")
    p.add_argument("--out_dir", required=True, help="输出目录（每个文件一个子目录）")
    p.add_argument("--model", default="vlm", choices=["vlm", "pipeline", "html"], help="云端模型选择（默认 vlm）")
    p.add_argument("--language", default="ch", help="语言参数（中文文献建议 ch；英文可 en）")
    p.add_argument("--ocr", action="store_true", help="开启 OCR（扫描件/水印遮挡建议开）")
    p.add_argument("--formula", action="store_true", help="开启公式识别（默认跟随 SDK/API 默认；显式开启）")
    p.add_argument("--table", action="store_true", help="开启表格识别（默认跟随 SDK/API 默认；显式开启）")
    p.add_argument("--timeout", type=int, default=1800, help="单文件最长等待秒数（默认 1800）")
    p.add_argument(
        "--token_file",
        default=str(Path(__file__).resolve().parents[1] / "secrets" / "mineru_token.env"),
        help="token 文件路径（默认 medrag/secrets/mineru_token.env）",
    )
    args = p.parse_args()

    token_file = Path(args.token_file)
    _load_dotenv_file(token_file)

    token = os.environ.get("MINERU_TOKEN", "").strip()
    if not token:
        print("缺少 MINERU_TOKEN。")
        print(f"请把 token 写入：{token_file}（一行：MINERU_TOKEN=...）")
        print("或临时：export MINERU_TOKEN='...'")
        return 2

    try:
        from mineru import MinerU  # type: ignore
    except ImportError as e:  # pragma: no cover
        print("未安装 mineru-open-sdk。请先在你的 Python3.10+ venv 里执行：pip install mineru-open-sdk")
        print(f"导入失败详情：{e!r}")
        return 3

    input_dir = Path(args.input_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    pdfs = _iter_inputs(input_dir, (".pdf",))
    if not pdfs:
        print(f"未找到 PDF：{input_dir}")
        return 2

    # 默认把三开关都打开：医疗文献更稳（代价是更慢/更贵一点，取决于云端计费策略）
    ocr = True if args.ocr else None
    formula = True if args.formula else None
    table = True if args.table else None

    with MinerU(token) as client:
        for pdf in tqdm(pdfs, desc="mineru-cloud"):
            safe_name = pdf.name
            target = out_dir / safe_name
            target.mkdir(parents=True, exist_ok=True)

            result = client.extract(
                str(pdf),
                model=args.model,
                ocr=ocr,
                formula=formula,
                table=table,
                language=args.language,
                timeout=int(args.timeout),
            )
            # save_all 会落 markdown/json/图片等资源（具体以 SDK 为准）
            result.save_all(str(target))

    print(f"完成：{len(pdfs)} 个文件")
    print(f"输出目录：{out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
