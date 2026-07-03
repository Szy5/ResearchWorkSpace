#!/usr/bin/env python3
"""一次性批量转换 artifacts 下 summary.md 中的 PDF 图片引用。"""

from __future__ import annotations

from pathlib import Path

from paper_wiki.core.config import get_settings
from paper_wiki.ingestion.summary_figure_converter import convert_summary_pdf_figures


def main() -> None:
    settings = get_settings()
    artifacts_dir = settings.resolved_artifacts_dir()
    raw_dir = settings.resolved_raw_dir()

    summaries = sorted(artifacts_dir.glob("*/summary.md"))
    total_converted = 0
    total_skipped = 0

    print(f"扫描 {len(summaries)} 个 summary.md ...")
    for summary_path in summaries:
        slug = summary_path.parent.name
        result = convert_summary_pdf_figures(
            summary_path,
            slug=slug,
            raw_dir=raw_dir,
            artifact_dir=summary_path.parent,
        )
        if not result.converted and not result.skipped:
            continue

        print(f"\n[{slug}]")
        for old, new in result.converted:
            print(f"  OK   {old} -> {new}")
        for ref, reason in result.skipped:
            print(f"  SKIP {ref}: {reason}")
        total_converted += len(result.converted)
        total_skipped += len(result.skipped)

    print(f"\n完成：converted={total_converted}, skipped={total_skipped}")


if __name__ == "__main__":
    main()
