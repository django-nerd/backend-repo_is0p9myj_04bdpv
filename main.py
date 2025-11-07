import os
import smtplib
from email.message import EmailMessage
from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from schemas import Contactmessage
from database import create_document

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI Backend!"}


@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}


@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response: Dict[str, Any] = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": [],
    }

    try:
        from database import db

        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, "name") else "✅ Connected"
            response["connection_status"] = "Connected"

            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:  # pragma: no cover - diagnostic only
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"

    except ImportError:
        response["database"] = "❌ Database module not found (run enable-database first)"
    except Exception as e:  # pragma: no cover - diagnostic only
        response["database"] = f"❌ Error: {str(e)[:50]}"

    import os as _os

    response["database_url"] = "✅ Set" if _os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if _os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


def try_send_email(payload: Contactmessage) -> Dict[str, Any]:
    """Attempt to send an email via SMTP. Returns a status dict and never raises.

    Configure via env:
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM, SMTP_TO
    If not provided, will skip with a graceful message.
    """
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    smtp_from = os.getenv("SMTP_FROM", payload.email)
    smtp_to = os.getenv("SMTP_TO", "studynotion.dev@gmail.com")

    if not smtp_host:
        return {
            "sent": False,
            "reason": "SMTP not configured; skipped sending",
        }

    try:
        msg = EmailMessage()
        msg["Subject"] = f"New portfolio contact: {payload.subject or 'No subject'}"
        msg["From"] = smtp_from
        msg["To"] = smtp_to
        msg.set_content(
            f"Name: {payload.name}\n"
            f"Email: {payload.email}\n\n"
            f"Message:\n{payload.message}\n"
        )

        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            server.starttls()
            if smtp_user and smtp_pass:
                server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        return {"sent": True}
    except Exception as e:  # pragma: no cover - depends on env
        return {"sent": False, "reason": str(e)}


class ContactResponse(BaseModel):
    id: str
    emailed: bool
    email_info: Dict[str, Any]


@app.post("/api/contact", response_model=ContactResponse)
def submit_contact(payload: Contactmessage):
    # Persist to database
    try:
        doc_id = create_document("contactmessage", payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

    # Try to send email (graceful if not configured)
    email_status = try_send_email(payload)

    return ContactResponse(id=doc_id, emailed=email_status.get("sent", False), email_info=email_status)


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
