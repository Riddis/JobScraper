from __future__ import annotations

import base64
from pathlib import Path
from typing import Iterable

import requests


GRAPH_SCOPE = "https://graph.microsoft.com/.default"
GRAPH_TOKEN_URL_TEMPLATE = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
GRAPH_SENDMAIL_URL_TEMPLATE = "https://graph.microsoft.com/v1.0/users/{sender}/sendMail"


def _get_access_token(
    tenant_id: str,
    client_id: str,
    client_secret: str,
) -> str:
    token_url = GRAPH_TOKEN_URL_TEMPLATE.format(tenant_id=tenant_id)

    response = requests.post(
        token_url,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": GRAPH_SCOPE,
            "grant_type": "client_credentials",
        },
        timeout=30,
    )
    response.raise_for_status()

    payload = response.json()
    access_token = payload.get("access_token")
    if not access_token:
        raise RuntimeError("No access_token returned by Microsoft identity platform.")

    return access_token


def _build_file_attachments(attachments: Iterable[Path]) -> list[dict]:
    graph_attachments: list[dict] = []

    for file_path in attachments:
        if not file_path.exists():
            continue

        content_bytes = file_path.read_bytes()
        content_base64 = base64.b64encode(content_bytes).decode("utf-8")

        graph_attachments.append(
            {
                "@odata.type": "#microsoft.graph.fileAttachment",
                "name": file_path.name,
                "contentBytes": content_base64,
            }
        )

    return graph_attachments


def send_report_email_graph(
    *,
    tenant_id: str,
    client_id: str,
    client_secret: str,
    sender: str,
    recipients: list[str],
    subject: str,
    body_html: str,
    attachments: list[Path],
) -> None:
    if not recipients:
        raise ValueError("No recipients provided.")

    access_token = _get_access_token(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret,
    )

    sendmail_url = GRAPH_SENDMAIL_URL_TEMPLATE.format(sender=sender)

    payload = {
        "message": {
            "subject": subject,
            "body": {
                "contentType": "HTML",
                "content": body_html,
            },
            "toRecipients": [
                {"emailAddress": {"address": recipient}}
                for recipient in recipients
            ],
            "attachments": _build_file_attachments(attachments),
        },
        "saveToSentItems": True,
    }

    response = requests.post(
        sendmail_url,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=60,
    )

    if response.status_code != 202:
        raise RuntimeError(
            f"Graph sendMail failed: {response.status_code} {response.text}"
        )