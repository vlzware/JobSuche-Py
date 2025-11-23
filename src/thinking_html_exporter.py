"""
HTML exporter for LLM thinking logs with clickable job references and tooltips
Uses external templates and styles for maintainability
"""

import re
from html import escape
from pathlib import Path

from .config import config
from .html_styles import THINKING_LOG_STYLES
from .html_templates import (
    THINKING_LOG_DOCUMENT,
    THINKING_LOG_JOB_ITEM,
    THINKING_LOG_JOBS_HEADER,
    THINKING_LOG_SCRIPT,
)


class ThinkingHTMLExporter:
    """Exports LLM thinking logs to interactive HTML with clickable refnrs"""

    def __init__(self):
        self.arbeitsagentur_base_url = config.get_required("api.arbeitsagentur.job_detail_url")

    def export_thinking(
        self,
        thinking_markdown: str,
        output_path: Path,
        batch_metadata: list[dict] | None = None,
        batch_label: str = "",
    ) -> str:
        """
        Export thinking log to HTML with clickable refnrs and tooltips

        Args:
            thinking_markdown: The markdown content from the thinking log
            output_path: Path where HTML file should be saved
            batch_metadata: Optional list of job metadata dicts for tooltips
                           [{"refnr": "...", "titel": "...", "ort": "...", "arbeitgeber": "..."}]
            batch_label: Optional label for this batch (e.g., "Batch 1")

        Returns:
            Path to the saved HTML file
        """
        # Build refnr to metadata mapping for tooltips
        refnr_map = {}
        if batch_metadata:
            for job in batch_metadata:
                refnr = job.get("refnr", "")
                if refnr:
                    refnr_map[refnr] = {
                        "titel": job.get("titel", "N/A"),
                        "ort": job.get("ort", "N/A"),
                        "arbeitgeber": job.get("arbeitgeber", "N/A"),
                    }

        # Build jobs header HTML
        jobs_header_html = self._build_jobs_header(batch_metadata) if batch_metadata else ""

        # Convert markdown to HTML with refnr links
        thinking_html = self._markdown_to_html(thinking_markdown, refnr_map)

        # Build batch label strings for title and header
        batch_label_title = f" - {escape(batch_label)}" if batch_label else ""
        batch_label_header = f" - {escape(batch_label)}" if batch_label else ""

        # Generate complete HTML document using template
        html_content = THINKING_LOG_DOCUMENT.format(
            batch_label_title=batch_label_title,
            batch_label_header=batch_label_header,
            css=THINKING_LOG_STYLES,
            jobs_header=jobs_header_html,
            thinking_html=thinking_html,
            javascript=THINKING_LOG_SCRIPT,
        )

        # Write to file
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        return str(output_path)

    def _build_jobs_header(self, batch_metadata: list[dict]) -> str:
        """Build the jobs header section listing all jobs in the batch"""
        job_items = []
        for job in batch_metadata:
            refnr = job.get("refnr", "N/A")
            titel = job.get("titel", "N/A")
            ort = job.get("ort", "N/A")
            arbeitgeber = job.get("arbeitgeber", "N/A")
            url = f"{self.arbeitsagentur_base_url}/{refnr}"

            job_items.append(
                THINKING_LOG_JOB_ITEM.format(
                    url=url,
                    refnr=escape(refnr),
                    titel=escape(titel),
                    ort=escape(ort),
                    arbeitgeber=escape(arbeitgeber),
                )
            )

        return THINKING_LOG_JOBS_HEADER.format(jobs_list="\n".join(job_items))

    def _markdown_to_html(self, markdown: str, refnr_map: dict[str, dict]) -> str:
        """
        Convert markdown to HTML with special handling for refnr patterns

        Handles: headers, bold, code blocks, line breaks, refnr patterns
        """
        html_lines = []
        in_code_block = False
        code_block_lines: list[str] = []

        for line in markdown.split("\n"):
            # Handle code blocks
            if line.strip().startswith("```"):
                if in_code_block:
                    # End code block
                    code_content = escape("\n".join(code_block_lines))
                    html_lines.append(f"<pre><code>{code_content}</code></pre>")
                    code_block_lines = []
                    in_code_block = False
                else:
                    # Start code block
                    in_code_block = True
                continue

            if in_code_block:
                code_block_lines.append(line)
                continue

            # Handle headers
            if line.startswith("# "):
                html_lines.append(f"<h1>{escape(line[2:])}</h1>")
            elif line.startswith("## "):
                html_lines.append(f"<h2>{escape(line[3:])}</h2>")
            elif line.startswith("### "):
                html_lines.append(f"<h3>{escape(line[4:])}</h3>")
            elif line.startswith("---"):
                html_lines.append("<hr>")
            elif line.strip() == "":
                html_lines.append("<br>")
            else:
                # Process inline formatting and refnr links
                processed_line = self._process_inline_formatting(line, refnr_map)
                html_lines.append(f"<p>{processed_line}</p>")

        # Close any remaining code block
        if in_code_block and code_block_lines:
            code_content = escape("\n".join(code_block_lines))
            html_lines.append(f"<pre><code>{code_content}</code></pre>")

        return "\n".join(html_lines)

    def _process_inline_formatting(self, text: str, refnr_map: dict[str, dict]) -> str:
        """Process inline markdown formatting and make refnrs clickable"""
        # First escape HTML
        text = escape(text)

        # Handle bold (**text**)
        text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)

        # Handle refnr patterns: [10001-1001417329-S] or [JOB_XXX]
        refnr_pattern = r"\[([0-9]+-[0-9]+-[A-Z]|JOB_\d+)\]"

        def replace_refnr(match):
            refnr = match.group(1)

            # Build tooltip and link if metadata available
            if refnr in refnr_map:
                metadata = refnr_map[refnr]
                tooltip = f"{metadata['titel']} | {metadata['ort']} | {metadata['arbeitgeber']}"
                url = f"{self.arbeitsagentur_base_url}/{refnr}"

                return (
                    f'<a href="{url}" target="_blank" '
                    f'class="refnr-link" '
                    f'data-tooltip="{escape(tooltip)}" '
                    f'id="job-{refnr}">[{refnr}]</a>'
                )
            else:
                # Refnr not in metadata
                if refnr.startswith("JOB_"):
                    # Just highlight JOB_XXX without link
                    return f'<span class="refnr-unknown">[{refnr}]</span>'
                else:
                    # Make it a link to Arbeitsagentur anyway
                    url = f"{self.arbeitsagentur_base_url}/{refnr}"
                    return f'<a href="{url}" target="_blank" class="refnr-link">[{refnr}]</a>'

        text = re.sub(refnr_pattern, replace_refnr, text)

        return text
