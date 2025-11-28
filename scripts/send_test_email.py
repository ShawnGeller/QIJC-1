import smtplib
msg = "Subject: test\r\n\r\nThis is a test from send_test_email.py"
s = smtplib.SMTP("127.0.0.1", 1025, timeout=10)
s.sendmail("from@example.com", ["to@example.com"], msg)
s.quit()
print("sent")