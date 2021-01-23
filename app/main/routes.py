import os
import re
import uuid
from datetime import datetime, timedelta
from textwrap import dedent

import arxiv
import PyPDF2
from PyPDF2 import PdfFileReader
import imghdr

from flask import (Flask, render_template, request,
                   flash, redirect, url_for, session, abort, Markup,
                   send_from_directory, current_app)
from flask_login import (current_user, login_user, logout_user, login_required)
from sqlalchemy import cast, Float
from werkzeug.utils import secure_filename
from werkzeug.urls import url_parse

from app import db
from app.main import bp
from app.main.forms import (PaperSubmissionForm, ManualSubmissionForm,
                            FullVoteForm, SearchForm,
                            FullEditForm, CommentForm, MessageForm,
                            AnnouncementForm)
from app.auth.forms import ChangePasswordForm, ChangeEmailForm
from app.models import User, Paper, Announcement, Upload, Comment
from app.email import send_abstracts

last_month = datetime.today() - timedelta(days=30)




@bp.route('/')
@bp.route('/index')
@login_required
def index():
    for user in User.query.all():
        if user.hp != user.hotpoints():
            user.hp = user.hotpoints()
            db.session.commit()
    users = (User.query.filter(User.retired == 0)
             .order_by(User.hp.desc()).all())
    announcement = Announcement.query.order_by(Announcement.timestamp.desc()).limit(1).first()
    if announcement is None:
        announcement = Announcement(text='')
    return render_template('main/index.html', users=users,
                           announcement=Markup(announcement.text),
                           current_user=current_user)

@bp.route('/announce', methods=['GET', 'POST'])
@login_required
def announce():
    if not current_user.admin:
        abort(403)
    announcement = Announcement.query.order_by(Announcement.timestamp.desc()).limit(1).first()
    form = AnnouncementForm(announcement=(announcement.text if announcement is not None else ''))
    if form.validate_on_submit():
        announcement = Announcement(
            text=form.announcement.data,
            announcer_id=current_user.get_id(),
        )
        db.session.add(announcement)
        db.session.commit()
        return redirect(url_for('main.index'))
    return render_template('main/announce.html', form=form, title='Announcement')



@bp.route('/submit', methods=['GET', 'POST'])
@login_required
def submit():
    form = PaperSubmissionForm()
    if form.submit.data and form.validate_on_submit():
        # link_str = form.link.data.split('?')[0].split('.pdf')[0]
        link_str = form.link.data
        m = re.match(".*/([0-9.]+\d).*", link_str)
        if m is not None:
            id = m.groups()[0]
        else:
            flash("Please correct the link and try again.")
            return redirect(url_for('main.submit'))
        try:
            q = arxiv.query(id_list=[id])[0]
        except:
            flash('Scraping error, check link or submit manually.')
            return redirect(url_for('main.submit_m'))
        authors = q['authors']
        title = q['title']
        abstract = q['summary']
        authors = ", ".join(authors)
        p = Paper(link=q['arxiv_url'], subber=current_user,
                  authors=authors, abstract=abstract,
                  title=title, pdf_url=q['pdf_url'])
        db.session.add(p)
        db.session.commit()
        # uploaded_file = request.files["attachment"]
        # up = manage_upload(uploaded_file)
        if form.comments.data:
            c_text = form.comments.data
        # elif up:
        #     c_text = ""
        else:
            c_text = None
        if c_text is not None:
            comment = Comment(
                text=c_text,
                commenter_id=current_user.id,
                paper_id=p.id,
                # upload=up,
            )
            db.session.add(comment)
            # if up:
            #     up.comment_id = comment.id
        db.session.commit()
        if form.volunteering.data == 'now':
            Paper.query.filter_by(
                link=link_str).first().volunteer = current_user
            db.session.commit()
        elif form.volunteering.data == 'later':
            Paper.query.filter_by(
                link=link_str).first().vol_later = current_user
            db.session.commit()
        flash('Paper submitted.')
        return redirect(url_for('main.submit'))
    papers = (Paper.query.filter(Paper.voted == None)
              .order_by(Paper.timestamp.desc()).all())
    editform = FullEditForm(edits=range(len(papers)))
    editforms = list(zip(papers, editform.edits))
    for i in range(len(editform.data['edits'])):
        paper = editforms[i][0]
        button = editform.data['edits'][i]
        if button['volunteer']:
            paper.volunteer = current_user
        elif button['vol_later']:
            paper.vol_later = current_user
        elif button['unvolunteer']:
            if paper.volunteer:
                paper.volunteer = None
            elif paper.vol_later:
                paper.vol_later = None
        elif button['unsubmit']:
            p_comms = Comment.query.filter(Comment.paper_id == paper.id).all()
            for comment in p_comms:
                db.session.delete(comment)
            db.session.delete(paper)
        elif button['comment']:
            return redirect(url_for('main.comment_on', id=paper.id))
        else:
            continue
        db.session.commit()
        return redirect(url_for('main.submit'))
    return render_template('main/submit.html', form=form,
                           title='Submit Paper', showsub=True,
                           editform=editform,
                           editforms=editforms, extras=True)


@bp.route('/submit_m', methods=['GET', 'POST'])
@login_required
def submit_m():
    form = ManualSubmissionForm()
    if form.validate_on_submit():
        p = Paper(
            link=form.link.data,
            subber=current_user,
            authors=form.authors.data,
            abstract=form.abstract.data,
            title=form.title.data,
        )
        db.session.add(p)
        # uploaded_file = request.files["attachment"]
        # up = manage_upload(uploaded_file)
        if form.comments.data:
            c_text = form.comments.data
        # elif up:
        #     c_text = ""
        else:
            c_text = None
        if c_text is not None:
            comment = Comment(
                text=c_text,
                commenter_id=current_user.id,
                paper_id=p.id,
                # upload=up,
            )
            db.session.add(comment)
            # if up:
            #     up.comment_id = comment.id
        db.session.commit()
        if form.volunteering.data:
            Paper.query.filter_by(
                link=form.link.data).first().volunteer = current_user
            db.session.commit()
        flash('Paper submitted.')
        return redirect(url_for('main.submit'))
    papers = Paper.query.filter(Paper.timestamp >= last_month).all()
    return render_template('main/submit_m.html', papers=papers,
                           form=form, title='Submit Paper', showsub=True)


@bp.route('/vote', methods=['GET', 'POST'])
@login_required
def vote():
    papers_v = (Paper.query.filter(Paper.voted==None)
              .filter(Paper.volunteer_id != None)
              .order_by(Paper.timestamp.asc()).all())
    papers_ = (Paper.query.filter(Paper.voted==None)
               .filter(Paper.volunteer_id == None)
               .order_by(Paper.timestamp.asc()).all())
    papers = papers_v + papers_
    voteform = FullVoteForm(votes=range(len(papers)))
    voteforms = list(zip(papers, voteform.votes))
    votes = 0
    for i in range(len(voteform.data['votes'])):
        paper = voteforms[i][0]
        data = voteform.data['votes'][i]
        if data['vote_num'] and voteform.submit.data:  # val on num
            paper.score_n = data['vote_num']
            paper.score_d = data['vote_den']
            paper.voted = datetime.now().date()
            votes += 1
        db.session.commit()
    if votes and voteform.submit.data:
        flash('{} votes counted.'.format(votes))
        week = datetime.now().date().strftime('%Y-%m-%d')
        return redirect(url_for('main.history', week=week))
    return render_template(
        'main/vote.html', title='Vote', showsub=True, voteform=voteform,
        voteforms=voteforms, extras=True
    )


@bp.route('/user/<username>', methods=['GET', 'POST'])
@login_required
def user(username):
    form = ChangePasswordForm()
    if form.validate_on_submit():
        current_user.set_password(form.new_pass.data)
        db.session.commit()
        flash('Password changed.')
    form2 = ChangeEmailForm()
    if form2.validate_on_submit():
        current_user.email = form2.new_email.data
        db.session.commit()
        flash('Email updated.')
    user = User.query.filter_by(username=username).first_or_404()
    subs = (Paper.query.filter_by(subber=user)
            .order_by(Paper.timestamp.desc()))[:10]
    vols = (Paper.query.filter_by(volunteer=user)
            .order_by(Paper.timestamp.desc()))[:10]
    ups = (Upload.query.filter_by(uploader=user)
            .order_by(Upload.timestamp.desc()))[:10]
    return render_template('main/user.html', user=user, form=form,
                           subs=subs, showsub=False, form2=form2, ups=ups,
                           vols=vols, current_user=current_user)


@bp.route('/history')
@login_required
def history():
    # poppers = ['latest', 'scroll']
    poppers = ['latest']
    poppers.extend([i for i in range(99)])
    for i in poppers:
        if i in session:
            session.pop(i, None)
    week = request.args.get('week', None)
    if week:
        papers = (Paper.query.filter_by(voted=week)
                  .order_by(cast(Paper.score_n, Float)
                            / cast(Paper.score_d, Float)).all())
        papers.reverse()
        return render_template('main/history.html', papers=papers,
                               showvote=True, showsub=True)
    weeks = [paper.voted for paper
             in Paper.query.group_by(Paper.voted).all()
             if paper.voted != None]
    weeks.reverse()
    return render_template('main/history.html', weeks=weeks)


@bp.route('/search', methods=['GET', 'POST'])
@login_required
def search():
    form = SearchForm()
    form.subber.choices = form.presenter.choices = ([(None, 'None')]
                                                    + [(u.id,
                                                        u.firstname + ' ' +
                                                        u.lastname[0])
                                                       for u in
                                                       User.query.order_by(
                                                           'firstname')])
    if form.validate_on_submit():
        query = Paper.query
        needles = []
        u_queries = []
        d_queries = []
        if form.title.data:
            needles.append((Paper.title, form.title.data))
        if form.authors.data:
            needles.append((Paper.authors, form.authors.data))
        if form.abstract.data:
            needles.append((Paper.abstract, form.abstract.data))
        if form.sub_date.data and (form.sub_date.data != ''):
            dates = [datetime.strptime(i, '%d/%M/%Y') for i in
                     form.sub_date.data.split('-')]
            d_queries.append((Paper.timestamp, dates[0], dates[1]))
        if form.vote_date.data and (form.vote_date.data != ''):
            dates = [datetime.strptime(i, '%d/%M/%Y') for i in
                     form.vote_date.data.split('-')]
            d_queries.append((Paper.voted, dates[0], dates[1]))
        if form.subber.data and (form.subber.data != 'None'):
            u_queries.append((Paper.subber_id, form.subber.data))
        if form.presenter.data and (form.presenter.data != 'None'):
            u_queries.append((Paper.volunteer_id, form.presenter.data))
        for needle in needles:
            query = query.filter(needle[0].ilike(f'%{needle[1]}%'))
        for d_query in d_queries:
            query = query.filter(d_query[0] >= d_query[1],
                                 d_query[0] <= d_query[2])
        for u_query in u_queries:
            query = query.filter(u_query[0] == u_query[1])
        papers = query.order_by(Paper.timestamp.desc()).all()
        return render_template('main/search.html', papers=papers,
                               form=form, showsub=True)
    return render_template('main/search.html', form=form)


@bp.route('/comment_on', methods=['GET', 'POST'])
@login_required
def comment_on():
    paper = Paper.query.get(request.args.get('id'))
    form = CommentForm()
    if form.validate_on_submit():
        # uploaded_file = request.files["file"]
        # up = manage_upload(uploaded_file)
        comment = Comment(
            text=form.comment.data,
            commenter_id=current_user.id,
            paper_id=paper.id,
            # upload=up,
        )
        db.session.add(comment)
        db.session.commit()
        return redirect(url_for('main.submit'))
    return render_template('main/comment_on.html', form=form, paper=paper,
                           title='Comment')


@bp.route('/message', methods=['GET', 'POST'])
@login_required
def message():
    form = MessageForm()
    if form.validate_on_submit():
        subject = form.subject.data
        e_from = '[' + form.e_from.data + ']'
        body = form.body.data
        attach = form.abstracts.data
        papers_v = (Paper.query.filter(Paper.voted == None)
                    .filter(Paper.volunteer_id != None)
                    .order_by(Paper.timestamp.desc()).all())
        papers_ = (Paper.query.filter(Paper.voted == None)
                   .order_by(Paper.timestamp.desc()).all())
        papers = papers_v + papers_
        send_abstracts(e_from, subject, body, papers)
    bodydefault = dedent('''    The abstracts for this week are attached.
    
    Please log in if you want to claim a paper to discuss.
    
    Best, {}.
    '''.format(current_user.firstname))
    form.body.data = bodydefault
    return render_template('main/message.html', form=form,
                           bodydefault=bodydefault)


def validate_image(stream):
    header = stream.read(512)  # 512 bytes should be enough for a header check
    stream.seek(0)  # reset stream pointer
    format = imghdr.what(None, header)
    if not format:
        return None
    return '.' + (format if format != 'jpeg' else 'jpg')


@bp.route('/uploads')
@login_required
def uploads():
    ups = Upload.query.order_by(Upload.timestamp.desc()).all()
    return render_template('main/uploads.html', ups=ups)


@bp.route('/uploads', methods=['POST'])
@login_required
def upload_files():
    uploaded_file = request.files['file']
    manage_upload(uploaded_file)
    return redirect(url_for('main.uploads'))


def manage_upload(uploaded_file, comment=None):
    filename = secure_filename(uploaded_file.filename)
    if filename != '':
        name, file_ext = os.path.splitext(filename)
        file_ext = file_ext.lower()
        if file_ext not in current_app.config['UPLOAD_EXTENSIONS']:
            print("Invalid File extension, valid extensions are "
                  ".jpg, .png, .gif, .pdf")
            abort(400)
        if (file_ext != ".pdf"):
            if (file_ext != validate_image(uploaded_file.stream)):
                print("Invalid Image")
                abort(400)
        else:
            try:
                doc = PdfFileReader(uploaded_file)
                print(doc.getNumPages())
            except PyPDF2.utils.PdfReadError:
                print("Invalid PDF")
                abort(400)
        uploaded_file.seek(0)
        s = uuid.uuid4().hex
        s += file_ext
        full_filename = os.path.join(current_app.config['UPLOAD_PATH'], s)
        uploaded_file.save(full_filename)
        if comment:
            comment_id = comment.id
        else:
            comment_id = None
        up_file = Upload(
            internal_filename=s,
            external_filename=(uuid.uuid4().hex + file_ext),
            user_filename=filename,
            uploader_id=current_user.get_id(),
            comment_id=comment_id,
        )
        db.session.add(up_file)
        db.session.commit()
        return up_file


@bp.route('/download/<filename>')
@login_required
def download(filename):
    print(Upload.query.filter(Upload.external_filename == filename).first().internal_filename)
    file = Upload.query.filter(Upload.external_filename == filename).first()
    filename = file.internal_filename
    return send_from_directory(current_app.config['UPLOAD_PATH'], filename, as_attachment=True)
