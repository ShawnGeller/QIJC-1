import os
import smtplib
from email.message import EmailMessage

host = os.environ.get('MAIL_SERVER')
port = int(os.environ.get('MAIL_PORT', 587))
user = os.environ.get('MAIL_USERNAME')
pwd = os.environ.get('MAIL_PASSWORD')
sender = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@example.com')
to = [os.environ.get('TEST_RECIPIENT', 'dida3797@colorado.edu')]

missing = [k for k in ('MAIL_SERVER','MAIL_USERNAME','MAIL_PASSWORD') if not os.environ.get(k)]
if missing:
	print('Missing required environment variables:', ', '.join(missing))
	print('Set them and re-run. Example:')
	print("export MAIL_SERVER=smtp.colorado.edu MAIL_PORT=587 MAIL_USERNAME='acct@colorado.edu' MAIL_PASSWORD='pw' MAIL_DEFAULT_SENDER='qijc@colorado.edu' TEST_RECIPIENT='you@colorado.edu'")
	raise SystemExit(2)

msg = EmailMessage()
msg['Subject'] = 'QIJC test'
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
	print('sent')
except Exception as e:
	print('Send failed:', repr(e))
	raise