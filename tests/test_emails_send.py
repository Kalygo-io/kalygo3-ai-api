"""Contract for the Model A send primitive — POST /api/emails/send.

Covers the redesign's acceptance criteria: an immutable template is rendered
with request variables + contact personalization + system tokens; a duplicate
(campaign, contact) send no-ops; dry_run validates required tokens without
sending; the resume helper returns only unsent contacts; and no send path
mutates the stored template body.

SES and credential decryption are stubbed so the test never leaves the process.
"""
from importlib import import_module

import pytest
from sqlalchemy.orm import Session

# NB: ``import src.routers.emails.router`` would bind the APIRouter, not the
# module — the ``emails`` package re-exports the APIRouter as ``emails.router``
# (see __init__.py), shadowing the submodule under attribute access. Only
# import_module() returns the real module object we need to patch.
emails_router = import_module("src.routers.emails.router")
from src.db.models import (
    Account,
    Contact,
    ContactList,
    ContactListMember,
    EmailCampaign,
    EmailEvent,
    EmailTemplate,
)

SEND_URL = "/api/emails/send"


@pytest.fixture(autouse=True)
def _stub_ses(monkeypatch):
    """Stub credential loading and the SES hand-off."""
    # Patch the module object directly (see import_module note above): a dotted
    # string target would resolve to the shadowing APIRouter, not the module.
    monkeypatch.setattr(
        emails_router,
        "load_ses_credential",
        lambda db, account_id, credential_id: {
            "aws_access_key_id": "AKIA", "aws_secret_access_key": "secret",
            "aws_region": "us-east-1", "from_email": "sender@cmdlabs.io",
        },
    )
    sent = []
    def _fake_send(cfg, to_email, subject, html_body):
        sent.append({"to": to_email, "subject": subject, "html": html_body})
        return "ses-message-id-123"
    monkeypatch.setattr("src.services.email_dispatch.send_ses_html_email", _fake_send)
    return sent


@pytest.fixture()
def template(db: Session, test_account: Account) -> EmailTemplate:
    tmpl = EmailTemplate(
        account_id=test_account.id,
        name="Haiku",
        subject_template="{{ SUBJECT }}",
        html_template="<html><body><h1>{{ TITLE }}</h1><p>Hi {{ first_name }}</p>"
                      "<p>{{ MAIN_CONTENT }}</p></body></html>",
        variables=[
            {"name": "SUBJECT", "label": "Subject", "required": True, "scope": "campaign"},
            {"name": "TITLE", "label": "Title", "required": True, "scope": "campaign"},
            {"name": "MAIN_CONTENT", "label": "Body", "required": True, "scope": "campaign"},
            {"name": "first_name", "label": "First name", "scope": "contact"},
        ],
    )
    db.add(tmpl)
    db.commit()
    db.refresh(tmpl)
    return tmpl


@pytest.fixture()
def contact(db: Session, test_account: Account) -> Contact:
    c = Contact(account_id=test_account.id, first_name="Alex", last_name="Doe",
                email="alex@example.com")
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@pytest.fixture()
def campaign(db: Session, test_account: Account) -> EmailCampaign:
    # A campaign is a pure correlation tag — no template/content needed.
    camp = EmailCampaign(account_id=test_account.id, name="Q2 Haiku")
    db.add(camp)
    db.commit()
    db.refresh(camp)
    return camp


@pytest.fixture()
def credential(db: Session, test_account: Account):
    # A real row so the email_events.credential_id FK is satisfied; the SES
    # loader is stubbed (see _stub_ses), so encrypted_data is never decrypted.
    from src.db.models import Credential, ServiceName
    cred = Credential(
        account_id=test_account.id,
        credential_type=ServiceName.AWS_SES,
        credential_name="SES (test)",
        encrypted_data="stub",
    )
    db.add(cred)
    db.commit()
    db.refresh(cred)
    return cred


def _body(campaign, template, contact, **over):
    payload = {
        "campaign_id": campaign.id,
        "template_id": template.id,
        "variables": {"SUBJECT": "Haiku.", "TITLE": "A Haiku for You",
                      "MAIN_CONTENT": "Three lines arrive late—"},
        "recipient": {"contact_id": contact.id},
        "credential_id": 999,
    }
    payload.update(over)
    return payload


async def test_send_renders_and_logs(authed_client, db, campaign, template, contact, credential, _stub_ses):
    resp = await authed_client.post(
        SEND_URL, json=_body(campaign, template, contact, credential_id=credential.id))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "sent"
    assert data["contact_id"] == contact.id
    assert data["event_id"] is not None

    # personalization + campaign variables landed in the rendered HTML
    assert _stub_ses[0]["subject"] == "Haiku."
    assert "Hi Alex" in _stub_ses[0]["html"]
    assert "A Haiku for You" in _stub_ses[0]["html"]

    # ledger: an attempting marker and a confirmed hand-off (send_to_ses)
    types = [e.event_type for e in db.query(EmailEvent).filter(
        EmailEvent.campaign_id == campaign.id).all()]
    assert "attempting" in types
    assert types.count("send_to_ses") == 1
    # the bare "send" type is reserved for SES SNS notifications — never written here
    assert "send" not in types


async def test_duplicate_send_skips(authed_client, db, campaign, template, contact, credential, _stub_ses):
    body = _body(campaign, template, contact, credential_id=credential.id)
    first = await authed_client.post(SEND_URL, json=body)
    assert first.json()["status"] == "sent"

    second = await authed_client.post(SEND_URL, json=body)
    assert second.status_code == 200
    assert second.json()["status"] == "skipped_duplicate"

    # exactly one confirmed hand-off, and SES was only invoked once
    sends = db.query(EmailEvent).filter(
        EmailEvent.campaign_id == campaign.id,
        EmailEvent.contact_id == contact.id,
        EmailEvent.event_type == "send_to_ses",
    ).count()
    assert sends == 1
    assert len(_stub_ses) == 1


async def test_dry_run_reports_missing_required(authed_client, campaign, template, contact, _stub_ses):
    body = _body(campaign, template, contact, dry_run=True, variables={"SUBJECT": "Hi"})
    resp = await authed_client.post(SEND_URL, json=body)
    assert resp.status_code == 422
    missing = {m["token"] for m in resp.json()["detail"]["missing"]}
    assert {"TITLE", "MAIN_CONTENT"} <= missing
    assert _stub_ses == []  # nothing sent


async def test_dry_run_validates_without_sending(authed_client, db, campaign, template, contact, _stub_ses):
    resp = await authed_client.post(SEND_URL, json=_body(campaign, template, contact, dry_run=True))
    assert resp.status_code == 200
    assert resp.json()["status"] == "validated"
    assert _stub_ses == []
    assert db.query(EmailEvent).filter(EmailEvent.campaign_id == campaign.id).count() == 0


async def test_template_not_mutated(authed_client, db, campaign, template, contact, credential, _stub_ses):
    original_subject = template.subject_template
    original_html = template.html_template
    await authed_client.post(
        SEND_URL, json=_body(campaign, template, contact, credential_id=credential.id))
    db.refresh(template)
    assert template.subject_template == original_subject
    assert template.html_template == original_html


async def test_unsent_resume_helper(authed_client, db, test_account, campaign, template, contact, credential, _stub_ses):
    # second contact, both in a list linked to the campaign
    other = Contact(account_id=test_account.id, first_name="Sam", email="sam@example.com")
    db.add(other)
    db.commit()
    clist = ContactList(account_id=test_account.id, name="Recipients")
    db.add(clist)
    db.commit()
    for c in (contact, other):
        db.add(ContactListMember(contact_list_id=clist.id, contact_id=c.id,
                                 account_id=test_account.id))
    campaign.contact_list_id = clist.id
    db.commit()

    # send to only the first contact
    await authed_client.post(
        SEND_URL, json=_body(campaign, template, contact, credential_id=credential.id))

    resp = await authed_client.get(f"/api/email-campaigns/{campaign.id}/unsent")
    assert resp.status_code == 200
    remaining_ids = {r["contact_id"] for r in resp.json()["remaining"]}
    assert remaining_ids == {other.id}
