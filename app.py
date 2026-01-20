from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import requests
from flask import Flask, redirect, render_template, request, url_for

app = Flask(__name__, static_folder="img", static_url_path="/img")

DATA_DIR = Path("data")
SUBMISSIONS_PATH = DATA_DIR / "requests.jsonl"
SHEETS_WEBHOOK_URL = (
    os.environ.get("SHEETS_WEBHOOK_URL", "").strip()
    or "https://script.google.com/macros/s/AKfycby9MsXmNsOPj-XyoJyTmfXX-umLHBCCZBZ-V4N-Ky02PbkigINMEVWu_c2f4kr3M9tEQQ/exec"
)


def _clean_text(value: str, max_len: int) -> str:
    value = value.strip()
    if len(value) > max_len:
        return value[:max_len]
    return value


def _is_valid_phone(value: str) -> bool:
    # Accepts +998 90 123 45 67, 901234567, or similar international formats.
    pattern = re.compile(r"^\+?\d[\d\s()\-]{7,}$")
    return bool(pattern.match(value))


def _send_to_sheets(payload: dict[str, str]) -> None:
    if not SHEETS_WEBHOOK_URL:
        return
    try:
        requests.post(SHEETS_WEBHOOK_URL, json=payload, timeout=10)
    except requests.RequestException:
        # Silent fallback to local storage if webhook fails.
        pass


@app.get("/")
def index() -> str:
    submitted = request.args.get("submitted") == "1"
    return render_template(
        "index.html",
        submitted=submitted,
        errors=[],
        form_data={},
    )


@app.post("/contact")
def contact() -> str:
    form_data = {
        "name": _clean_text(request.form.get("name", ""), 120),
        "phone": _clean_text(request.form.get("phone", ""), 40),
        "service": _clean_text(request.form.get("service", ""), 80),
        "message": _clean_text(request.form.get("message", ""), 1000),
    }

    errors: list[str] = []
    if len(form_data["name"]) < 2:
        errors.append("Ism yoki tashkilot nomi kamida 2 ta belgidan iborat bo'lishi kerak.")
    if not _is_valid_phone(form_data["phone"]):
        errors.append("Telefon raqami noto'g'ri. Namuna: +998 90 123 45 67.")

    if errors:
        return render_template(
            "index.html",
            submitted=False,
            errors=errors,
            form_data=form_data,
        )

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "name": form_data["name"],
        "phone": form_data["phone"],
        "service": form_data["service"],
        "message": form_data["message"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _send_to_sheets(payload)
    with SUBMISSIONS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    return redirect(url_for("index", submitted="1"))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port, debug=True)
