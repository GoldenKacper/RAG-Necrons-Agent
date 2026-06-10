from dataclasses import dataclass, field
from typing import List, Optional

from app.config import settings
from text_cleaning import normalize_label, estimate_tokens
from preprocessing import SubBlock

@dataclass
class Chunk:
    chunk_id: int
    parent_block_id: int
    parent_heading: str
    heading: str
    text: str
    start_line: int
    end_line: int
    token_estimate: int
    kind: str
    source_subblock_ids: List[int] = field(default_factory=list)
    source_file: str = ""


@dataclass
class Span:
    """Intermediate text fragment used while turning sub-blocks into chunks."""

    heading: str
    text: str
    start_line: int
    end_line: int
    kind: str
    source_subblock_ids: List[int] = field(default_factory=list)


def is_exact_marker_from_content_line(line: str) -> bool:
    """Return True if the stripped line matches one of our content labels exactly."""
    return normalize_label(line) in settings.exact_markers_from_content


def split_span_by_exact_markers(span: Span) -> List[Span]:
    """Split a text span by exact marker lines from content."""
    lines = span.text.split("\n")
    parts: List[Span] = []

    current_heading = span.heading
    current_start_line = span.start_line
    current_lines: List[str] = []
    current_kind = span.kind

    def flush(end_line: int) -> None:
        nonlocal current_lines, current_heading, current_start_line, current_kind
        text = "\n".join(current_lines).strip()
        if not text:
            current_lines = []
            return
        parts.append(
            Span(
                heading=current_heading,
                text=text,
                start_line=current_start_line,
                end_line=end_line,
                kind=current_kind,
                source_subblock_ids=span.source_subblock_ids.copy(),
            )
        )
        current_lines = []

    for idx, line in enumerate(lines):
        line_no = span.start_line + idx
        if is_exact_marker_from_content_line(line.strip()):
            if current_lines:
                flush(end_line=line_no - 1)
            current_heading = line.strip()
            current_start_line = line_no
            current_kind = "marker"
            current_lines = [line]
            continue

        if not current_lines:
            current_start_line = line_no
        current_lines.append(line)

    if current_lines:
        flush(end_line=span.end_line)

    return parts


def split_span_by_paragraphs(span: Span) -> List[Span]:
    """Split a span by paragraphs while preserving approximate line numbers."""
    lines = span.text.split("\n")
    parts: List[Span] = []

    current_lines: List[str] = []
    para_start_line: Optional[int] = None

    def flush(end_line: int) -> None:
        nonlocal current_lines, para_start_line
        text = "\n".join(current_lines).strip()
        if not text:
            current_lines = []
            para_start_line = None
            return

        parts.append(
            Span(
                heading=span.heading,
                text=text,
                start_line=para_start_line if para_start_line is not None else span.start_line,
                end_line=end_line,
                kind="paragraph",
                source_subblock_ids=span.source_subblock_ids.copy(),
            )
        )
        current_lines = []
        para_start_line = None

    for idx, line in enumerate(lines):
        line_no = span.start_line + idx
        if line.strip() == "":
            if current_lines:
                flush(end_line=line_no - 1)
            continue

        if not current_lines:
            para_start_line = line_no
        current_lines.append(line)

    if current_lines:
        flush(end_line=span.end_line)

    return parts


def expand_span(span: Span, max_tokens: int) -> List[Span]:
    """Recursively split large spans until they fit the target size."""
    if estimate_tokens(span.text) <= max_tokens:
        return [span]

    exact_parts = split_span_by_exact_markers(span)
    if len(exact_parts) > 1:
        expanded: List[Span] = []
        for part in exact_parts:
            expanded.extend(expand_span(part, max_tokens=max_tokens))
        return expanded

    paragraph_parts = split_span_by_paragraphs(span)
    if len(paragraph_parts) > 1:
        expanded = []
        for part in paragraph_parts:
            if estimate_tokens(part.text) > max_tokens and part.text != span.text:
                expanded.extend(expand_span(part, max_tokens=max_tokens))
            else:
                expanded.append(part)
        return expanded

    return [span]


def faq_subblocks_to_spans(subblocks: List[SubBlock]) -> List[Span]:
    """
    Convert FAQ subblocks to spans.

    Q: + A: are kept together as one atomic span.
    """
    spans: List[Span] = []
    i = 0

    while i < len(subblocks):
        current = subblocks[i]
        current_text = current.text.strip()

        if current_text.startswith("Q:") and i + 1 < len(subblocks):
            nxt = subblocks[i + 1]
            if nxt.text.strip().startswith("A:"):
                combined_text = current.text.strip() + "\n\n" + nxt.text.strip()
                spans.append(
                    Span(
                        heading=current.heading,
                        text=combined_text,
                        start_line=current.start_line,
                        end_line=nxt.end_line,
                        kind="faq_pair",
                        source_subblock_ids=[current.subblock_id, nxt.subblock_id],
                    )
                )
                i += 2
                continue

        spans.append(
            Span(
                heading=current.heading,
                text=current.text.strip(),
                start_line=current.start_line,
                end_line=current.end_line,
                kind="faq_single",
                source_subblock_ids=[current.subblock_id],
            )
        )
        i += 1

    return spans


def subblock_to_spans(subblock: SubBlock, max_tokens: int) -> List[Span]:
    """Convert a non-FAQ subblock into one or more candidate spans."""
    base_span = Span(
        heading=subblock.heading,
        text=subblock.text.strip(),
        start_line=subblock.start_line,
        end_line=subblock.end_line,
        kind=subblock.marker_type,
        source_subblock_ids=[subblock.subblock_id],
    )
    return expand_span(base_span, max_tokens=max_tokens)


def select_overlap_spans(spans: List[Span], overlap_tokens: int) -> List[Span]:
    """
    Take a small tail from the previous chunk so the next chunk keeps context.

    NEW: this is where overlap_tokens is used.
    """
    if overlap_tokens <= 0 or not spans:
        return []

    selected: List[Span] = []
    total = 0

    for span in reversed(spans):
        span_tokens = estimate_tokens(span.text)
        if selected and total + span_tokens > overlap_tokens:
            break

        selected.insert(0, span)
        total += span_tokens
        if total >= overlap_tokens:
            break

    return selected


def pack_spans_into_chunks(
        spans: List[Span],
        parent_block_id: int,
        parent_heading: str,
        source_file: str,
        min_tokens: int,
        max_tokens: int,
        overlap_tokens: int,
) -> List[Chunk]:
    """
    Pack spans into chunks.

    NEW:
    - min_tokens is used as a preference target for grouping small spans.
    - overlap_tokens is used to carry a small tail into the next chunk.
    """
    chunks: List[Chunk] = []
    buffer: List[Span] = []
    buffer_tokens = 0
    pending_overlap: List[Span] = []

    def start_buffer_from_overlap() -> None:
        nonlocal buffer, buffer_tokens, pending_overlap
        if pending_overlap:
            buffer = pending_overlap.copy()
            buffer_tokens = sum(estimate_tokens(span.text) for span in buffer)
            pending_overlap = []

    def flush_buffer() -> None:
        nonlocal buffer, buffer_tokens, pending_overlap
        if not buffer:
            return

        text = "\n\n".join(span.text for span in buffer).strip()
        chunks.append(
            Chunk(
                chunk_id=len(chunks),
                parent_block_id=parent_block_id,
                parent_heading=parent_heading,
                heading=buffer[0].heading,
                text=text,
                start_line=buffer[0].start_line,
                end_line=buffer[-1].end_line,
                token_estimate=estimate_tokens(text),
                kind="merged",
                source_subblock_ids=[sid for span in buffer for sid in span.source_subblock_ids],
                source_file=source_file,
            )
        )

        pending_overlap = select_overlap_spans(buffer, overlap_tokens)
        buffer = []
        buffer_tokens = 0

    for span in spans:
        span_tokens = estimate_tokens(span.text)

        # Safety valve: if a span is still too large, emit it as-is.
        # Normally expand_span() should already keep spans under max_tokens.
        if span_tokens > max_tokens:
            flush_buffer()
            chunks.append(
                Chunk(
                    chunk_id=len(chunks),
                    parent_block_id=parent_block_id,
                    parent_heading=parent_heading,
                    heading=span.heading,
                    text=span.text,
                    start_line=span.start_line,
                    end_line=span.end_line,
                    token_estimate=span_tokens,
                    kind=span.kind,
                    source_subblock_ids=span.source_subblock_ids.copy(),
                    source_file=source_file,
                )
            )
            pending_overlap = select_overlap_spans([span], overlap_tokens)
            continue

        if not buffer:
            start_buffer_from_overlap()

        # NEW: if the current span still fits and the current buffer has not
        # reached the preferred minimum size yet, keep merging.
        if buffer and buffer_tokens < min_tokens and buffer_tokens + span_tokens <= max_tokens:
            buffer.append(span)
            buffer_tokens += span_tokens
            continue

        # If the current span fits, but the buffer already reached the minimum
        # target, flush first so we avoid very large chunks.
        if buffer and buffer_tokens >= min_tokens:
            flush_buffer()
            start_buffer_from_overlap()

            if buffer and buffer_tokens + span_tokens > max_tokens:
                # The overlap itself was too large; drop it to avoid deadlock.
                buffer = []
                buffer_tokens = 0

        # If the span still does not fit, flush whatever is in the buffer first.
        if buffer and buffer_tokens + span_tokens > max_tokens:
            flush_buffer()
            start_buffer_from_overlap()

            if buffer and buffer_tokens + span_tokens > max_tokens:
                buffer = []
                buffer_tokens = 0

        # Add current span.
        if not buffer:
            buffer = [span]
            buffer_tokens = span_tokens
        else:
            buffer.append(span)
            buffer_tokens += span_tokens

    flush_buffer()
    return chunks


def build_chunks_from_subblocks(
        subblocks: List[SubBlock],
        min_tokens: int,
        max_tokens: int,
        overlap_tokens: int,
) -> List[Chunk]:
    """Build final chunks from sub-blocks."""
    chunks: List[Chunk] = []

    grouped: dict[int, List[SubBlock]] = {}
    for subblock in subblocks:
        grouped.setdefault(subblock.parent_block_id, []).append(subblock)

    for parent_block_id in sorted(grouped.keys()):
        parent_subblocks = grouped[parent_block_id]
        parent_heading = parent_subblocks[0].parent_heading if parent_subblocks else ""
        source_file = parent_subblocks[0].source_file if parent_subblocks else ""

        # NEW: FAQ stays special because Q + A should remain together.
        if parent_heading == "FAQ":
            spans = faq_subblocks_to_spans(parent_subblocks)
            chunks.extend(
                pack_spans_into_chunks(
                    spans=spans,
                    parent_block_id=parent_block_id,
                    parent_heading=parent_heading,
                    source_file=source_file,
                    min_tokens=0,
                    max_tokens=max_tokens,
                    overlap_tokens=0,
                )
            )
            continue

        spans: List[Span] = []
        for subblock in parent_subblocks:
            spans.extend(subblock_to_spans(subblock, max_tokens=max_tokens))

        chunks.extend(
            pack_spans_into_chunks(
                spans=spans,
                parent_block_id=parent_block_id,
                parent_heading=parent_heading,
                source_file=source_file,
                min_tokens=min_tokens,
                max_tokens=max_tokens,
                overlap_tokens=overlap_tokens,
            )
        )

    for i, chunk in enumerate(chunks):
        chunk.chunk_id = i

    return chunks
