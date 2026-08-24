import re
import markdown
from typing import List, Dict

from ..sources.registry import SourceRecord, SourceRegistry
from ..sources.validator import normalize_url


_SOURCE_ID_PATTERN = re.compile(r"\[(S\d+)\]", re.IGNORECASE)
_REFERENCE_SECTION_PATTERN = re.compile(
    r"(?ims)^##\s+(?:references|参考文献)\s*$.*\Z"
)
_MARKDOWN_LINK_PATTERN = re.compile(
    r"(?<!!)\[([^\]]+)\]\((https?://[^)\s]+)\)", re.IGNORECASE
)
_BARE_URL_PATTERN = re.compile(r"(?<!\]\()https?://[^\s)>]+", re.IGNORECASE)


def render_source_context(records: List[SourceRecord]) -> str:
    """Render model-visible evidence without exposing source URLs."""
    blocks = []
    for record in records:
        title = record.title.strip() or "Untitled source"
        blocks.append(f"[{record.source_id}] {title}\n{record.clean_content}")
    return "\n\n".join(blocks)


def build_source_citation_instruction(records: List[SourceRecord]) -> str:
    """Tell the writer to cite only stable IDs from admitted evidence."""
    source_ids = ", ".join(record.source_id for record in records)
    if not source_ids:
        return ""
    return (
        "CITATION WHITELIST:\n"
        f"- Allowed source IDs: {source_ids}.\n"
        "- Cite supporting claims using only [S1], [S2], and other allowed IDs.\n"
        "- Do not invent source IDs, URLs, hyperlinks, or a References section.\n"
        "- A post-processing step will render validated links and references."
    )


def extract_cited_source_ids(report_markdown: str) -> List[str]:
    """Return cited source IDs once, preserving first-seen order."""
    seen = set()
    source_ids = []
    for match in _SOURCE_ID_PATTERN.finditer(report_markdown or ""):
        source_id = match.group(1).upper()
        if source_id not in seen:
            seen.add(source_id)
            source_ids.append(source_id)
    return source_ids


def render_validated_references(
    report_markdown: str,
    registry: SourceRegistry,
) -> str:
    """Render citations and references exclusively from admitted sources."""
    report_body = _REFERENCE_SECTION_PATTERN.sub("", report_markdown or "").rstrip()
    records_by_id = {
        record.source_id: record for record in registry.usable_records()
    }
    usable_urls = set(registry.usable_urls())

    cited_ids = [
        source_id
        for source_id in extract_cited_source_ids(report_body)
        if source_id in records_by_id
    ]
    for source_id in cited_ids:
        registry.mark_cited(source_id)

    def replace_source_id(match: re.Match) -> str:
        source_id = match.group(1).upper()
        record = records_by_id.get(source_id)
        if record is None:
            return ""
        return f"[{source_id}]({record.canonical_url})"

    report_body = _SOURCE_ID_PATTERN.sub(replace_source_id, report_body)

    def sanitize_markdown_link(match: re.Match) -> str:
        label, url = match.groups()
        try:
            canonical_url = normalize_url(url)
        except ValueError:
            return label
        if canonical_url not in usable_urls:
            return label
        return f"[{label}]({canonical_url})"

    report_body = _MARKDOWN_LINK_PATTERN.sub(sanitize_markdown_link, report_body)

    def sanitize_bare_url(match: re.Match) -> str:
        url = match.group(0)
        try:
            canonical_url = normalize_url(url)
        except ValueError:
            return ""
        return canonical_url if canonical_url in usable_urls else ""

    report_body = _BARE_URL_PATTERN.sub(sanitize_bare_url, report_body)

    if not cited_ids:
        return report_body

    references = ["", "", "## References", ""]
    for source_id in cited_ids:
        record = records_by_id[source_id]
        title = record.title.strip() or source_id
        references.append(
            f"- [{title}]({record.canonical_url}) [{source_id}]"
        )
    return report_body + "\n".join(references) + "\n"

def extract_headers(markdown_text: str) -> List[Dict]:
    """
    Extract headers from markdown text.

    Args:
        markdown_text (str): The markdown text to process.

    Returns:
        List[Dict]: A list of dictionaries representing the header structure.
    """
    headers = []
    parsed_md = markdown.markdown(markdown_text)
    lines = parsed_md.split("\n")

    stack = []
    for line in lines:
        if line.startswith("<h") and len(line) > 2 and line[2].isdigit():
            level = int(line[2])
            header_text = line[line.index(">") + 1 : line.rindex("<")]

            while stack and stack[-1]["level"] >= level:
                stack.pop()

            header = {
                "level": level,
                "text": header_text,
            }
            if stack:
                stack[-1].setdefault("children", []).append(header)
            else:
                headers.append(header)

            stack.append(header)

    return headers

def extract_sections(markdown_text: str) -> List[Dict[str, str]]:
    """
    Extract all written sections from subtopic report.

    Args:
        markdown_text (str): Subtopic report text.

    Returns:
        List[Dict[str, str]]: List of sections, each section is a dictionary containing
        'section_title' and 'written_content'.
    """
    sections = []
    parsed_md = markdown.markdown(markdown_text)
    
    pattern = r'<h\d>(.*?)</h\d>(.*?)(?=<h\d>|$)'
    matches = re.findall(pattern, parsed_md, re.DOTALL)
    
    for title, content in matches:
        clean_content = re.sub(r'<.*?>', '', content).strip()
        if clean_content:
            sections.append({
                "section_title": title.strip(),
                "written_content": clean_content
            })
    
    return sections

def table_of_contents(markdown_text: str) -> str:
    """
    Generate a table of contents for the given markdown text.

    Args:
        markdown_text (str): The markdown text to process.

    Returns:
        str: The generated table of contents.
    """
    def generate_table_of_contents(headers, indent_level=0):
        toc = ""
        for header in headers:
            toc += " " * (indent_level * 4) + "- " + header["text"] + "\n"
            if "children" in header:
                toc += generate_table_of_contents(header["children"], indent_level + 1)
        return toc

    try:
        headers = extract_headers(markdown_text)
        toc = "## Table of Contents\n\n" + generate_table_of_contents(headers)
        return toc
    except Exception as e:
        print("table_of_contents Exception : ", e)
        return markdown_text

def add_references(report_markdown: str, visited_urls: set) -> str:
    """
    Add references to the markdown report.

    Args:
        report_markdown (str): The existing markdown report.
        visited_urls (set): A set of URLs that have been visited during research.

    Returns:
        str: The updated markdown report with added references.
    """
    try:
        url_markdown = "\n\n\n## References\n\n"
        url_markdown += "".join(f"- [{url}]({url})\n" for url in visited_urls)
        updated_markdown_report = report_markdown + url_markdown
        return updated_markdown_report
    except Exception as e:
        print(f"Encountered exception in adding source urls : {e}")
        return report_markdown
