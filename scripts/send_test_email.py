import os
import smtplib
from email.message import EmailMessage
import requests


def send_via_graph():
	tenant = os.environ.get('GRAPH_TENANT_ID')
	client_id = os.environ.get('GRAPH_CLIENT_ID')
	client_secret = os.environ.get('GRAPH_CLIENT_SECRET')
	sender = os.environ.get('GRAPH_SENDER') or os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@example.com')
	recipient = os.environ.get('TEST_RECIPIENT', 'dida3797@colorado.edu')

	missing = [k for k in ('GRAPH_TENANT_ID', 'GRAPH_CLIENT_ID', 'GRAPH_CLIENT_SECRET') if not os.environ.get(k)]
	if missing:
		print('Missing required Graph variables:', ', '.join(missing))
		raise SystemExit(2)

	token_url = f'https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token'
	token_resp = requests.post(
		token_url,
		data={
			'client_id': client_id,
			'client_secret': client_secret,
			'scope': 'https://graph.microsoft.com/.default',
			'grant_type': 'client_credentials',
		},
		timeout=15,
	)
	if not token_resp.ok:
		print('Graph token request failed:', token_resp.status_code, token_resp.text)
		raise SystemExit(1)
	token = token_resp.json().get('access_token')
	if not token:
		print('Graph token response missing access_token')
		raise SystemExit(1)

	send_resp = requests.post(
		f'https://graph.microsoft.com/v1.0/users/{sender}/sendMail',
		headers={
			'Authorization': f'Bearer {token}',
			'Content-Type': 'application/json',
		},
		json={
			'message': {
				'subject': 'QIJC Graph test',
				'body': {
					'contentType': 'Text',
					'content': 'Test body sent through Microsoft Graph',
				},
				'toRecipients': [
					{'emailAddress': {'address': recipient}},
				],
			},
			'saveToSentItems': 'true',
		},
		timeout=20,
	)
	if not send_resp.ok:
		print('Graph send failed:', send_resp.status_code, send_resp.text)
		raise SystemExit(1)
	print('sent via graph')


def send_via_smtp():
	host = os.environ.get('MAIL_SERVER')
	port = int(os.environ.get('MAIL_PORT', 587))
	user = os.environ.get('MAIL_USERNAME')
	pwd = os.environ.get('MAIL_PASSWORD')
	sender = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@example.com')
	to = [os.environ.get('TEST_RECIPIENT', 'dida3797@colorado.edu')]

	missing = [k for k in ('MAIL_SERVER', 'MAIL_USERNAME', 'MAIL_PASSWORD') if not os.environ.get(k)]
	if missing:
		print('Missing required environment variables:', ', '.join(missing))
		print('Set them and re-run. Example:')
		print("export MAIL_SERVER=smtp.colorado.edu MAIL_PORT=587 MAIL_USERNAME='acct@colorado.edu' MAIL_PASSWORD='pw' MAIL_DEFAULT_SENDER='qijc@colorado.edu' TEST_RECIPIENT='you@colorado.edu'")
		raise SystemExit(2)

	msg = EmailMessage()
	msg['Subject'] = 'QIJC SMTP test'
	msg['From'] = sender
	msg['To'] = ','.join(to)
	msg.set_content('Test body')

	try:
		s = smtplib.SMTP(host, port, timeout=10)
		s.set_debuglevel(1)
		s.ehlo()
		s.starttls()
		s.ehlo()
		s.login(user, pwd)
		s.send_message(msg)
		s.quit()
		print('sent via smtp')
	except Exception as e:
		print('Send failed:', repr(e))
		raise

if __name__ == '__main__':
	# Prefer Graph when configured; otherwise use SMTP.
	if os.environ.get('GRAPH_TENANT_ID') and os.environ.get('GRAPH_CLIENT_ID') and os.environ.get('GRAPH_CLIENT_SECRET'):
		send_via_graph()
	else:
		send_via_smtp()