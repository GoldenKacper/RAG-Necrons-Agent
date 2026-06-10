import math
import re


def normalize_label(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def normalize_whitespace(text: str) -> str:
    """
    Normalize extracted text for downstream parsing.

    This function:
    - normalizes line endings to LF,
    - removes BOM characters,
    - trims leading and trailing whitespace from each line,
    - drops isolated numeric lines such as page numbers,
    - collapses repeated internal whitespace,
    - and reduces excessive blank lines.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\ufeff", "")
    lines = []
    for raw_line in text.split("\n"):
        line = raw_line.strip()

        # Remove isolated page numbers / artefacts like "1" or "27".
        if re.fullmatch(r"\d+", line):
            continue

        # Remove repeated whitespace inside the line.
        line = re.sub(r"\s+", " ", line)
        lines.append(line)

    # Collapse excessive blank lines.
    cleaned = "\n".join(lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def estimate_tokens(text: str) -> int:
    """
    Estimate the number of tokens in text.

    Uses tiktoken when available for a more accurate count. If tiktoken is not
    installed, falls back to a lightweight word-based heuristic.
    """
    try:
        import tiktoken  # type: ignore

        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        # Fallback heuristic: approximate token count from whitespace-separated words.
        words = len(re.findall(r"\S+", text))
        return max(1, math.ceil(words * 1.3))
