from dataclasses import dataclass
from typing import List, Optional
import re

from app.config import settings
from text_cleaning import normalize_label


@dataclass
class Block:
    block_id: int
    heading: str
    text: str
    start_line: int
    end_line: int
    source_file: str = ""


# second-level structure inside a block.
@dataclass
class SubBlock:
    subblock_id: int
    parent_block_id: int
    parent_heading: str
    heading: str
    text: str
    start_line: int
    end_line: int
    marker_type: str
    source_file: str = ""


def is_heading_line(line: str) -> bool:
    """
    Return True if a line is a manual top-level header.

       Expected format:
           ### Header Name
    """
    return bool(re.fullmatch(r"###\s+.+", line.strip()))


def is_exact_marker_line(line: str) -> bool:
    """Return True if the stripped line matches one of our labels exactly."""
    return normalize_label(line) in settings.exact_markers


def is_faq_marker_line(line: str) -> bool:
    """Return True if a line is a FAQ line starting with Q: or A:.

    We keep this helper separate so it is easy to decide later whether FAQ
    should be split differently from the other sections.
    """
    stripped = line.strip()
    return stripped.startswith(settings.faq_prefixes)


def parse_blocks(text: str, source_file: str = "necrons.txt") -> List[Block]:
    """Split the text into blocks using ### headers as boundaries."""
    lines = text.split("\n")
    blocks: List[Block] = []
    current_heading = ""
    current_start_line: Optional[int] = None
    current_lines: List[str] = []
    block_id = 0

    def flush_block(end_line: int) -> None:
        nonlocal block_id, current_heading, current_start_line, current_lines
        if current_heading == "" and not current_lines:
            return

        block_text = "\n".join(current_lines).strip()
        if not block_text:
            # Skip empty blocks, but still reset state.
            current_heading = ""
            current_start_line = None
            current_lines = []
            return

        blocks.append(
            Block(
                block_id=block_id,
                heading=current_heading,
                text=block_text,
                start_line=current_start_line if current_start_line is not None else end_line,
                end_line=end_line,
                source_file=source_file,
            )
        )

        block_id += 1
        current_heading = ""
        current_start_line = None
        current_lines = []

    for line_no, line in enumerate(lines, start=1):
        if is_heading_line(line):
            # If we already have a block open, close it before starting a new one.
            if current_heading != "" or current_lines:
                flush_block(end_line=line_no - 1)

            current_heading = line.strip("# ").strip()
            current_start_line = line_no
            current_lines = []
            continue

        if current_heading == "" and not current_lines:
            # Skip leading lines until we find the first heading.
            continue

        current_lines.append(line)

    # Flush last block at EOF.
    if current_heading != "" or current_lines:
        flush_block(end_line=len(lines))

    return blocks


def split_block_into_subblocks(block: Block) -> List[SubBlock]:
    """
    Split a block into sub-blocks using exact marker lines as boundaries.
    Split one top-level block into smaller sub-blocks.

    The rule is simple:
    - if a line is exactly one of our markers, it starts a new sub-block
    - if the block is FAQ, we can later handle Q:/A: specially
    (for now this helper only marks them so the logic is explicit)
    """
    lines = block.text.split("\n")

    subblocks: List[SubBlock] = []
    current_heading = block.heading
    current_marker_type = "preface"
    current_start_line = block.start_line + 1
    current_lines: List[str] = []
    subblock_id = 0

    def flush_subblock(end_line: int) -> None:
        nonlocal subblock_id, current_heading, current_marker_type, current_start_line, current_lines
        text = "\n".join(current_lines).strip()
        if not text:
            # Skip empty sub-blocks, but still reset state.
            current_lines = []
            return

        subblocks.append(
            SubBlock(
                subblock_id=subblock_id,
                parent_block_id=block.block_id,
                parent_heading=block.heading,
                heading=current_heading,
                text=text,
                start_line=current_start_line,
                end_line=end_line,
                marker_type=current_marker_type,
                source_file=block.source_file,
            )
        )
        subblock_id += 1
        current_lines = []

    for line_no, line in enumerate(lines):
        original_line_no = block.start_line + 1 + line_no
        stripped = line.strip()

        # exact-line matching only.
        # This prevents matching labels inside a normal sentence.
        exact_marker = is_exact_marker_line(stripped)
        faq_marker = block.heading == "FAQ" and is_faq_marker_line(stripped)
        starts_new_subblock = exact_marker or faq_marker

        if starts_new_subblock:
            if current_lines:
                flush_subblock(end_line=original_line_no - 1)

            current_heading = stripped
            current_marker_type = "faq" if faq_marker else "exact"
            current_start_line = original_line_no
            current_lines = [line]
            continue

        if not current_lines:
            current_start_line = original_line_no

        current_lines.append(line)

    # Flush last sub-block at EOF.
    if current_lines:
        flush_subblock(end_line=block.end_line)

    return subblocks


def split_blocks_into_subblocks(blocks: List[Block]) -> List[SubBlock]:
    """Split all top-level blocks into sub-blocks."""
    all_subblocks: List[SubBlock] = []
    for block in blocks:
        all_subblocks.extend(split_block_into_subblocks(block))
    return all_subblocks
