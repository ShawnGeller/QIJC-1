from flask import flash
from flask_wtf import FlaskForm
from wtforms import (StringField, PasswordField, BooleanField,
                     SubmitField, SelectField, HiddenField)
from wtforms.validators import (DataRequired, ValidationError, Email,
                                EqualTo)
from flask_login import current_user
from app.models import User

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user is None:
            raise ValidationError('User not found.')

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    firstname = StringField('First Name', validators=[DataRequired()])
    lastname = StringField('Last Name', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    password2 = PasswordField('Repeat Password', validators=[
        DataRequired(), EqualTo('password')])
    submit = SubmitField('Request account.')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user is not None:
            raise ValidationError('Please use a different username.')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user is not None:
            raise ValidationError('Please use a different email address.')

class ResetPasswordRequestForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Reset password.')

class ResetPasswordForm(FlaskForm):
    new_pass = PasswordField('New password',
                           validators=[DataRequired()])
    new_pass2 = PasswordField('Confirm new password',
                              validators=[DataRequired(),
                              EqualTo('new_pass',
                                      message='Entries do not match.')])
    submit = SubmitField('Submit.')

class ChangePasswordForm(FlaskForm):
    current_pass = PasswordField('Current Password',
                               validators=[DataRequired()])
    new_pass = PasswordField('New password',
                           validators=[DataRequired()])
    new_pass2 = PasswordField('Confirm new password',
                              validators=[DataRequired(),
                              EqualTo('new_pass',
                                      message='Entries do not match.')])
    submit = SubmitField('Submit.')

    def validate_current_pass(self, current_pass):
        if not current_user.check_password(current_pass.data):
            raise ValidationError('Password incorrect.')

class ChangeEmailForm(FlaskForm):
    new_email = StringField('New Email',
                            validators=[DataRequired(), Email()])
    new_email2 = StringField('Confirm Email',
                             validators=[EqualTo(
                                 'new_email',
                                 message='Entries do not match.')])
    submit = SubmitField('Submit.')

class ManageUserForm(FlaskForm):
    action_ = SelectField('Action', 
                          choices=[('ret', 'Retire'),
                                   ('adm', 'Make admin')],
                          validate_choice=False)
    action2_ = SelectField('Action',
                           choices=[('ret', 'Retire'),
                                    ('rma', 'Remove admin')],
                           validate_choice=False)
    action3_ = SelectField('Action',
                           choices=[('unr', 'unRetire'),
                                     ('del', 'Delete user')],
                           validate_choice=False)
    approve = BooleanField('Approve')
    user_ = HiddenField('user_')
    submit_ = SubmitField('>')
