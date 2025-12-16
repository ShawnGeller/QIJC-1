import smtplib
from email.message import EmailMessage

msg = EmailMessage()
msg['Subject'] = 'SMTP debug test'
msg['From'] = 'noreply@example.com'
msg['To'] = 'you@example.com'
msg.set_content('short body')

s = smtplib.SMTP('127.0.0.1', 1025, timeout=10)
s.set_debuglevel(1)   # prints protocol conversation to stdout
try:
    s.send_message(msg)
    print('sent OK')
except Exception as e:
    print('send failed:', e)
finally:
    s.quit()
