from app import db
from app.auth import bp
from flask import (Flask, render_template, request, flash,
                   redirect, url_for)
from sqlalchemy import func
from datetime import datetime, timedelta
from werkzeug.urls import url_parse
from app.auth.forms import (LoginForm, RegistrationForm,
                            ManageUserForm, ResetPasswordRequestForm,
                            ResetPasswordForm)
from flask_login import (current_user, login_user, logout_user,
                         login_required)
from app.models import User, Paper
from app.email import send_password_reset_email

@bp.route('/login', methods=['GET', 'POST'])
def login():
    '''
    If the user is already authenticated, route them to the index.
    If the user is not authenticated, send them login.html.
    If the form on login.html is posted and validates,
      check the password. If it's good, log them in
      and redirect them to the index.
    If the password_hash is set to 'waiting', the admin
      has not yet approved their account.
    '''
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user.password_hash == 'waiting':
            flash('Admin has not yet approved account.')
            return redirect(url_for('auth.login'))
        if user is None or not user.check_password(form.password.data):
            flash('Incorrect password.')
            return redirect(url_for('auth.login'))
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get('next')
        if not next_page or url_parse(next_page).netloc != '':
            next_page = url_for('main.index')
        return redirect(next_page)
    return render_template('auth/login.html', title='Sign in', form=form)

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.index'))

@bp.route('/register', methods=['GET', 'POST'])
def register():
    '''
    Send the register.html page with the form.
    If the form posts and validates, create a new 
    user object and add it into the database.
    set_password is called with argument=1
      so that the account will be in limbo
      until the admin approves their account.
    '''
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data,
                    firstname=form.firstname.data,
                    lastname=form.lastname.data)
        user.set_password(form.password.data, 1)
        db.session.add(user)
        db.session.commit()
        flash('Account requested, await admin approval.')
        return redirect(url_for('auth.login'))
    return render_template('auth/register.html', title='Register',
                           form=form)

@bp.route('/reset_password_req', methods=['GET', 'POST'])
def reset_password_req():
    '''
    If the user requests a password reset,
    look up their account by the email they submit.
    If the account is found, send a reset email.
    '''
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = ResetPasswordRequestForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            send_password_reset_email(user)
            flash('Password reset email sent.')
            return redirect(url_for('auth.login'))
        else:
            flash('No user registered with that email address.')
            return redirect(url_for('auth.reset_password_req'))
    return render_template('auth/reset_password_req.html',
                           title='Reset Password', form=form)

@bp.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    '''
    Once the user gets the token in their email
    they can come to this page. if the token validates,
    they can access this page with the password reset form.
    '''
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    user = User.verify_reset_password_token(token)
    if not user:
        return redirect(url_for('main.index'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.new_pass.data)
        db.session.commit()
        flash('Password updated.')
        return redirect(url_for('auth.login'))
    return render_template('auth/reset_password.html', form=form)

@bp.route('/manage', methods=['GET', 'POST'])
@login_required
def manage():
    '''
    Display all users in a table. Populate the table with forms.
    If a form submits, do the appropriate action.
    More detail on these in the form doc strings.
    Refresh the page after any given form is submitted and processed.
    '''
    manageforms = []
    if not current_user.admin:
        flash('Admin privilege required to manage.')
        return redirect(url_for('main.index'))
    users = (User.query.order_by(User.password_hold.desc())
             .order_by(User.retired).order_by(User.admin.desc())
             .order_by(func.lower(User.firstname)).all())
    for user in users:
        user.manage_form = ManageUserForm(user_=user.id)
        manageforms.append(user.manage_form)
    for form in manageforms:
        if form.submit_.data and form.validate_on_submit():
            if (form.action_.data == 'ret') or (
                    form.action2_.data == 'ret'):
                user = User.query.get(form.user_.data)
                user.retired = 1
                from secrets import token_hex
                user.set_password(token_hex())
                db.session.commit()
                flash('Retired {}.'.format(user.username))
            elif form.action_.data == 'adm':
                User.query.get(form.user_.data).admin = True
                db.session.commit()
            elif form.action2_.data == 'rma':
                User.query.get(form.user_.data).admin = False
                db.session.commit()
            elif form.action3_.data == 'unr':
                user = User.query.get(form.user_.data)
                user.retired = False
                db.session.commit()
            elif form.action3_.data == 'del':
                flash(form.user_.data)
                flash(User.query.get(form.user_.data))
                print(form.user_.data)
                print(User.query.get(form.user_.data))
                db.session.delete(User.query.get(form.user_.data))
                db.session.commit()
            elif form.approve.data:
                u = User.query.get(form.user_.data)
                u.password_hash = u.password_hold
                u.password_hold = None
                db.session.commit()
            return redirect(url_for('auth.manage'))
    return render_template('auth/manage.html', title='Manage',
                           manageforms=manageforms, users=users)
