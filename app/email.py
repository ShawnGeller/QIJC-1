from flask import render_template, current_app, flash, url_for
from app import mail, db
from app.models import User
from flask_mail import Message
from threading import Thread
import requests

def _chunks(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i:i+size]

# --- new helper: wrap long lines to avoid RFC5321 line-length errors ---
def _wrap_text_lines(s, maxlen=750, is_html=False):
    """
    Break lines so no SMTP DATA line exceeds maxlen bytes (use CRLF).
    For HTML we also inject <wbr> where helpful for display, but we always
    insert CRLF in the raw payload so SMTP sees short lines.
    """
    if not s:
        return s
    # normalize newlines
    s = s.replace('\r\n', '\n').replace('\r', '\n')
    out_lines = []
    for line in s.split('\n'):
        if len(line) <= maxlen:
            out_lines.append(line)
            continue
        # break long line into pieces
        while len(line) > maxlen:
            # prefer to break at these separators within the window
            candidates = []
            for sep in (',', ' ', ';', '/', '-', '>', '<'):
                pos = line.rfind(sep, 0, maxlen + 1)
                if pos and pos > 0:
                    candidates.append(pos)
            if candidates:
                idx = max(candidates)
            else:
                idx = maxlen
            part = line[:idx]
            # if HTML try to avoid breaking inside a tag name badly:
            if is_html:
                # if breaking at a tag, prefer to break before the '<' if possible
                if idx > 3 and line[idx-3:idx] == '...':
                    idx -= 3
                elif idx > 4 and line[idx-4:idx] == '...':
                    idx -= 4
            out_lines.append(part)
            line = line[idx:].lstrip()
        if line:
            out_lines.append(line)
    # use CRLF which is standard for SMTP data lines
    return '\r\n'.join(out_lines)
# --- end new helper ---

def send_via_sendgrid(app, subject, sender, recipients, text_body, html_body):
    """Send via SendGrid HTTP API."""
    api_key = app.config.get("SENDGRID_API_KEY")
    if not api_key:
        raise RuntimeError("SENDGRID_API_KEY not configured")
    payload = {
        "personalizations": [{"to": [{"email": r} for r in recipients]}],
        "from": {"email": sender},
        "subject": subject,
        "content": []
    }
    if text_body:
        payload["content"].append({"type": "text/plain", "value": text_body})
    if html_body:
        payload["content"].append({"type": "text/html", "value": html_body})
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    resp = requests.post("https://api.sendgrid.com/v3/mail/send", json=payload, headers=headers, timeout=10)
    if not (200 <= resp.status_code < 300):
        app.logger.error("SendGrid send failed: %s %s", resp.status_code, resp.text)
        resp.raise_for_status()
    app.logger.info("SendGrid message queued subject=%s recipients=%s", subject, recipients)


def _graph_is_configured(app):
    return all([
        app.config.get("GRAPH_TENANT_ID"),
        app.config.get("GRAPH_CLIENT_ID"),
        app.config.get("GRAPH_CLIENT_SECRET"),
    ])


def _graph_access_token(app):
    token_url = (
        f"https://login.microsoftonline.com/{app.config.get('GRAPH_TENANT_ID')}"
        "/oauth2/v2.0/token"
    )
    payload = {
        "client_id": app.config.get("GRAPH_CLIENT_ID"),
        "client_secret": app.config.get("GRAPH_CLIENT_SECRET"),
        "scope": "https://graph.microsoft.com/.default",
        "grant_type": "client_credentials",
    }
    resp = requests.post(token_url, data=payload, timeout=15)
    if not (200 <= resp.status_code < 300):
        raise RuntimeError(f"Graph token request failed: {resp.status_code} {resp.text}")
    token = resp.json().get("access_token")
    if not token:
        raise RuntimeError("Graph token response missing access_token")
    return token


def send_via_graph(app, subject, sender, recipients, text_body, html_body, batch_size=50):
    """Send via Microsoft Graph Mail API using client credentials."""
    if not _graph_is_configured(app):
        raise RuntimeError("Microsoft Graph mail configuration missing")
    if not recipients:
        return

    graph_sender = app.config.get("GRAPH_SENDER") or sender
    token = _graph_access_token(app)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    endpoint = f"https://graph.microsoft.com/v1.0/users/{graph_sender}/sendMail"
    body_content = html_body if html_body else (text_body or "")
    body_type = "HTML" if html_body else "Text"

    for batch in _chunks(recipients, max(1, int(batch_size or 50))):
        payload = {
            "message": {
                "subject": subject,
                "body": {
                    "contentType": body_type,
                    "content": body_content,
                },
                "toRecipients": [
                    {"emailAddress": {"address": r}} for r in batch
                ],
            },
            "saveToSentItems": "true",
        }
        resp = requests.post(endpoint, json=payload, headers=headers, timeout=20)
        if not (200 <= resp.status_code < 300):
            raise RuntimeError(f"Graph send failed: {resp.status_code} {resp.text}")

    app.logger.info("Graph message queued subject=%s recipients=%s", subject, recipients)

def send_async_email(app, subject, sender, recipients, text_body, html_body, batch_size=50):
    """Attempt Graph, then SendGrid, then fall back to Flask-Mail SMTP."""
    with app.app_context():
        # small wrapping to avoid extremely long lines (unchanged)
        safe_text = _wrap_text_lines(text_body or "", maxlen=750, is_html=False)
        safe_html = _wrap_text_lines(html_body or "", maxlen=750, is_html=True)

        if _graph_is_configured(app):
            try:
                send_via_graph(app, subject, sender, recipients, safe_text, safe_html, batch_size=batch_size)
                return
            except Exception as e:
                app.logger.error("Graph send failed: %s", e, exc_info=True)
                # fall through to SendGrid/SMTP fallback

        if app.config.get("SENDGRID_API_KEY"):
            try:
                send_via_sendgrid(app, subject, sender, recipients, safe_text, safe_html)
                return
            except Exception as e:
                app.logger.error("SendGrid send failed: %s", e, exc_info=True)
                # fall through to SMTP fallback

        # Fallback to existing Flask-Mail path (keeps previous behavior)
        try:
            msg = Message(subject, sender=sender, recipients=recipients)
            msg.body = safe_text
            msg.html = safe_html
            mail.send(msg)
            app.logger.info("SMTP message sent subject=%s recipients=%s", subject, recipients)
        except Exception as e:
            app.logger.error("SMTP send failed: %s", e, exc_info=True)

def send_email(subject, sender, recipients, text_body, html_body, batch_size=50):
    # start a background thread that will send in batches
    current_app.logger.info("Queueing email to %d recipients subject=%s", len(recipients) if recipients else 0, subject)
    Thread(target=send_async_email,
           args=(current_app._get_current_object(), subject, sender, recipients or [], text_body, html_body, batch_size)
           ).start()

def send_password_reset_email(user):
    token = user.get_reset_password_token()
    reset_url = url_for('auth.reset_password', token=token, _external=True)
    sender = current_app.config.get('ADMINS', [current_app.config.get('MAIL_DEFAULT_SENDER','noreply@example.com')])[0]
    text = render_template('email/reset_password.txt', user=user, token=token, reset_url=reset_url)
    html = render_template('email/reset_password.html', user=user, token=token, reset_url=reset_url)

    current_app.logger.info("Preparing reset email for user=%s email=%s", user.username, user.email)

    if (not current_app.config.get('MAIL_SERVER')) or current_app.config.get('MAIL_SUPPRESS_SEND', False):
        current_app.logger.info("Mail not configured/suppressed — printed reset URL for dev: %s", reset_url)
        print("Password reset URL (dev):", reset_url)
        flash('Password reset link printed to console (development mode).')
        return

    send_email('[QIJC] Reset Your Password', sender, [user.email], text, html)

# --- New/updated helpers for selectable recipients ---
def resolve_recipients(mode='everyone', user_ids=None, manual_emails=None):
    """
    mode: 'everyone' | 'selected' | 'manual'
    - 'everyone' -> all non-retired users' emails
    - 'selected' -> user_ids must be list of integer user IDs
    - 'manual' -> manual_emails must be list of email strings
    """
    if mode == 'everyone':
        rows = db.session.query(User.email).filter(~User.retired).all()
        return [r[0] for r in rows]
    if mode == 'selected' and user_ids:
        users = User.query.filter(User.id.in_(user_ids)).all()
        return [u.email for u in users]
    if mode == 'manual' and manual_emails:
        return manual_emails
    return []

def send_abstracts(e_from, subject, body, papers, mode='everyone', user_ids=None, manual_emails=None):
    recipients = resolve_recipients(mode=mode, user_ids=user_ids, manual_emails=manual_emails)
    if not recipients:
        flash('No recipients selected.')
        return

    text = render_template('email/snd_abstracts.txt', papers=papers, body=body)
    html = render_template('email/snd_abstracts.html', papers=papers, body=body)

    # If mail not configured or suppressed, avoid SMTP attempt — print + flash for dev
    if (not current_app.config.get('MAIL_SERVER')) or current_app.config.get('MAIL_SUPPRESS_SEND', False):
        print("Abstract email recipients (dev):", recipients)
        print("Subject:", subject)
        print("Body:", body)
        flash('Emails printed to console (development mode).')
        return

    send_email(subject, e_from, recipients, text, html)
    flash('Message sent.')


def send_new_paper_notification(paper, submitter):
    recipients = resolve_recipients(mode='everyone')
    if not recipients:
        return

    sender = current_app.config.get('MAIL_DEFAULT_SENDER', 'noreply@example.com')
    subject = f"[QIJC] New paper submitted: {paper.title}"
    text = render_template('email/new_paper.txt', paper=paper, submitter=submitter)
    html = render_template('email/new_paper.html', paper=paper, submitter=submitter)

    if current_app.config.get('MAIL_SUPPRESS_SEND', False):
        current_app.logger.info("Mail suppressed: skipped new paper notification for paper_id=%s", paper.id)
        return

    send_email(subject, sender, recipients, text, html)


def send_vote_notification(week, vote_count, nomination_count, voter):
    recipients = resolve_recipients(mode='everyone')
    if not recipients:
        return

    sender = current_app.config.get('MAIL_DEFAULT_SENDER', 'noreply@example.com')
    subject = f"[QIJC] Vote results submitted ({week})"
    text = render_template(
        'email/vote_submitted.txt',
        week=week,
        vote_count=vote_count,
        nomination_count=nomination_count,
        voter=voter,
    )
    html = render_template(
        'email/vote_submitted.html',
        week=week,
        vote_count=vote_count,
        nomination_count=nomination_count,
        voter=voter,
    )

    if current_app.config.get('MAIL_SUPPRESS_SEND', False):
        current_app.logger.info("Mail suppressed: skipped vote notification for week=%s", week)
        return

    send_email(subject, sender, recipients, text, html)


def send_nomination_notification(paper, nominee, nominator):
    if not nominee or not nominee.email:
        return

    sender = current_app.config.get('MAIL_DEFAULT_SENDER', 'noreply@example.com')
    subject = f"[QIJC] You were nominated to discuss: {paper.title}"
    text = render_template(
        'email/nomination.txt',
        paper=paper,
        nominee=nominee,
        nominator=nominator,
    )
    html = render_template(
        'email/nomination.html',
        paper=paper,
        nominee=nominee,
        nominator=nominator,
    )

    if current_app.config.get('MAIL_SUPPRESS_SEND', False):
        current_app.logger.info(
            "Mail suppressed: skipped nomination notification for paper_id=%s nominee=%s",
            paper.id,
            nominee.username,
        )
        return

    send_email(subject, sender, [nominee.email], text, html)
