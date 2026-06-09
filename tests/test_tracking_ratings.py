"""Regression: ratings from Model A sends must attribute to the campaign.

A Model A send (POST /api/emails/send and the campaign fan-out) records its
confirmed SES hand-off as ``EmailEvent(event_type="send_to_ses")`` carrying the
per-recipient ``tracking_id`` in ``event_metadata``. The public
``GET /t/r/{tracking_id}/{rating}`` tracker must resolve that id and write an
``EmailCampaignRating`` with the correct campaign / contact / template.

Originally the tracker only matched the legacy ``"send_to_ses"`` event while
Model A wrote ``"send"``, so every rating from the new send path was silently
dropped — HTTP 200, nothing written, ``ratings/summary`` stuck at 0. The send
path now also writes ``"send_to_ses"`` (the unified hand-off type). These tests
lock in attribution and the ``404`` for an unresolvable id (a silent 200 is what
masked the bug).
"""
import uuid

import pytest
from sqlalchemy.orm import Session

from src.db.models import (
    Account,
    Contact,
    EmailCampaign,
    EmailCampaignRating,
    EmailEvent,
    EmailTemplate,
)


@pytest.fixture()
def sent(db: Session, test_account: Account):
    """A campaign/contact/template plus the ``send`` event a Model A dispatch writes."""
    template = EmailTemplate(
        account_id=test_account.id,
        name="Rate template",
        subject_template="{{ SUBJECT }}",
        html_template="<html><body>{{ RATING_BASE_URL }}/5</body></html>",
    )
    contact = Contact(account_id=test_account.id, first_name="Alex", email="alex@example.com")
    campaign = EmailCampaign(account_id=test_account.id, name="Q2")
    db.add_all([template, contact, campaign])
    db.commit()
    db.refresh(template)
    db.refresh(contact)
    db.refresh(campaign)

    tracking_id = str(uuid.uuid4())
    # Mirror dispatch_one's confirmed hand-off ledger row exactly.
    db.add(EmailEvent(
        account_id=test_account.id,
        campaign_id=campaign.id,
        contact_id=contact.id,
        primary_recipient=contact.email,
        event_type="send_to_ses",
        provider="ses",
        message_id="ses-message-id-123",
        event_metadata={"tracking_id": tracking_id, "email_template_id": template.id},
    ))
    db.commit()
    return {"tracking_id": tracking_id, "campaign": campaign,
            "contact": contact, "template": template}


async def test_rating_attributes_to_campaign(authed_client, db, sent):
    tid = sent["tracking_id"]

    resp = await authed_client.get(f"/t/r/{tid}/5")
    assert resp.status_code == 200, resp.text

    row = db.query(EmailCampaignRating).filter_by(tracking_id=tid).one()
    assert row.rating == 5
    assert row.campaign_id == sent["campaign"].id
    assert row.contact_id == sent["contact"].id
    assert row.email_template_id == sent["template"].id

    summary = await authed_client.get(
        f"/api/email-campaigns/{sent['campaign'].id}/ratings/summary")
    assert summary.status_code == 200
    assert summary.json()["total_ratings"] == 1


async def test_unknown_tracking_id_returns_404(authed_client, db):
    bogus = "00000000-0000-0000-0000-000000000000"
    resp = await authed_client.get(f"/t/r/{bogus}/5")
    assert resp.status_code == 404
    assert db.query(EmailCampaignRating).filter_by(tracking_id=bogus).count() == 0


async def test_duplicate_click_counts_once(authed_client, db, sent):
    tid = sent["tracking_id"]
    first = await authed_client.get(f"/t/r/{tid}/4")
    second = await authed_client.get(f"/t/r/{tid}/4")
    # A human re-clicking still lands on the thank-you page, but no double count.
    assert first.status_code == 200
    assert second.status_code == 200
    assert db.query(EmailCampaignRating).filter_by(tracking_id=tid).count() == 1
