"""Generate the sample PDF in the knowledge base.

The knowledge base is checked in as text so the repository stays reviewable, but the ingestion
pipeline needs a real PDF to exercise its PDF path. This writes one with no third-party
dependency, so `python scripts/make_sample_pdf.py` regenerates it anywhere.

    python scripts/make_sample_pdf.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402

LINES_PER_PAGE = 46

# ("h", ...) renders bold, ("b", ...) renders body text, ("", "") is a blank line.
DOCUMENT: list[tuple[str, str]] = [
    ("h", "Shipment SLA and Escalation Policy"),
    ("", ""),
    ("b", "Revision 4.2 - Operations Governance Board"),
    ("b", "Applies to all outbound shipping facilities."),
    ("", ""),
    ("h", "1. Dispatch service levels"),
    ("", ""),
    ("b", "A shipment must leave CREATED within a fixed window measured from"),
    ("b", "its created_at timestamp. The window depends on shipment priority:"),
    ("", ""),
    ("b", "  EXPRESS   - 2 hours"),
    ("b", "  STANDARD  - 24 hours"),
    ("b", "  ECONOMY   - 72 hours"),
    ("", ""),
    ("b", "A shipment that exceeds its window is classed as SLA-breaching and"),
    ("b", "must be reported to the duty operations manager on the same shift."),
    ("", ""),
    ("h", "2. Escalation tiers"),
    ("", ""),
    ("b", "Tier 1. Facility coordinator. Owns any shipment blocked for less"),
    ("b", "than one SLA window. Resolves trailer assignment and dock issues"),
    ("b", "directly without further approval."),
    ("", ""),
    ("b", "Tier 2. Regional operations manager. Owns any shipment blocked for"),
    ("b", "one to three SLA windows, and any shipment blocked by a facility"),
    ("b", "configuration problem such as outbound dispatch being disabled."),
    ("", ""),
    ("b", "Tier 3. Platform engineering on-call. Owns any shipment blocked by"),
    ("b", "a workflow service error rather than a data problem, and any"),
    ("b", "incident affecting more than ten shipments at one facility."),
    ("", ""),
    ("h", "3. Approval requirements"),
    ("", ""),
    ("b", "Any corrective action that writes to production shipment state"),
    ("b", "requires a named human approver before it is applied. This covers"),
    ("b", "assigning a trailer, changing a shipment status, clearing a"),
    ("b", "compliance hold and re-enabling outbound dispatch at a facility."),
    ("", ""),
    ("b", "Read-only investigation never requires approval. Automated systems"),
    ("b", "may diagnose and recommend, but may not apply, a state change."),
    ("", ""),
    ("h", "4. Priority handling for blocked shipments"),
    ("", ""),
    ("b", "EXPRESS shipments blocked for any reason are escalated to Tier 2"),
    ("b", "immediately, bypassing the Tier 1 window. A blocked EXPRESS"),
    ("b", "shipment at an inbound-only facility is a Tier 3 incident because"),
    ("b", "it indicates an upstream routing defect."),
    ("", ""),
    ("h", "5. Reporting"),
    ("", ""),
    ("b", "Every SLA breach is recorded with the shipment identifier, the"),
    ("b", "root cause category, the escalation tier reached and the total"),
    ("b", "blocked duration. Root cause categories are: MISSING_TRAILER,"),
    ("b", "TRAILER_UNAVAILABLE, FACILITY_DISABLED, COMPLIANCE_HOLD and"),
    ("b", "SERVICE_ERROR."),
]


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _content_stream(lines: list[tuple[str, str]]) -> str:
    parts = ["BT", "16 TL", "1 0 0 1 56 780 Tm"]
    for style, text in lines:
        parts.append("/F2 13 Tf" if style == "h" else "/F1 11 Tf")
        if text:
            parts.append(f"({_escape(text)}) Tj")
        parts.append("T*")
    parts.append("ET")
    return "\n".join(parts)


def build_pdf(lines: list[tuple[str, str]]) -> bytes:
    pages = [lines[i : i + LINES_PER_PAGE] for i in range(0, len(lines), LINES_PER_PAGE)]
    n = len(pages)

    font_regular = 3 + 2 * n
    font_bold = font_regular + 1
    page_ids = [3 + 2 * i for i in range(n)]

    objects: dict[int, str] = {
        1: "<< /Type /Catalog /Pages 2 0 R >>",
        2: (
            "<< /Type /Pages /Count {count} /Kids [{kids}] >>".format(
                count=n, kids=" ".join(f"{pid} 0 R" for pid in page_ids)
            )
        ),
        font_regular: "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        font_bold: "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>",
    }

    for i, page_lines in enumerate(pages):
        page_id = page_ids[i]
        content_id = page_id + 1
        stream = _content_stream(page_lines)
        objects[page_id] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 {font_regular} 0 R /F2 {font_bold} 0 R >> >> "
            f"/Contents {content_id} 0 R >>"
        )
        objects[content_id] = (
            f"<< /Length {len(stream.encode('latin-1'))} >>\nstream\n{stream}\nendstream"
        )

    out = bytearray(b"%PDF-1.4\n")
    offsets: dict[int, int] = {}
    for num in sorted(objects):
        offsets[num] = len(out)
        out += f"{num} 0 obj\n{objects[num]}\nendobj\n".encode("latin-1")

    xref_at = len(out)
    total = max(objects) + 1
    out += f"xref\n0 {total}\n".encode("latin-1")
    out += b"0000000000 65535 f \n"
    for num in range(1, total):
        out += f"{offsets.get(num, 0):010d} 00000 n \n".encode("latin-1")
    out += (
        f"trailer\n<< /Size {total} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF\n"
    ).encode("latin-1")
    return bytes(out)


def main() -> None:
    target = settings.knowledge_dir / "sla_escalation_policy.pdf"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(build_pdf(DOCUMENT))
    print(f"Wrote {target} ({target.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
