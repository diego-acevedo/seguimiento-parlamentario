import io
from pathlib import Path

import markdown
from babel.dates import format_datetime
from jinja2 import Environment, FileSystemLoader
from markdown_pdf import MarkdownPdf, Section

from seguimiento_parlamentario.core.db import get_db
from seguimiento_parlamentario.core.utils import convert_datetime_strings_to_datetime

# Initialize database connection
db = get_db()


class SummaryFormatter:
    """
    Formats legislative summaries into Markdown, HTML, or PDF.

    This class retrieves session and commission metadata from the database
    and uses it to render summaries in different formats.
    """

    def get_metadata(self, summary):
        """
        Extract raw Markdown and fetch related session and commission metadata.

        Args:
            summary (dict): Dictionary containing the summary data.
                Expected keys:
                - "summary": str, the summary text (escaped with "\\n").
                - "session_id": str, the ID of the session.

        Returns:
            tuple:
                - str: The raw Markdown summary with newlines properly formatted.
                - dict: Session metadata with datetime values converted.
                - dict: Commission metadata.
        """
        raw_md = summary["summary"].replace("\\n", "\n")
        session = db.find_session(summary["session_id"])
        commission = db.find_commission(session["commission_id"])

        return raw_md, convert_datetime_strings_to_datetime(session), commission

    def to_markdown(self, summary):
        """
        Convert summary data into Markdown format with an introductory header.

        Args:
            summary (dict): Dictionary containing summary and session details.

        Returns:
            str: The formatted Markdown string.
        """
        raw_md, session, commission = self.get_metadata(summary)
        intro = f"""
**{commission["name"]} ({commission["chamber"]}) - {format_datetime(session['start'], "EEEE d 'de' MMMM 'de' y HH:mm", locale='es').capitalize()}**
"""
        return "\n".join([intro, raw_md])

    def to_html(self, summary):
        """
        Convert summary data into HTML format.

        Args:
            summary (dict): Dictionary containing summary and session details.

        Returns:
            str: The HTML representation of the summary.
        """
        md_format = self.to_markdown(summary)
        html_format = markdown.markdown(md_format)
        return html_format

    def to_pdf(self, summary):
        """
        Convert summary data into a styled PDF.

        Args:
            summary (dict): Dictionary containing summary and session details.

        Returns:
            io.BytesIO: A binary buffer containing the generated PDF.
        """
        md_format = self.to_markdown(summary)
        pdf = MarkdownPdf(toc_level=2, optimize=True)

        current_folder = Path(__file__).parent
        with open(current_folder / "styles.css", "r", encoding="utf-8") as styles:
            pdf.add_section(
                Section(md_format, paper_size="A4", borders=(50, 50, -50, -50)),
                user_css=styles.read(),
            )

        buffer = io.BytesIO()
        pdf.save(buffer)
        buffer.seek(0)

        return buffer


class MindmapFormatter:
    """
    Formats mindmap data into JSON or HTML.

    This class retrieves session and commission metadata and renders
    an HTML page for mindmaps using Jinja2 templates.
    """

    def to_json(self, mindmap):
        """
        Extract the raw JSON representation of the mindmap.

        Args:
            mindmap (dict): Dictionary containing the mindmap data.
                Expected keys:
                - "mindmap": dict, the structured mindmap data.

        Returns:
            dict: The mindmap JSON data.
        """
        return mindmap["mindmap"]

    def to_html(self, mindmap):
        """
        Render mindmap data into an HTML page using a Jinja2 template.

        Args:
            mindmap (dict): Dictionary containing mindmap and session details.
                Expected keys:
                - "mindmap": dict, the structured mindmap data.
                - "session_id": str, the ID of the session.

        Returns:
            str: Rendered HTML string.
        """
        json_mindmap = self.to_json(mindmap)
        session = db.find_session(mindmap["session_id"])
        commission = db.find_commission(session["commission_id"])

        env = Environment(loader=FileSystemLoader(Path(__file__).parent))
        template = env.get_template("mindmap.html")

        context = {
            "session": session,
            "commission": commission,
            "data": json_mindmap,
        }

        rendered_html = template.render(context)
        return rendered_html
