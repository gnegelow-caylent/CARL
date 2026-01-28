"""
Document Generator for CARL Reports.

Converts markdown reports to professional PDF documents using ReportLab.
"""

import re
from io import BytesIO
from datetime import datetime
from typing import Optional

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib import colors

from utils.logger import get_logger

logger = get_logger(__name__)


class DocumentGenerator:
    """Generate professional PDF documents from markdown reports."""

    def __init__(self):
        """Initialize the document generator."""
        self.styles = getSampleStyleSheet()

        # Add custom styles
        self.styles.add(ParagraphStyle(
            name='CenterTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            alignment=TA_CENTER,
            spaceAfter=12
        ))

        self.styles.add(ParagraphStyle(
            name='CenterSubtitle',
            parent=self.styles['Normal'],
            fontSize=14,
            alignment=TA_CENTER,
            textColor=colors.grey,
            spaceAfter=6
        ))

    def markdown_to_pdf(self, markdown_content: str, title: str = "CARL Compliance Report") -> BytesIO:
        """
        Convert markdown content to a formatted PDF document.

        Args:
            markdown_content: The markdown content to convert
            title: The document title

        Returns:
            BytesIO object containing the PDF document
        """
        logger.info(f"Generating PDF document: {title}")

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18,
        )

        # Container for the 'Flowable' objects
        elements = []

        # Add title
        elements.append(Paragraph(title, self.styles['CenterTitle']))
        elements.append(Spacer(1, 12))

        # Add generation timestamp
        timestamp_text = f"<i>Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</i>"
        elements.append(Paragraph(timestamp_text, self.styles['CenterSubtitle']))
        elements.append(Spacer(1, 24))

        # Parse markdown and convert to PDF elements
        lines = markdown_content.split('\n')
        i = 0
        in_code_block = False
        code_lines = []

        while i < len(lines):
            line = lines[i]

            # Handle code blocks
            if line.strip().startswith('```'):
                if not in_code_block:
                    in_code_block = True
                    code_lines = []
                else:
                    # End of code block - add it to document
                    if code_lines:
                        code_text = '<pre>' + '<br/>'.join(code_lines) + '</pre>'
                        elements.append(Paragraph(code_text, self.styles['Code']))
                        elements.append(Spacer(1, 12))
                    in_code_block = False
                    code_lines = []
                i += 1
                continue

            if in_code_block:
                code_lines.append(line.replace('<', '&lt;').replace('>', '&gt;'))
                i += 1
                continue

            # Handle headings
            if line.startswith('# '):
                elements.append(Spacer(1, 12))
                elements.append(Paragraph(line[2:], self.styles['Heading1']))
                elements.append(Spacer(1, 6))
            elif line.startswith('## '):
                elements.append(Spacer(1, 12))
                elements.append(Paragraph(line[3:], self.styles['Heading2']))
                elements.append(Spacer(1, 6))
            elif line.startswith('### '):
                elements.append(Spacer(1, 12))
                elements.append(Paragraph(line[4:], self.styles['Heading3']))
                elements.append(Spacer(1, 6))
            elif line.startswith('#### '):
                elements.append(Spacer(1, 12))
                elements.append(Paragraph(line[5:], self.styles['Heading4']))
                elements.append(Spacer(1, 6))

            # Handle horizontal rules
            elif line.strip() in ['---', '***', '___']:
                elements.append(Spacer(1, 12))

            # Handle bullet lists
            elif line.strip().startswith('- ') or line.strip().startswith('* '):
                content = line.strip()[2:]
                # Convert markdown bold to HTML
                content = content.replace('**', '<b>', 1).replace('**', '</b>', 1)
                elements.append(Paragraph(f"• {content}", self.styles['Normal']))
                elements.append(Spacer(1, 3))

            # Handle numbered lists
            elif re.match(r'^\d+\.\s', line.strip()):
                content = re.sub(r'^(\d+)\.\s', r'\1. ', line.strip())
                content = content.replace('**', '<b>', 1).replace('**', '</b>', 1)
                elements.append(Paragraph(content, self.styles['Normal']))
                elements.append(Spacer(1, 3))

            # Handle bold text emphasis
            elif '**' in line and line.strip():
                # Convert markdown bold to HTML bold
                formatted = line
                while '**' in formatted:
                    formatted = formatted.replace('**', '<b>', 1).replace('**', '</b>', 1)
                elements.append(Paragraph(formatted, self.styles['Normal']))
                elements.append(Spacer(1, 6))

            # Handle blank lines
            elif not line.strip():
                elements.append(Spacer(1, 12))

            # Regular paragraphs
            else:
                if line.strip():
                    # Clean up and escape HTML
                    clean_line = line.replace('_', '').replace('`', '')
                    clean_line = clean_line.replace('<', '&lt;').replace('>', '&gt;')
                    elements.append(Paragraph(clean_line, self.styles['Normal']))
                    elements.append(Spacer(1, 6))

            i += 1

        # Build PDF
        doc.build(elements)
        buffer.seek(0)

        logger.info("PDF document generated successfully")
        return buffer

    def create_executive_summary_pdf(
        self,
        markdown_content: str,
        organization_name: str = "Organization",
        audit_period: str = ""
    ) -> BytesIO:
        """
        Create a specially formatted executive summary PDF document.

        Args:
            markdown_content: The markdown content
            organization_name: Organization name for the cover
            audit_period: Audit period for the cover

        Returns:
            BytesIO object containing the PDF document
        """
        logger.info(f"Generating executive summary PDF for {organization_name}")

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18,
        )

        elements = []

        # Cover page
        elements.append(Spacer(1, 2*inch))

        cover_style = ParagraphStyle(
            'CoverTitle',
            parent=self.styles['Heading1'],
            fontSize=32,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#1a237e')
        )
        elements.append(Paragraph('SOC 2 Type II', cover_style))
        elements.append(Spacer(1, 12))

        subtitle_style = ParagraphStyle(
            'CoverSubtitle',
            parent=self.styles['Heading2'],
            fontSize=24,
            alignment=TA_CENTER
        )
        elements.append(Paragraph('Executive Summary', subtitle_style))
        elements.append(Spacer(1, 48))

        org_style = ParagraphStyle(
            'OrgName',
            parent=self.styles['Normal'],
            fontSize=18,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#424242')
        )
        elements.append(Paragraph(f"<b>{organization_name}</b>", org_style))

        if audit_period:
            elements.append(Spacer(1, 12))
            period_style = ParagraphStyle(
                'Period',
                parent=self.styles['Normal'],
                fontSize=14,
                alignment=TA_CENTER
            )
            elements.append(Paragraph(f"Audit Period: {audit_period}", period_style))

        elements.append(Spacer(1, 48))

        date_style = ParagraphStyle(
            'GenDate',
            parent=self.styles['Normal'],
            fontSize=12,
            alignment=TA_CENTER,
            textColor=colors.grey
        )
        elements.append(Paragraph(f"<i>Generated: {datetime.utcnow().strftime('%B %d, %Y')}</i>", date_style))

        # Page break
        elements.append(PageBreak())

        # Add content using markdown_to_pdf parsing
        lines = markdown_content.split('\n')
        for line in lines:
            if line.startswith('# '):
                elements.append(Spacer(1, 12))
                elements.append(Paragraph(line[2:], self.styles['Heading1']))
                elements.append(Spacer(1, 6))
            elif line.startswith('## '):
                elements.append(Spacer(1, 12))
                elements.append(Paragraph(line[3:], self.styles['Heading2']))
                elements.append(Spacer(1, 6))
            elif line.startswith('### '):
                elements.append(Spacer(1, 12))
                elements.append(Paragraph(line[4:], self.styles['Heading3']))
                elements.append(Spacer(1, 6))
            elif line.strip().startswith('- '):
                content = line.strip()[2:].replace('**', '<b>', 1).replace('**', '</b>', 1)
                elements.append(Paragraph(f"• {content}", self.styles['Normal']))
                elements.append(Spacer(1, 3))
            elif line.strip().startswith('**') and line.strip().endswith('**'):
                content = line.strip()[2:-2]
                elements.append(Paragraph(f"<b>{content}</b>", self.styles['Normal']))
                elements.append(Spacer(1, 6))
            elif line.strip():
                clean_line = line.replace('_', '').replace('`', '')
                clean_line = clean_line.replace('<', '&lt;').replace('>', '&gt;')
                elements.append(Paragraph(clean_line, self.styles['Normal']))
                elements.append(Spacer(1, 6))

        # Build PDF
        doc.build(elements)
        buffer.seek(0)

        logger.info("Executive summary PDF generated successfully")
        return buffer
