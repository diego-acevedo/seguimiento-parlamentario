from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import (
    JSONResponse,
    PlainTextResponse,
    StreamingResponse,
    HTMLResponse,
)

from seguimiento_parlamentario.core.db import get_db
from seguimiento_parlamentario.core.utils import convert_datetime_in_dict
from seguimiento_parlamentario.processing.qa import QuestionAnswerModel
from seguimiento_parlamentario.reports.formatters import (
    SummaryFormatter,
    MindmapFormatter,
)

from api.types import QueryRequest

# Router configuration
router = APIRouter(prefix="/data", tags=["Data"])

# Initialize database
db = get_db()


@router.post("/ask")
async def ask(data: QueryRequest):
    """
    Answer natural language questions about parliamentary data.

    Args:
        data (QueryResquest): Contains the user `message` and optional `filters`.

    Returns:
        JSONResponse: Answer and citation source.
    """
    qa_model = QuestionAnswerModel()
    message = data.message
    filters = data.filters

    answer, citation = qa_model.ask(message, filters)
    return JSONResponse(content={"response": answer, "citation": citation})


@router.get("/commissions")
async def get_commissions(
    detailed: bool = Query(False, description="Return simplified or extended version."),
):
    """
    Retrieve available commissions.

    Args:
        detailed (bool): Whether to return full details or a simplified version.

    Returns:
        JSONResponse: List of commissions.
    """
    commissions = convert_datetime_in_dict(db.find_commissions(detailed=detailed))
    return JSONResponse(content=commissions)


@router.get("/sessions")
async def get_sessions(
    commission_id: int = Query(..., description="Commission ID"),
    year: int = Query(..., description="Year"),
    month: int = Query(..., ge=1, le=12, description="Month"),
    detailed: bool = Query(False, description="Return extended version."),
):
    """
    Retrieve sessions for a given commission, year, and month.

    Args:
        commission_id (int): ID of the commission.
        year (int): Year of the sessions.
        month (int): Month of the sessions (1–12).
        detailed (bool): Whether to return extended session details.

    Returns:
        dict | HTTPException: List of sessions or error if retrieval fails.
    """
    try:
        sessions = convert_datetime_in_dict(
            db.find_sessions(commission_id, year, month, detailed=detailed)
        )
        return sessions
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/commission/{commission_id}")
async def get_commission(commission_id: int):
    """
    Retrieve details for a specific commission.

    Args:
        commission_id (int): ID of the commission.

    Returns:
        JSONResponse: Commission details.
    """
    commission = convert_datetime_in_dict(db.find_commission(commission_id))
    return JSONResponse(content=commission)


@router.get("/session/{session_id}")
async def get_session(
    session_id: int,
    detailed: bool = Query(False, description="Return extended version."),
):
    """
    Retrieve details for a specific session.

    Args:
        session_id (int): ID of the session.
        detailed (bool): Whether to return extended session details.

    Returns:
        JSONResponse: Session details.
    """
    session = convert_datetime_in_dict(db.find_session(session_id, detailed=detailed))
    return JSONResponse(content=session)


@router.get("/summary/{session_id}")
async def get_summary(
    session_id: int,
    format: str = Query("raw", enum=["raw", "md", "html", "pdf"]),
):
    """
    Retrieve the summary of a session in different formats.

    Args:
        session_id (int): ID of the session.
        format (str): Output format (`raw`, `md`, `html`, `pdf`).

    Returns:
        JSONResponse | PlainTextResponse | HTMLResponse | StreamingResponse:
            Summary in the requested format.
    """
    summary = db.find_summary(session_id)
    formatter = SummaryFormatter()

    if format == "raw":
        return JSONResponse(content=summary, media_type="application/json")

    if format == "md":
        md = formatter.to_markdown(summary)
        return PlainTextResponse(content=md, media_type="text/markdown")

    if format == "html":
        html = formatter.to_html(summary)
        return HTMLResponse(content=html, media_type="text/html")

    if format == "pdf":
        pdf = formatter.to_pdf(summary)
        return StreamingResponse(
            pdf,
            media_type="application/pdf",
            headers={"Content-Disposition": f"inline; filename={session_id}.pdf"},
        )


@router.get("/mindmap/{session_id}")
async def get_mindmap(
    session_id: int,
    format: str = Query("raw", enum=["raw", "json", "html"]),
):
    """
    Retrieve the mindmap of a session in different formats.

    Args:
        session_id (int): ID of the session.
        format (str): Output format (`raw`, `json`, `html`).

    Returns:
        JSONResponse | HTMLResponse:
            Mindmap in the requested format.
    """
    mindmap = db.find_mindmap(session_id)
    formatter = MindmapFormatter()

    if format == "raw":
        return JSONResponse(content=mindmap, media_type="application/json")

    if format == "json":
        json_data = formatter.to_json(mindmap)
        return JSONResponse(content=json_data, media_type="application/json")

    if format == "html":
        html = formatter.to_html(mindmap)
        return HTMLResponse(content=html, media_type="text/html")
