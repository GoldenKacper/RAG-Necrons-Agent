from __future__ import annotations

"""
Stage 1 - Preprocess a single rulebook text file into RAG-friendly chunks.

Pipeline steps:
1) read raw text
2) normalize whitespace
3) split into top-level blocks using `###`
4) split each block into sub-blocks using exact marker lines
5) build chunks:
   - FAQ: pair Q + A into one chunk
   - small sub-blocks: merge with the next ones inside the same block
   - large sub-blocks: split further by exact markers or paragraphs
6) save blocks, sub-blocks, and chunks to JSONL


This script is intentionally heuristic and file-friendly: it works well for a
single structured document like `necrons.txt` without requiring a full parser.
"""

from dataclasses import asdict
from pathlib import Path
from typing import List, Optional
import argparse
import json

from app.config import settings
from app.utils.text_cleaning import normalize_whitespace
from app.utils.preprocessing import Block, SubBlock, parse_blocks, split_blocks_into_subblocks
from app.utils.chunking import Chunk, build_chunks_from_subblocks


def write_jsonl(items: List[object], output_path: Path) -> None:
    """Write chunks to a JSONL file, one chunk per line."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(asdict(item), ensure_ascii=False) + "\n")


def write_report(blocks: List[Block], subblocks: List[SubBlock], chunks: List[Chunk], report_path: Path) -> None:
    """Write a simple Markdown report with preprocessing statistics and samples."""
    report_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Preprocessing report",
        "",
        f"- top-level blocks: {len(blocks)}",
        f"- sub-blocks: {len(subblocks)}",
        f"- chunks: {len(chunks)}",
        f"- avg tokens per chunk: {sum(c.token_estimate for c in chunks) / max(1, len(chunks)):.1f}",
        "",
        "## Top-level blocks",
        "",
    ]

    for block in blocks:
        preview = block.text[:220].replace("\n", " ")
        lines.extend(
            [
                f"### Block {block.block_id}",
                f"heading: {block.heading}",
                f"lines: {block.start_line}-{block.end_line}",
                f"chars: {len(block.text)}",
                "",
                preview,
                "",
            ]
        )

    lines.extend(["## Sub-blocks", ""])
    for subblock in subblocks[:40]:
        preview = subblock.text[:220].replace("\n", " ")
        lines.extend(
            [
                f"### SubBlock {subblock.subblock_id} (parent {subblock.parent_block_id})",
                f"heading: {subblock.heading}",
                f"marker_type: {subblock.marker_type}",
                f"lines: {subblock.start_line}-{subblock.end_line}",
                f"chars: {len(subblock.text)}",
                "",
                preview,
                "",
            ]
        )

    lines.extend(["## Chunks", ""])
    for chunk in chunks[:40]:
        preview = chunk.text[:220].replace("\n", " ")
        lines.extend(
            [
                f"### Chunk {chunk.chunk_id} ({chunk.kind})",
                f"parent_heading: {chunk.parent_heading}",
                f"heading: {chunk.heading}",
                f"lines: {chunk.start_line}-{chunk.end_line}",
                f"tokens: {chunk.token_estimate}",
                "",
                preview,
                "",
            ]
        )

    report_path.write_text("\n".join(lines), encoding="utf-8")


def preprocess(input_path: Path, output_path: Path, report_path: Optional[Path], min_tokens: int, max_tokens: int,
               overlap_tokens: int, no_report: bool) -> None:
    """Run the full preprocessing pipeline from raw text to structured chunks."""

    raw_text = input_path.read_text(encoding="utf-8", errors="ignore")
    cleaned_text = normalize_whitespace(raw_text)

    blocks = parse_blocks(cleaned_text, source_file=input_path.name)
    subblocks = split_blocks_into_subblocks(blocks)
    chunks = build_chunks_from_subblocks(subblocks, min_tokens=min_tokens, max_tokens=max_tokens,
                                         overlap_tokens=overlap_tokens)

    blocks_path = output_path.with_name(f"{output_path.stem}_blocks{output_path.suffix}")
    subblocks_path = output_path.with_name(f"{output_path.stem}_subblocks{output_path.suffix}")
    chunks_path = output_path.with_name(f"{output_path.stem}_chunks{output_path.suffix}")

    write_jsonl(blocks, blocks_path)
    write_jsonl(subblocks, subblocks_path)
    write_jsonl(chunks, chunks_path)

    if report_path is not None and not no_report:
        write_report(blocks, subblocks, chunks, report_path)

    print(f"Input file: {input_path}")
    print(f"Top-level blocks: {len(blocks)}")
    print(f"Sub-blocks: {len(subblocks)}")
    print(
        f"Chunks: {len(chunks)} | avg tokens/chunk: {sum(c.token_estimate for c in chunks) / max(1, len(chunks)):.1f} | min tokens/chunk: {min(c.token_estimate for c in chunks)} | max tokens/chunk: {max(c.token_estimate for c in chunks)}")
    print(f"Saved blocks JSONL: {blocks_path}")
    print(f"Saved sub-blocks JSONL: {subblocks_path}")
    print(f"Saved chunks JSONL: {chunks_path}")
    if report_path is not None and not no_report:
        print(f"Saved report: {report_path}")

    small_chunks = [c for c in chunks if c.token_estimate < min_tokens]
    print(f"Small chunks - {len(small_chunks)}")
    for chunk in small_chunks:
        print(f"Id - {chunk.chunk_id} | Tokens - {chunk.token_estimate} | Text - {chunk.text.replace(chr(10), ' ')}")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Preprocess necrons.txt into RAG chunks.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/raw/necrons.txt"),
        help="Path to the raw text file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/necrons.jsonl"),
        help="Path to the output JSONL file.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("data/processed/preprocess_report.md"),
        help="Optional markdown report path.",
    )
    parser.add_argument(
        "--min-tokens",
        type=int,
        default=settings.chunk_min_tokens,
        help="Target minimum size of a chunk in tokens.",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=settings.chunk_max_tokens,
        help="Target maximum size of a chunk in tokens.",
    )
    parser.add_argument(
        "--overlap-tokens",
        type=int,
        default=80,
        help="Approximate overlap size in tokens.",
    )
    parser.add_argument(
        "--no-report",
        action="store_true",
        help="Disable generation of the markdown report.",
    )
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    if not args.input.exists():
        raise FileNotFoundError(f"Input file not found: {args.input}")

    report_path = None if args.no_report else args.report
    preprocess(
        input_path=args.input,
        output_path=args.output,
        report_path=report_path,
        min_tokens=args.min_tokens,
        max_tokens=args.max_tokens,
        overlap_tokens=args.overlap_tokens,
        no_report=args.no_report
    )


if __name__ == "__main__":
    main()
