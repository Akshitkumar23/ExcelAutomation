"""
docgen_agent.py — BuildFlow AI
FastAPI router: /api/docgen

Generates professional PDF documents (Contract, Invoice, Work Order, Site Report)
using ReportLab. Each document is saved to ./generated_docs/<doc_id>.pdf and
served via the /download/{doc_id} endpoint.

All generated-doc metadata is stored in an in-memory list (no database).
"""

from __future__ import annotations

import logging
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

# ReportLab
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from config import settings

    DOCS_DIR = Path(settings.DOCS_PATH)
except Exception:
    DOCS_DIR = Path("./generated_docs")

DOCS_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/docgen", tags=["DocGen"])

# ---------------------------------------------------------------------------
# SQLite database helpers for generated docs
# ---------------------------------------------------------------------------
def _save_document(record: dict[str, Any], data: Any, session_id: str | None = None) -> None:
    from database import save_generated_document_db
    from data_loader import data_loader
    
    project_id = ""
    project_name = ""
    
    # Try to extract project_id
    if data:
        if hasattr(data, "project_id"):
            project_id = getattr(data, "project_id", "")
        elif isinstance(data, dict):
            project_id = data.get("project_id", "")
            
    if project_id and data_loader:
        try:
            proj = data_loader.get_project_by_id(project_id, session_id=session_id)
            if proj:
                project_name = proj.get("project_name", "")
        except Exception:
            pass
            
    metadata = {
        "preview_text": record.get("preview_text", ""),
        "download_url": record.get("download_url", "")
    }
    
    save_generated_document_db(
        doc_id=record["doc_id"],
        doc_type=record["doc_type"],
        project_id=project_id,
        project_name=project_name,
        generated_at=record["generated_at"],
        file_path=record["file_path"],
        metadata=metadata
    )


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class ContractRequest(BaseModel):
    project_name: str
    client_name: str
    budget: float
    start_date: str
    end_date: str
    scope_of_work: str


class InvoiceRequest(BaseModel):
    invoice_number: str
    client_name: str
    project_id: str
    amount: float
    services: list[str] = Field(default_factory=list)
    due_date: str


class WorkOrderRequest(BaseModel):
    project_id: str
    task_description: str
    assigned_to: str
    deadline: str
    materials_required: list[str] = Field(default_factory=list)


class SiteReportRequest(BaseModel):
    project_id: str
    date: str
    progress_percent: float
    issues: list[str] = Field(default_factory=list)
    completed_tasks: list[str] = Field(default_factory=list)


class GenerateRequest(BaseModel):
    doc_type: str  # CONTRACT | INVOICE | WORK_ORDER | SITE_REPORT
    data: dict[str, Any]
    session_id: str | None = None


# ---------------------------------------------------------------------------
# Brand colours / styles
# ---------------------------------------------------------------------------

BRAND_DARK = colors.HexColor("#1a2e44")       # Deep navy
BRAND_ACCENT = colors.HexColor("#f97316")     # BuildFlow orange
BRAND_LIGHT = colors.HexColor("#e8f4f8")      # Light blue-grey
BRAND_GRAY = colors.HexColor("#64748b")       # Muted text
WHITE = colors.white
BLACK = colors.black


def _get_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "doc_title": ParagraphStyle(
            "doc_title",
            parent=base["Title"],
            fontSize=22,
            textColor=WHITE,
            alignment=TA_CENTER,
            spaceAfter=4,
            fontName="Helvetica-Bold",
        ),
        "doc_subtitle": ParagraphStyle(
            "doc_subtitle",
            parent=base["Normal"],
            fontSize=11,
            textColor=colors.HexColor("#cbd5e1"),
            alignment=TA_CENTER,
            spaceAfter=2,
            fontName="Helvetica",
        ),
        "section_heading": ParagraphStyle(
            "section_heading",
            parent=base["Heading2"],
            fontSize=12,
            textColor=BRAND_DARK,
            spaceBefore=14,
            spaceAfter=4,
            fontName="Helvetica-Bold",
            borderPad=2,
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["Normal"],
            fontSize=10,
            textColor=colors.HexColor("#334155"),
            spaceAfter=4,
            leading=14,
            fontName="Helvetica",
        ),
        "label": ParagraphStyle(
            "label",
            parent=base["Normal"],
            fontSize=9,
            textColor=BRAND_GRAY,
            fontName="Helvetica-Bold",
        ),
        "footer": ParagraphStyle(
            "footer",
            parent=base["Normal"],
            fontSize=8,
            textColor=BRAND_GRAY,
            alignment=TA_CENTER,
            fontName="Helvetica",
        ),
        "table_header": ParagraphStyle(
            "table_header",
            parent=base["Normal"],
            fontSize=9,
            textColor=WHITE,
            fontName="Helvetica-Bold",
            alignment=TA_CENTER,
        ),
        "table_cell": ParagraphStyle(
            "table_cell",
            parent=base["Normal"],
            fontSize=9,
            textColor=colors.HexColor("#1e293b"),
            fontName="Helvetica",
        ),
        "progress_label": ParagraphStyle(
            "progress_label",
            parent=base["Normal"],
            fontSize=10,
            textColor=BRAND_DARK,
            fontName="Helvetica-Bold",
        ),
        "amount": ParagraphStyle(
            "amount",
            parent=base["Normal"],
            fontSize=13,
            textColor=BRAND_ACCENT,
            fontName="Helvetica-Bold",
            alignment=TA_RIGHT,
        ),
    }


# ---------------------------------------------------------------------------
# Shared header / footer builders
# ---------------------------------------------------------------------------


def _build_header(styles: dict, doc_type: str, ref_number: str = "") -> list:
    """Return a list of Flowables that form the branded header."""
    elements: list = []

    # Header banner table (dark background)
    header_data = [
        [
            Paragraph("🏗 BuildFlow AI", styles["doc_title"]),
            Paragraph(
                f"{doc_type.replace('_', ' ')}<br/>"
                f'<font size="9" color="#94a3b8">{ref_number}</font>',
                styles["doc_subtitle"],
            ),
        ]
    ]
    header_table = Table(header_data, colWidths=["55%", "45%"])
    header_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), BRAND_DARK),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 14),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
                ("LEFTPADDING", (0, 0), (0, 0), 16),
                ("RIGHTPADDING", (-1, -1), (-1, -1), 16),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
            ]
        )
    )
    elements.append(header_table)

    # Accent bar
    elements.append(
        Table(
            [[""]],
            colWidths=["100%"],
            rowHeights=[4],
            style=TableStyle([("BACKGROUND", (0, 0), (-1, -1), BRAND_ACCENT)]),
        )
    )
    elements.append(Spacer(1, 10))
    return elements


def _build_footer(styles: dict, doc_id: str) -> list:
    generated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    elements: list = [
        Spacer(1, 18),
        HRFlowable(width="100%", thickness=0.5, color=BRAND_GRAY),
        Spacer(1, 6),
        Paragraph(
            f"Generated by BuildFlow AI • Document ID: {doc_id} • {generated_at}",
            styles["footer"],
        ),
        Paragraph(
            "This document is system-generated. Contact support@buildflow.ai for queries.",
            styles["footer"],
        ),
    ]
    return elements


def _kv_table(pairs: list[tuple[str, str]], col_widths: list = None) -> Table:
    """Two-column key-value info table with alternating row shading."""
    col_widths = col_widths or ["35%", "65%"]
    data = [[Paragraph(f"<b>{k}</b>", _get_styles()["label"]),
             Paragraph(str(v), _get_styles()["body"])]
            for k, v in pairs]
    tbl = Table(data, colWidths=col_widths)
    style_cmds = [
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]
    for i in range(0, len(data), 2):
        style_cmds.append(("BACKGROUND", (0, i), (-1, i), BRAND_LIGHT))
    tbl.setStyle(TableStyle(style_cmds))
    return tbl


# ---------------------------------------------------------------------------
# Document generators
# ---------------------------------------------------------------------------


def _generate_contract_pdf(data: dict, doc_id: str, pdf_path: Path) -> str:
    """Build a CONTRACT PDF and return preview text."""
    req = ContractRequest(**data)
    styles = _get_styles()

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=1.5 * cm,
        bottomMargin=2 * cm,
    )

    elements = _build_header(styles, "CONTRACT AGREEMENT", f"Ref: {doc_id[:8].upper()}")

    elements.append(Paragraph("CONSTRUCTION CONTRACT AGREEMENT", styles["section_heading"]))
    elements.append(
        Paragraph(
            "This agreement is entered into between BuildFlow AI (hereinafter 'Contractor') "
            "and the Client named below, subject to the terms and conditions set forth herein.",
            styles["body"],
        )
    )
    elements.append(Spacer(1, 8))

    elements.append(Paragraph("PARTIES", styles["section_heading"]))
    elements.append(
        _kv_table(
            [
                ("Client Name", req.client_name),
                ("Project Name", req.project_name),
                ("Contract Start", req.start_date),
                ("Contract End", req.end_date),
            ]
        )
    )

    elements.append(Paragraph("SCOPE OF WORK", styles["section_heading"]))
    elements.append(Paragraph(req.scope_of_work, styles["body"]))

    elements.append(Paragraph("PAYMENT TERMS", styles["section_heading"]))
    elements.append(
        _kv_table(
            [
                ("Total Contract Value", f"₹ {req.budget:,.2f} Lac"),
                ("Payment Schedule", "30% on signing | 40% at mid-point | 30% on completion"),
                ("Payment Method", "Bank Transfer / NEFT / RTGS"),
                ("Late Payment Penalty", "1.5% per month on overdue amount"),
            ]
        )
    )

    elements.append(Paragraph("AI-DRAFTED CONTRACT CLAUSES", styles["section_heading"]))
    
    terms = []
    
    from config import settings
    if settings.GEMINI_API_KEY:
        try:
            import google.generativeai as genai
            genai.configure(api_key=settings.GEMINI_API_KEY)
            
            prompt = (
                f"You are an expert construction attorney. Draft 4 concise, legally binding clauses for a contract "
                f"between Contractor 'BuildFlow AI' and Client '{req.client_name}' for the project '{req.project_name}'.\n"
                f"Project Details:\n"
                f"- Scope: {req.scope_of_work}\n"
                f"- Budget: ₹{req.budget} Lac\n"
                f"- Timeline: {req.start_date} to {req.end_date}\n\n"
                f"Draft exactly 4 numbered clauses: 1. Scope & Execution, 2. Payment Terms, 3. Safety & Liability, 4. Disputes & Jurisdiction.\n"
                f"Keep each clause under 3 sentences. Do not use markdown code block formatting."
            )
            
            # Use gemini-1.5-flash for fast completion
            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content(prompt)
            raw_text = response.text.strip()
            
            # Split by line
            lines = [line.strip() for line in raw_text.split('\n') if line.strip()]
            for line in lines:
                if line[0].isdigit() or line.startswith('-') or len(line) > 10:
                    terms.append(line)
        except Exception as e:
            logger.warning("Gemini contract drafting failed, falling back: %s", e)
            
    if not terms:
        # Fallback terms
        terms = [
            f"1. Scope & Execution: The Contractor shall complete the works for '{req.project_name}' between {req.start_date} and {req.end_date} in accordance with the specified scope of work.",
            f"2. Payment Terms: The total contract value is ₹{req.budget:,.2f} Lac. Client shall disburse payments in milestones (30% signing, 40% midpoint, 30% hand-off).",
            f"3. Safety & Compliance: Contractor shall enforce standard labor safety regulations and maintain workers compensation insurance throughout the project lifecycle.",
            f"4. Dispute Resolution: Any legal disputes arising out of this agreement shall be settled through binding arbitration under the Arbitration and Conciliation Act.",
        ]
        
    for term in terms:
        elements.append(Paragraph(term, styles["body"]))

    elements.append(Paragraph("SIGNATURES", styles["section_heading"]))
    sig_data = [
        [
            Paragraph("<b>Client Signature</b>", styles["label"]),
            Paragraph("<b>Contractor Signature</b>", styles["label"]),
        ],
        ["", ""],
        [
            Paragraph(f"Name: {req.client_name}", styles["body"]),
            Paragraph("Name: BuildFlow AI Representative", styles["body"]),
        ],
        [
            Paragraph("Date: ____________________", styles["body"]),
            Paragraph("Date: ____________________", styles["body"]),
        ],
    ]
    sig_table = Table(sig_data, colWidths=["50%", "50%"])
    sig_table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (0, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("BOX", (1, 0), (1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("ROWBACKGROUND", (0, 1), (-1, 1), colors.HexColor("#f8fafc")),
                ("MINROWHEIGHT", (0, 1), (-1, 1), 40),
            ]
        )
    )
    elements.append(sig_table)

    elements += _build_footer(styles, doc_id)
    doc.build(elements)

    preview = (
        f"CONTRACT | Project: {req.project_name} | Client: {req.client_name} | "
        f"Budget: ₹{req.budget:,.2f} Lac | {req.start_date} → {req.end_date}"
    )
    return preview


def _generate_invoice_pdf(data: dict, doc_id: str, pdf_path: Path) -> str:
    """Build an INVOICE PDF and return preview text."""
    req = InvoiceRequest(**data)
    styles = _get_styles()

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=1.5 * cm,
        bottomMargin=2 * cm,
    )

    elements = _build_header(styles, "TAX INVOICE", f"Invoice #: {req.invoice_number}")

    elements.append(Paragraph("BILL TO", styles["section_heading"]))
    elements.append(
        _kv_table(
            [
                ("Client Name", req.client_name),
                ("Project ID", req.project_id),
                ("Invoice Number", req.invoice_number),
                ("Due Date", req.due_date),
                ("Invoice Date", datetime.utcnow().strftime("%Y-%m-%d")),
            ]
        )
    )

    elements.append(Paragraph("SERVICES", styles["section_heading"]))
    services = req.services if req.services else ["General Construction Services"]
    per_service_amt = round(req.amount / len(services), 2)

    svc_header = [
        Paragraph("#", styles["table_header"]),
        Paragraph("Service Description", styles["table_header"]),
        Paragraph("Amount (₹ Lac)", styles["table_header"]),
    ]
    svc_rows = [svc_header]
    for idx, svc in enumerate(services, 1):
        svc_rows.append(
            [
                Paragraph(str(idx), styles["table_cell"]),
                Paragraph(svc, styles["table_cell"]),
                Paragraph(f"{per_service_amt:,.2f}", styles["table_cell"]),
            ]
        )

    subtotal = req.amount
    gst = round(subtotal * 0.18, 2)
    total = round(subtotal + gst, 2)

    svc_rows.append(["", Paragraph("<b>Subtotal</b>", styles["label"]),
                      Paragraph(f"{subtotal:,.2f}", styles["table_cell"])])
    svc_rows.append(["", Paragraph("<b>GST @ 18%</b>", styles["label"]),
                      Paragraph(f"{gst:,.2f}", styles["table_cell"])])
    svc_rows.append(["", Paragraph("<b>TOTAL DUE</b>", styles["label"]),
                      Paragraph(f"<b>{total:,.2f}</b>", styles["table_cell"])])

    svc_table = Table(svc_rows, colWidths=["8%", "67%", "25%"])
    svc_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), BRAND_DARK),
                ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
                ("ROWBACKGROUND", (0, 1), (-1, -2), [BRAND_LIGHT, WHITE]),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#fff7ed")),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("ALIGN", (2, 0), (2, -1), "RIGHT"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    elements.append(svc_table)
    elements.append(Spacer(1, 8))
    elements.append(Paragraph(f"<b>Total Amount Due: ₹ {total:,.2f} Lac</b>", styles["amount"]))

    elements.append(Paragraph("PAYMENT INFORMATION", styles["section_heading"]))
    elements.append(
        _kv_table(
            [
                ("Bank Name", "BuildFlow Central Bank"),
                ("Account Number", "XXXX-XXXX-4281"),
                ("IFSC Code", "BFAI0001234"),
                ("Payment Mode", "NEFT / RTGS / UPI"),
                ("UPI ID", "buildflow@upi"),
            ]
        )
    )

    elements += _build_footer(styles, doc_id)
    doc.build(elements)

    preview = (
        f"INVOICE #{req.invoice_number} | Client: {req.client_name} | "
        f"Project: {req.project_id} | Total: ₹{total:,.2f} Lac | Due: {req.due_date}"
    )
    return preview


def _generate_work_order_pdf(data: dict, doc_id: str, pdf_path: Path) -> str:
    """Build a WORK ORDER PDF and return preview text."""
    req = WorkOrderRequest(**data)
    styles = _get_styles()

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=1.5 * cm,
        bottomMargin=2 * cm,
    )

    wo_ref = f"WO-{doc_id[:8].upper()}"
    elements = _build_header(styles, "WORK ORDER", wo_ref)

    elements.append(Paragraph("ASSIGNMENT DETAILS", styles["section_heading"]))
    elements.append(
        _kv_table(
            [
                ("Work Order Ref", wo_ref),
                ("Project ID", req.project_id),
                ("Assigned To", req.assigned_to),
                ("Deadline", req.deadline),
                ("Issued Date", datetime.utcnow().strftime("%Y-%m-%d")),
                ("Issued By", "BuildFlow AI Orchestrator"),
            ]
        )
    )

    elements.append(Paragraph("TASK DESCRIPTION", styles["section_heading"]))
    elements.append(Paragraph(req.task_description, styles["body"]))

    elements.append(Paragraph("MATERIALS REQUIRED", styles["section_heading"]))
    materials = req.materials_required if req.materials_required else ["As per site requirement"]

    mat_header = [
        Paragraph("#", styles["table_header"]),
        Paragraph("Material", styles["table_header"]),
        Paragraph("Status", styles["table_header"]),
    ]
    mat_rows = [mat_header]
    for idx, mat in enumerate(materials, 1):
        mat_rows.append(
            [
                Paragraph(str(idx), styles["table_cell"]),
                Paragraph(mat, styles["table_cell"]),
                Paragraph("To Be Arranged", styles["table_cell"]),
            ]
        )

    mat_table = Table(mat_rows, colWidths=["8%", "67%", "25%"])
    mat_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), BRAND_DARK),
                ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
                ("ROWBACKGROUND", (0, 1), (-1, -1), [BRAND_LIGHT, WHITE]),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    elements.append(mat_table)

    elements.append(Paragraph("APPROVAL SECTION", styles["section_heading"]))
    approval_data = [
        [
            Paragraph("<b>Site Supervisor</b>", styles["label"]),
            Paragraph("<b>Project Manager</b>", styles["label"]),
            Paragraph("<b>Client Rep.</b>", styles["label"]),
        ],
        ["", "", ""],
        [
            Paragraph("Signature: __________", styles["body"]),
            Paragraph("Signature: __________", styles["body"]),
            Paragraph("Signature: __________", styles["body"]),
        ],
        [
            Paragraph("Date: __________", styles["body"]),
            Paragraph("Date: __________", styles["body"]),
            Paragraph("Date: __________", styles["body"]),
        ],
    ]
    approval_table = Table(approval_data, colWidths=["33%", "33%", "34%"])
    approval_table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (0, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("BOX", (1, 0), (1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("BOX", (2, 0), (2, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("BACKGROUND", (0, 0), (-1, 0), BRAND_LIGHT),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("MINROWHEIGHT", (0, 1), (-1, 1), 36),
            ]
        )
    )
    elements.append(approval_table)

    elements += _build_footer(styles, doc_id)
    doc.build(elements)

    preview = (
        f"WORK ORDER {wo_ref} | Project: {req.project_id} | "
        f"Assigned To: {req.assigned_to} | Deadline: {req.deadline}"
    )
    return preview


def _generate_site_report_pdf(data: dict, doc_id: str, pdf_path: Path) -> str:
    """Build a SITE REPORT PDF and return preview text."""
    req = SiteReportRequest(**data)
    styles = _get_styles()

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=1.5 * cm,
        bottomMargin=2 * cm,
    )

    rpt_ref = f"SR-{doc_id[:8].upper()}"
    elements = _build_header(styles, "DAILY SITE REPORT", rpt_ref)

    elements.append(Paragraph("REPORT SUMMARY", styles["section_heading"]))
    elements.append(
        _kv_table(
            [
                ("Report Ref", rpt_ref),
                ("Project ID", req.project_id),
                ("Report Date", req.date),
                ("Overall Progress", f"{req.progress_percent:.1f}%"),
                ("Prepared By", "BuildFlow AI Analytics Agent"),
            ]
        )
    )

    # Progress bar (visual representation using a table)
    elements.append(Paragraph("PROGRESS OVERVIEW", styles["section_heading"]))
    progress_pct = max(0.0, min(100.0, req.progress_percent))
    filled = int(progress_pct)
    empty = 100 - filled

    # Use a two-cell table row as a visual progress bar
    bar_color = (
        colors.HexColor("#22c55e")  # green
        if progress_pct >= 75
        else (
            colors.HexColor("#f97316")  # orange
            if progress_pct >= 40
            else colors.HexColor("#ef4444")  # red
        )
    )
    progress_bar_data = [["", ""]]
    bar_table = Table(
        progress_bar_data,
        colWidths=[f"{filled}%", f"{empty}%"],
        rowHeights=[18],
    )
    bar_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, 0), bar_color),
                ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#e2e8f0")),
                ("ROUNDEDCORNERS", [4, 4, 4, 4]),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    elements.append(bar_table)
    elements.append(Spacer(1, 4))
    elements.append(
        Paragraph(
            f"<b>{progress_pct:.1f}% Complete</b>",
            styles["progress_label"],
        )
    )

    # Completed tasks
    elements.append(Paragraph("COMPLETED TASKS", styles["section_heading"]))
    if req.completed_tasks:
        for task in req.completed_tasks:
            elements.append(Paragraph(f"✔  {task}", styles["body"]))
    else:
        elements.append(Paragraph("No completed tasks recorded for this period.", styles["body"]))

    # Issues
    elements.append(Paragraph("ISSUES & OBSERVATIONS", styles["section_heading"]))
    if req.issues:
        issue_data = [
            [
                Paragraph("#", styles["table_header"]),
                Paragraph("Issue Description", styles["table_header"]),
                Paragraph("Priority", styles["table_header"]),
            ]
        ]
        for idx, issue in enumerate(req.issues, 1):
            priority = "High" if idx == 1 else "Medium"
            issue_data.append(
                [
                    Paragraph(str(idx), styles["table_cell"]),
                    Paragraph(issue, styles["table_cell"]),
                    Paragraph(priority, styles["table_cell"]),
                ]
            )
        issue_table = Table(issue_data, colWidths=["8%", "72%", "20%"])
        issue_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), BRAND_DARK),
                    ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
                    ("ROWBACKGROUND", (0, 1), (-1, -1), [colors.HexColor("#fff1f0"), WHITE]),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        elements.append(issue_table)
    else:
        elements.append(Paragraph("No issues reported.", styles["body"]))

    # Sign-off
    elements.append(Paragraph("SIGN-OFF", styles["section_heading"]))
    signoff_data = [
        [
            Paragraph("<b>Site Engineer</b>", styles["label"]),
            Paragraph("<b>Project Manager</b>", styles["label"]),
        ],
        ["", ""],
        [
            Paragraph("Signature: __________", styles["body"]),
            Paragraph("Signature: __________", styles["body"]),
        ],
        [
            Paragraph("Date: __________", styles["body"]),
            Paragraph("Date: __________", styles["body"]),
        ],
    ]
    signoff_table = Table(signoff_data, colWidths=["50%", "50%"])
    signoff_table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (0, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("BOX", (1, 0), (1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("BACKGROUND", (0, 0), (-1, 0), BRAND_LIGHT),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("MINROWHEIGHT", (0, 1), (-1, 1), 36),
            ]
        )
    )
    elements.append(signoff_table)

    elements += _build_footer(styles, doc_id)
    doc.build(elements)

    preview = (
        f"SITE REPORT {rpt_ref} | Project: {req.project_id} | "
        f"Date: {req.date} | Progress: {req.progress_percent:.1f}% | "
        f"Issues: {len(req.issues)}"
    )
    return preview


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

_GENERATORS: dict[str, Any] = {
    "CONTRACT": _generate_contract_pdf,
    "INVOICE": _generate_invoice_pdf,
    "WORK_ORDER": _generate_work_order_pdf,
    "SITE_REPORT": _generate_site_report_pdf,
}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/generate")
async def generate_document(request: GenerateRequest) -> dict[str, Any]:
    """
    Accept a GenerateRequest, produce a PDF, persist metadata, and return
    {doc_id, doc_type, preview_text, download_url, generated_at}.
    """
    doc_type = request.doc_type.strip().upper()
    if doc_type not in _GENERATORS:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown doc_type '{doc_type}'. Valid: {list(_GENERATORS.keys())}",
        )

    doc_id = str(uuid.uuid4())
    pdf_path = DOCS_DIR / f"{doc_id}.pdf"

    try:
        generator = _GENERATORS[doc_type]
        preview_text = generator(request.data, doc_id, pdf_path)
    except Exception as exc:
        logger.exception("PDF generation failed for doc_type=%s", doc_type)
        raise HTTPException(status_code=500, detail=f"PDF generation error: {exc}") from exc

    generated_at = datetime.utcnow().isoformat() + "Z"
    record = {
        "doc_id": doc_id,
        "doc_type": doc_type,
        "preview_text": preview_text,
        "download_url": f"/api/docgen/download/{doc_id}",
        "generated_at": generated_at,
        "file_path": str(pdf_path),
    }
    _save_document(record, request.data, session_id=request.session_id)

    logger.info("Generated %s doc %s at %s", doc_type, doc_id, pdf_path)
    return record


@router.get("/download/{doc_id}")
async def download_document(doc_id: str) -> FileResponse:
    """Serve the generated PDF for the given doc_id."""
    pdf_path = DOCS_DIR / f"{doc_id}.pdf"
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found")

    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=f"buildflow_{doc_id[:8]}.pdf",
    )


@router.get("/recent")
async def get_recent_docs() -> list[dict[str, Any]]:
    """Return metadata for the last 10 generated documents."""
    from database import get_recent_generated_documents_db
    return get_recent_generated_documents_db(limit=10)


# ---------------------------------------------------------------------------
# Internal helper — callable by orchestrator without HTTP round-trip
# ---------------------------------------------------------------------------


def generate_site_report_internal(
    project_id: str,
    date: str,
    progress_percent: float,
    issues: list[str] | None = None,
    completed_tasks: list[str] | None = None,
) -> dict[str, Any]:
    """
    Generate a site report PDF directly (no HTTP) and return the record dict.
    Used by the orchestrator agent to avoid circular HTTP calls.
    """
    data = {
        "project_id": project_id,
        "date": date,
        "progress_percent": progress_percent,
        "issues": issues or [],
        "completed_tasks": completed_tasks or [],
    }
    doc_id = str(uuid.uuid4())
    pdf_path = DOCS_DIR / f"{doc_id}.pdf"

    try:
        preview_text = _generate_site_report_pdf(data, doc_id, pdf_path)
    except Exception as exc:
        logger.exception("Internal site report generation failed")
        return {"error": str(exc), "doc_id": doc_id}

    generated_at = datetime.utcnow().isoformat() + "Z"
    record = {
        "doc_id": doc_id,
        "doc_type": "SITE_REPORT",
        "preview_text": preview_text,
        "download_url": f"/api/docgen/download/{doc_id}",
        "generated_at": generated_at,
        "file_path": str(pdf_path),
    }
    _save_document(record, data)
    logger.info("Internal site report generated: %s", doc_id)
    return record
