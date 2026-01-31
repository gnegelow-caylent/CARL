"""
Professional PDF Report Generator for CARL.

Generates audit-ready PDF reports with:
- Clean, professional design
- Charts and visualizations
- Tables with proper formatting
- Executive summary with key metrics
- Detailed control assessments
- Trend analysis

Uses WeasyPrint for HTML→PDF conversion with full CSS support.
"""

import io
import base64
from datetime import datetime
from typing import Any, Optional
from dataclasses import dataclass
import boto3
from weasyprint import HTML, CSS
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for Lambda
import matplotlib.pyplot as plt
from matplotlib.patches import Wedge
import numpy as np

from utils.logger import get_logger

logger = get_logger(__name__)


class PDFReportGenerator:
    """Generates professional PDF reports from report data."""

    # Professional color palette
    COLORS = {
        'primary': '#1e40af',      # Blue
        'secondary': '#64748b',    # Slate
        'success': '#10b981',      # Green
        'warning': '#f59e0b',      # Amber
        'danger': '#ef4444',       # Red
        'background': '#f8fafc',   # Light gray
        'text': '#1e293b',         # Dark gray
        'border': '#e2e8f0'        # Light border
    }

    def __init__(self):
        self.s3_client = boto3.client('s3')

    def generate_compliance_score_chart(self, score: float, width: int = 400, height: int = 300) -> str:
        """
        Generate a professional compliance score gauge chart.

        Args:
            score: Compliance score (0-100)
            width: Chart width in pixels
            height: Chart height in pixels

        Returns:
            Base64 encoded PNG image
        """
        fig, ax = plt.subplots(figsize=(width/100, height/100), dpi=100)
        ax.set_xlim(-1.5, 1.5)
        ax.set_ylim(-1.5, 1.5)
        ax.set_aspect('equal')
        ax.axis('off')

        # Background arc (gray)
        background = Wedge((0, 0), 1, 0, 180, width=0.3,
                          facecolor='#e5e7eb', edgecolor='none')
        ax.add_patch(background)

        # Score arc (colored based on score)
        if score >= 80:
            color = '#10b981'  # Green
        elif score >= 60:
            color = '#f59e0b'  # Amber
        else:
            color = '#ef4444'  # Red

        angle = 180 * (score / 100)
        score_arc = Wedge((0, 0), 1, 0, angle, width=0.3,
                         facecolor=color, edgecolor='none')
        ax.add_patch(score_arc)

        # Score text in center
        ax.text(0, -0.3, f'{score:.0f}%',
               ha='center', va='center',
               fontsize=48, fontweight='bold', color=color)
        ax.text(0, -0.7, 'COMPLIANCE SCORE',
               ha='center', va='center',
               fontsize=12, color='#64748b')

        # Save to bytes
        buf = io.BytesIO()
        plt.tight_layout()
        plt.savefig(buf, format='png', transparent=True, bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)

        # Return base64 encoded
        return base64.b64encode(buf.read()).decode('utf-8')

    def generate_findings_chart(self, findings_by_severity: dict, width: int = 600, height: int = 400) -> str:
        """
        Generate a bar chart of findings by severity.

        Args:
            findings_by_severity: Dict like {'critical': 2, 'high': 5, 'medium': 12, 'low': 8}

        Returns:
            Base64 encoded PNG image
        """
        severities = ['Critical', 'High', 'Medium', 'Low']
        counts = [
            findings_by_severity.get('critical', 0),
            findings_by_severity.get('high', 0),
            findings_by_severity.get('medium', 0),
            findings_by_severity.get('low', 0)
        ]
        colors = ['#ef4444', '#f59e0b', '#fbbf24', '#10b981']

        fig, ax = plt.subplots(figsize=(width/100, height/100), dpi=100)
        bars = ax.bar(severities, counts, color=colors, alpha=0.8, edgecolor='white', linewidth=2)

        # Add value labels on bars
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{int(height)}',
                       ha='center', va='bottom', fontsize=14, fontweight='bold')

        ax.set_ylabel('Number of Findings', fontsize=12, color='#64748b')
        ax.set_title('Findings by Severity', fontsize=14, fontweight='bold', color='#1e293b', pad=20)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color('#e5e7eb')
        ax.spines['bottom'].set_color('#e5e7eb')
        ax.tick_params(colors='#64748b')
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        ax.set_axisbelow(True)

        # Save to bytes
        buf = io.BytesIO()
        plt.tight_layout()
        plt.savefig(buf, format='png', transparent=False, facecolor='white', bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)

        return base64.b64encode(buf.read()).decode('utf-8')

    def generate_trend_chart(self, dates: list, scores: list, width: int = 600, height: int = 300) -> str:
        """
        Generate a line chart showing compliance score trend.

        Args:
            dates: List of date strings
            scores: List of compliance scores

        Returns:
            Base64 encoded PNG image
        """
        fig, ax = plt.subplots(figsize=(width/100, height/100), dpi=100)

        ax.plot(range(len(dates)), scores, marker='o', linewidth=3,
               markersize=8, color='#1e40af', markerfacecolor='white',
               markeredgewidth=2, markeredgecolor='#1e40af')

        ax.set_xticks(range(len(dates)))
        ax.set_xticklabels(dates, rotation=45, ha='right')
        ax.set_ylabel('Compliance Score (%)', fontsize=12, color='#64748b')
        ax.set_title('Compliance Score Trend', fontsize=14, fontweight='bold', color='#1e293b', pad=20)
        ax.set_ylim(0, 100)

        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color('#e5e7eb')
        ax.spines['bottom'].set_color('#e5e7eb')
        ax.tick_params(colors='#64748b')
        ax.grid(True, alpha=0.3, linestyle='--')
        ax.set_axisbelow(True)

        # Save to bytes
        buf = io.BytesIO()
        plt.tight_layout()
        plt.savefig(buf, format='png', transparent=False, facecolor='white', bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)

        return base64.b64encode(buf.read()).decode('utf-8')

    def generate_html_template(self, report_data: dict) -> str:
        """
        Generate professional HTML template for PDF report.

        Args:
            report_data: Dictionary with report content

        Returns:
            HTML string
        """
        # Generate charts
        compliance_score = report_data.get('compliance_score', 0)
        findings_by_severity = report_data.get('findings_by_severity', {})

        score_chart = self.generate_compliance_score_chart(compliance_score)
        findings_chart = self.generate_findings_chart(findings_by_severity)

        # Build HTML
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        @page {{
            size: letter;
            margin: 0.75in;
            @bottom-right {{
                content: "Page " counter(page) " of " counter(pages);
                font-size: 10px;
                color: #64748b;
            }}
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            color: #1e293b;
            line-height: 1.6;
            font-size: 11pt;
        }}

        h1 {{
            color: #1e40af;
            font-size: 28pt;
            font-weight: 700;
            margin-bottom: 0.5em;
            page-break-after: avoid;
        }}

        h2 {{
            color: #1e40af;
            font-size: 18pt;
            font-weight: 600;
            margin-top: 1.5em;
            margin-bottom: 0.5em;
            border-bottom: 2px solid #e2e8f0;
            padding-bottom: 0.3em;
            page-break-after: avoid;
        }}

        h3 {{
            color: #475569;
            font-size: 14pt;
            font-weight: 600;
            margin-top: 1em;
            margin-bottom: 0.5em;
            page-break-after: avoid;
        }}

        .cover-page {{
            text-align: center;
            page-break-after: always;
            padding-top: 3in;
        }}

        .cover-title {{
            font-size: 36pt;
            font-weight: 700;
            color: #1e40af;
            margin-bottom: 0.5em;
        }}

        .cover-subtitle {{
            font-size: 18pt;
            color: #64748b;
            margin-bottom: 2em;
        }}

        .cover-meta {{
            font-size: 12pt;
            color: #64748b;
            line-height: 2;
        }}

        .executive-summary {{
            background: #f8fafc;
            padding: 1.5em;
            border-radius: 8px;
            margin-bottom: 2em;
            page-break-inside: avoid;
        }}

        .metric-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 1em;
            margin: 1.5em 0;
        }}

        .metric-card {{
            background: white;
            padding: 1em;
            border-radius: 6px;
            border: 1px solid #e2e8f0;
            text-align: center;
        }}

        .metric-value {{
            font-size: 24pt;
            font-weight: 700;
            color: #1e40af;
            display: block;
        }}

        .metric-label {{
            font-size: 10pt;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-top: 0.5em;
        }}

        .chart-container {{
            text-align: center;
            margin: 2em 0;
            page-break-inside: avoid;
        }}

        .chart-container img {{
            max-width: 100%;
            height: auto;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 1em 0;
            page-break-inside: avoid;
        }}

        th {{
            background: #1e40af;
            color: white;
            padding: 0.75em;
            text-align: left;
            font-weight: 600;
            font-size: 10pt;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        td {{
            padding: 0.75em;
            border-bottom: 1px solid #e2e8f0;
        }}

        tr:nth-child(even) {{
            background: #f8fafc;
        }}

        .badge {{
            display: inline-block;
            padding: 0.25em 0.75em;
            border-radius: 4px;
            font-size: 9pt;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        .badge-critical {{ background: #fee2e2; color: #991b1b; }}
        .badge-high {{ background: #fef3c7; color: #92400e; }}
        .badge-medium {{ background: #fef9c3; color: #854d0e; }}
        .badge-low {{ background: #d1fae5; color: #065f46; }}
        .badge-compliant {{ background: #d1fae5; color: #065f46; }}
        .badge-partial {{ background: #fef3c7; color: #92400e; }}
        .badge-non-compliant {{ background: #fee2e2; color: #991b1b; }}

        .status-icon {{
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 0.5em;
        }}

        .status-pass {{ background: #10b981; }}
        .status-fail {{ background: #ef4444; }}
        .status-warning {{ background: #f59e0b; }}

        .page-break {{ page-break-before: always; }}

        .footer {{
            margin-top: 2em;
            padding-top: 1em;
            border-top: 1px solid #e2e8f0;
            font-size: 9pt;
            color: #64748b;
            text-align: center;
        }}
    </style>
</head>
<body>
    <!-- Cover Page -->
    <div class="cover-page">
        <div class="cover-title">Compliance Report</div>
        <div class="cover-subtitle">{report_data.get('report_type', 'SOC 2 Type II')}</div>
        <div class="cover-meta">
            <div><strong>Audit Period:</strong> {report_data.get('audit_period', 'N/A')}</div>
            <div><strong>Generated:</strong> {report_data.get('generated_at', datetime.utcnow().strftime('%B %d, %Y'))}</div>
            <div><strong>Organization:</strong> {report_data.get('organization', 'CARL')}</div>
        </div>
    </div>

    <!-- Executive Summary -->
    <h1>Executive Summary</h1>

    <div class="executive-summary">
        <p><strong>Overview:</strong> {report_data.get('executive_summary', 'This report provides a comprehensive assessment of compliance controls.')}</p>
    </div>

    <div class="chart-container">
        <img src="data:image/png;base64,{score_chart}" alt="Compliance Score" style="width: 400px;">
    </div>

    <div class="metric-grid">
        <div class="metric-card">
            <span class="metric-value">{report_data.get('total_controls', 0)}</span>
            <span class="metric-label">Total Controls</span>
        </div>
        <div class="metric-card">
            <span class="metric-value">{report_data.get('controls_passed', 0)}</span>
            <span class="metric-label">Controls Passed</span>
        </div>
        <div class="metric-card">
            <span class="metric-value">{report_data.get('total_findings', 0)}</span>
            <span class="metric-label">Total Findings</span>
        </div>
    </div>

    <div class="chart-container">
        <img src="data:image/png;base64,{findings_chart}" alt="Findings by Severity">
    </div>

    <!-- AI-Generated Recommendations (if available) -->
    {self._generate_recommendations_section(report_data)}

    <!-- Detailed Sections -->
    {self._generate_detailed_sections(report_data)}

    <div class="footer">
        Generated by CARL (Cloud Automated Risk & Compliance Logic) • Confidential
    </div>
</body>
</html>
"""
        return html

    def _generate_recommendations_section(self, report_data: dict) -> str:
        """Generate AI recommendations section if available."""
        recommendations = report_data.get('ai_recommendations', '')

        if not recommendations or len(recommendations.strip()) < 20:
            return ""

        # Format recommendations with proper HTML
        # Replace line breaks with <br> and wrap in styled div
        formatted_recs = recommendations.replace('\n', '<br>')

        return f"""
    <div class="page-break"></div>
    <h2>Priority Remediation Recommendations</h2>
    <div class="executive-summary">
        <p style="white-space: pre-wrap;">{formatted_recs}</p>
    </div>
"""

    def _generate_detailed_sections(self, report_data: dict) -> str:
        """Generate detailed sections for controls, findings, etc."""
        sections = []
        is_executive = report_data.get('is_executive', False)
        show_controls = report_data.get('show_controls_table', True)
        has_recommendations = report_data.get('ai_recommendations', '') and len(report_data.get('ai_recommendations', '').strip()) >= 20

        # Controls section (only for full audit report)
        if show_controls and 'controls' in report_data and report_data['controls']:
            sections.append('<div class="page-break"></div>')
            sections.append('<h2>Control Assessment</h2>')
            sections.append('<table>')
            sections.append('<thead><tr><th>Control ID</th><th>Control Name</th><th>Status</th><th>Evidence</th><th>Findings</th></tr></thead>')
            sections.append('<tbody>')

            for control in report_data['controls']:
                status_class = 'compliant' if control.get('status') == 'compliant' else 'non-compliant'
                sections.append(f"""
                <tr>
                    <td><strong>{control.get('control_id', 'N/A')}</strong></td>
                    <td>{control.get('control_name', 'N/A')}</td>
                    <td><span class="badge badge-{status_class}">{control.get('status', 'N/A')}</span></td>
                    <td>{control.get('evidence_count', 0)} items</td>
                    <td>{control.get('findings_count', 0)}</td>
                </tr>
                """)

            sections.append('</tbody></table>')

        # Findings section
        if 'findings' in report_data and report_data['findings']:
            # Add page break only if we had controls section before this
            if show_controls and 'controls' in report_data and report_data['controls']:
                sections.append('<div class="page-break"></div>')
            # For executive: only add page break if we DON'T have recommendations (to avoid double page break)
            elif is_executive and not has_recommendations:
                sections.append('<div class="page-break"></div>')

            # Title depends on report type
            if is_executive:
                sections.append('<h2>Priority Findings Requiring Attention</h2>')
                sections.append('<p><em>Showing critical and high severity findings only. Run full audit report for complete details.</em></p>')
            else:
                sections.append('<h2>Findings Detail</h2>')

            for finding in report_data['findings']:
                severity = finding.get('severity', 'medium').lower()
                sections.append(f"""
                <h3><span class="badge badge-{severity}">{finding.get('severity', 'N/A')}</span> {finding.get('title', 'N/A')}</h3>
                <p><strong>Resource:</strong> {finding.get('resource_id', 'N/A')}</p>
                <p><strong>Description:</strong> {finding.get('description', 'N/A')}</p>
                <p><strong>Recommendation:</strong> {finding.get('remediation_steps', 'N/A')}</p>
                """)

        return '\n'.join(sections)

    def generate_pdf(self, report_data: dict) -> bytes:
        """
        Generate PDF from report data.

        Args:
            report_data: Dictionary with report content

        Returns:
            PDF bytes
        """
        try:
            html_content = self.generate_html_template(report_data)

            # Convert HTML to PDF
            pdf_bytes = HTML(string=html_content).write_pdf()

            logger.info(f"Generated PDF report ({len(pdf_bytes)} bytes)")
            return pdf_bytes

        except Exception as e:
            logger.exception("Failed to generate PDF")
            raise

    def upload_to_s3(self, pdf_bytes: bytes, bucket: str, key: str) -> str:
        """
        Upload PDF to S3.

        Args:
            pdf_bytes: PDF content
            bucket: S3 bucket name
            key: S3 object key

        Returns:
            S3 key
        """
        try:
            self.s3_client.put_object(
                Bucket=bucket,
                Key=key,
                Body=pdf_bytes,
                ContentType='application/pdf',
                ContentDisposition=f'attachment; filename="{key.split("/")[-1]}"'
            )

            logger.info(f"Uploaded PDF to s3://{bucket}/{key}")
            return key

        except Exception as e:
            logger.exception("Failed to upload PDF to S3")
            raise

    def generate_presigned_url(self, bucket: str, key: str, expiration: int = 86400) -> str:
        """
        Generate presigned URL for S3 object.

        Args:
            bucket: S3 bucket name
            key: S3 object key
            expiration: URL expiration in seconds (default 24 hours)

        Returns:
            Presigned URL
        """
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket, 'Key': key},
                ExpiresIn=expiration
            )
            return url
        except Exception as e:
            logger.exception("Failed to generate presigned URL")
            raise
