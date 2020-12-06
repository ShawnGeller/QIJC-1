from flask import render_template, current_app, flash
from app import mail, db
from app.models import User
from flask_mail import Message
from threading import Thread

def send_async_email(app, msg):
    with app.app_context():
        mail.send(msg)

def send_email(subject, sender, recipients, text_body, html_body):
    msg = Message(subject, sender=sender, recipients=recipients)
    msg.body = text_body
    msg.html = html_body
    Thread(target=send_async_email,
           args=(current_app._get_current_object(), msg)).start()

def send_password_reset_email(user):
    token = user.get_reset_password_token()
    send_email('[QIJC] Reset your password',
               sender=current_app.config['ADMINS'][0],
               recipients=[user.email],
               text_body=render_template('email/reset_password.txt',
                                         user=user, token=token),
               html_body=render_template('email/reset_password.html',
                                         user=user, token=token))

def send_abstracts(e_from, subject, body, papers):
#    recipients = db.session.query(User.email).filter(User.retired==0).all()
    recipients = list(db.session.query(User.email)
                      .filter(User.username=='austin').first())
    send_email(subject, e_from, recipients,
                   text_body=render_template('email/snd_abstracts.txt',
                                                papers=papers,
                                                 body=body),
                   html_body=render_template('email/snd_abstracts.html',
                                                 papers=papers,
                                                 body=body))
    flash('Message sent.')
