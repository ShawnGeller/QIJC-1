import os
import re
import uuid
import io
from datetime import datetime, timedelta
from textwrap import dedent

import operator
import time
import arxiv
import PyPDF2
from PyPDF2 import PdfFileReader
from PIL import Image

from flask import (Flask, render_template, request,
                   flash, redirect, url_for, session, abort,
                   send_from_directory, current_app)
from markupsafe import Markup
from flask_login import (current_user, login_user, logout_user, login_required)
from sqlalchemy import cast, Float, inspect
from werkzeug.utils import secure_filename
from urllib.parse import urlparse, urljoin
from app import db
from app.main import bp
from app.main.forms import (PaperSubmissionForm, ManualSubmissionForm,
                            FullVoteForm, SearchForm,
                            FullEditForm, CommentForm, MessageForm,
                            AnnouncementForm, EditCommentForm, DeleteCommentForm)
from app.auth.forms import ChangePasswordForm, ChangeEmailForm, ChangeNameForm
from app.models import User, Paper, Announcement, Upload, Comment, Nomination
from app.email import send_abstracts, send_nomination_notification, get_configured_sender

last_month = datetime.today() - timedelta(days=30)
one_year_ago = datetime.today() - timedelta(days=365)


def extract_arxiv_id(link_value):
    if not link_value:
        return None
    match = re.search(r"([0-9]{4}\.[0-9]{4,5})(v\d+)?", str(link_value))
    return match.group(1) if match else None


def is_duplicate_active_paper(link_value):
    candidate_link = (link_value or '').strip()
    if not candidate_link:
        return False

    candidate_norm = candidate_link.rstrip('/')
    candidate_arxiv_id = extract_arxiv_id(candidate_link)

    active_papers = (Paper.query.filter(Paper.voted == None)
                     .filter(Paper.timestamp >= one_year_ago)
                     .all())
    for paper in active_papers:
        for existing in (paper.link, paper.pdf_url):
            if not existing:
                continue
            existing_norm = str(existing).strip().rstrip('/')
            if existing_norm == candidate_norm:
                return True
            existing_arxiv_id = extract_arxiv_id(existing)
            if candidate_arxiv_id and existing_arxiv_id and candidate_arxiv_id == existing_arxiv_id:
                return True
    return False


@bp.context_processor
def inject_delete_form():
    # always provide a delete form instance to templates that render comments
    return dict(delete_form=DeleteCommentForm())




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
    # Handle file uploads and deletes submitted from the submit page
    if request.method == 'POST':
        # upload a file
        if "filesubmit" in request.form:
            uploaded_file = request.files.get('file')
            if uploaded_file is None:
                flash("no file")
                return redirect(url_for('main.submit'))

            r = store_upload(uploaded_file)
            if r is None:
                flash("Upload failed.")
            else:
                flash("Upload complete.")
            return redirect(url_for('main.submit'))

        # delete a file
        if "Delete" in request.form:
            cname = clean_pdf_name(request.form.get("Delete"))
            if cname is None:
                flash("Delete: bad file.")
            else:
                updir = get_upload_dir()
                if updir is None:
                    return redirect(url_for('main.submit'))

                fullf = os.path.join(updir, cname)
                if os.path.exists(fullf):
                    os.remove(fullf)
                    flash("File deleted.")
                else:
                    flash("Delete: file not found")

            return redirect(url_for('main.submit'))
    if form.submit.data and form.validate_on_submit():
        # link_str = form.link.data.split('?')[0].split('.pdf')[0]
        link_str = form.link.data
        if is_duplicate_active_paper(link_str):
            flash('That paper is already on the list.')
            return redirect(url_for('main.submit'))
        m = re.match(r".*/([0-9.]+\d).*", link_str)
        # print(m,flush=True)
        if m is not None:
            id = m.groups()[0]
        else:
            flash("Please correct the link and try again.")
            return redirect(url_for('main.submit'))
        try:
            rs = arxiv.Search(id_list=[id])
            q = next(rs.results())
        except:
            flash('Scraping error, check link or submit manually.')
            return redirect(url_for('main.submit_m'))
        authors = q.authors
        title = q.title
        abstract = q.summary
        authors = ", ".join([author.name for author in authors])
        a_url = q.entry_id
        p_url = q.pdf_url
        if is_duplicate_active_paper(a_url) or is_duplicate_active_paper(p_url):
            flash('That paper is already on the list.')
            return redirect(url_for('main.submit'))
        p = Paper(link=a_url, subber=current_user,
                  authors=authors, abstract=abstract,
                  title=title, pdf_url=p_url)
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
                link=a_url).first().volunteer = current_user
            db.session.commit()
        elif form.volunteering.data == 'later':
            Paper.query.filter_by(
                link=a_url).first().vol_later = current_user
            db.session.commit()
        flash('Paper submitted.')
        return redirect(url_for('main.submit'))


    papers = (Paper.query.filter(Paper.voted == None)
              .filter(Paper.timestamp >= one_year_ago)
              .order_by(Paper.timestamp.desc()).all())
    editform = FullEditForm(edits=range(len(papers)))
    editforms = list(zip(papers, editform.edits))
    # Populate nomination choices with active users
    all_users = User.query.order_by(User.firstname.asc()).all()
    nom_choices = [(u.username, f"{u.firstname} {u.lastname[0] if u.lastname else ''}") for u in all_users]
    nom_choices.insert(0, ('', 'Select user'))
    for _, f in editforms:
        try:
            f.nominate_user.choices = nom_choices
        except Exception:
            pass
    for i in range(len(editform.data['edits'])):
        paper = editforms[i][0]
        button = editform.data['edits'][i]
        if button['volunteer']:
            paper.volunteer = current_user
        elif button['vol_later']:
            paper.vol_later = current_user
        elif button.get('nominate_vol'):
            # Nominate another user by username for later volunteering
            nominee_name = editforms[i][1].nominate_user.data if hasattr(editforms[i][1], 'nominate_user') else None
            if nominee_name:
                nominee = User.query.filter_by(username=nominee_name.strip()).first()
                if nominee:
                    if paper.vol_later_id != nominee.id:
                        paper.vol_later = nominee
                        # Record nomination (safely ignore if table doesn't exist)
                        try:
                            if inspect(db.engine).has_table('nomination'):
                                db.session.add(Nomination(paper_id=paper.id, nominee_id=nominee.id, nominator_id=current_user.id))
                        except Exception:
                            pass
                        flash(f"Nominated {nominee.username} as volunteer candidate.")
                        db.session.commit()
                        send_nomination_notification(paper, nominee, current_user)
                else:
                    flash("User not found for nomination.")
        elif button['unvolunteer']:
            if paper.volunteer:
                paper.volunteer = None
            elif paper.vol_later:
                paper.vol_later = None
        elif button['unsubmit']:
            try:
                if inspect(db.engine).has_table('nomination'):
                    Nomination.query.filter(Nomination.paper_id == paper.id).delete(synchronize_session=False)
            except Exception:
                pass
            p_comms = Comment.query.filter(Comment.paper_id == paper.id).all()
            for comment in p_comms:
                uploads = Upload.query.filter(Upload.comment_id == comment.id).all()
                for up in uploads:
                    db.session.delete(up)
                db.session.delete(comment)
            Paper.query.filter(Paper.id == paper.id).delete(synchronize_session=False)
        elif button['comment']:
            return redirect(url_for('main.comment_on', id=paper.id))
        else:
            continue
        db.session.commit()
        return redirect(url_for('main.submit'))
    delete_form = DeleteCommentForm()
    # Also list user's uploaded files (previously on the /uploads page)
    username = get_clean_username()
    ups = []
    updir = get_upload_dir()
    if updir is not None and os.path.exists(updir):
        for item in os.listdir(updir):
            if os.path.isfile(os.path.join(updir, item)):
                cname = clean_pdf_name(item)
                if cname is not None:
                    l = [cname, time.ctime(os.path.getmtime(os.path.join(updir, cname)))]
                    ups.append(l)
    ups.sort(reverse=True, key=lambda x: x[1])

    # Build nominated_by map: only if nominations table exists
    nominated_by = {}
    try:
        inspector = inspect(db.engine)
        if inspector.has_table('nomination'):
            for p in papers:
                if p.vol_later:
                    try:
                        nm = (Nomination.query.filter_by(paper_id=p.id, nominee_id=p.vol_later.id)
                              .order_by(Nomination.timestamp.desc()).first())
                        if nm:
                            nominated_by[p.id] = nm.nominator
                    except Exception:
                        continue
    except Exception:
        pass

    return render_template('main/submit.html', form=form,
                           title='Submit Paper', showsub=True,
                           editform=editform,
                           editforms=editforms, extras=True,
                           delete_form=delete_form, ups=ups, username=username, nominated_by=nominated_by)


@bp.route('/submit_m', methods=['GET', 'POST'])
@login_required
def submit_m():
    form = ManualSubmissionForm()
    if form.validate_on_submit():
        link_value = (form.link.data or '').strip() or None
        if is_duplicate_active_paper(link_value):
            flash('That paper is already on the list.')
            return redirect(url_for('main.submit_m'))
        p = Paper(
            link=link_value,
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
            p.volunteer = current_user
            db.session.commit()
        flash('Paper submitted.')
        return redirect(url_for('main.submit'))
    papers = Paper.query.filter(Paper.timestamp >= one_year_ago).all()
    return render_template('main/submit_m.html', papers=papers,
                           form=form, title='Submit Paper', showsub=True)


@bp.route('/vote', methods=['GET', 'POST'])
@login_required
def vote():
    papers_v = (Paper.query.filter(Paper.voted==None)
              .filter(Paper.volunteer_id != None)
              .filter(Paper.timestamp >= one_year_ago)
              .order_by(Paper.timestamp.asc()).all())
    papers_ = (Paper.query.filter(Paper.voted==None)
               .filter(Paper.volunteer_id == None)
               .filter(Paper.timestamp >= one_year_ago)
               .order_by(Paper.timestamp.asc()).all())
    papers = papers_v + papers_
    voteform = FullVoteForm(votes=range(len(papers)))
    voteforms = list(zip(papers, voteform.votes))
    
    # Handle voting + nominations together on a single submit.
    votes = 0
    nominations = 0
    nomination_events = []
    if request.method == 'POST':
        # Collect nomination selections from each paper row.
        for paper in papers:
            nominee_username = request.form.get(f'nominate_user_{paper.id}', '').strip()
            if not nominee_username:
                continue
            nominee = User.query.filter_by(username=nominee_username).first()
            if not nominee:
                continue
            if paper.vol_later_id != nominee.id:
                paper.vol_later = nominee
                nominations += 1
                nomination_events.append((paper, nominee))
                # Record nomination event when the table exists.
                try:
                    if inspect(db.engine).has_table('nomination'):
                        db.session.add(
                            Nomination(
                                paper_id=paper.id,
                                nominee_id=nominee.id,
                                nominator_id=current_user.id,
                            )
                        )
                except Exception:
                    pass

        current_app.logger.info(f"Vote form submitted. Validating...")
        current_app.logger.info(f"Form data: {voteform.data}")
        current_app.logger.info(f"Form errors: {voteform.errors}")
        if voteform.validate_on_submit():
            current_app.logger.info(f"Form validated successfully")
            votes_data = voteform.data.get('votes', [])
            current_app.logger.info(f"Processing {len(votes_data)} vote entries")
            for i, paper in enumerate(papers):
                if i >= len(votes_data):
                    break
                data = votes_data[i]
                num = data.get('vote_num')
                den = data.get('vote_den')
                if num is None or den is None or num == '' or den == '':
                    continue
                try:
                    paper.score_n = int(num)
                    paper.score_d = int(den)
                    paper.voted = datetime.now().date()
                    votes += 1
                    current_app.logger.info(f"Recorded vote for paper {paper.id}: {num}/{den}")
                except (ValueError, TypeError) as e:
                    current_app.logger.warning(f"Invalid vote data for paper {paper.id}: {e}")
                    continue
            
            if votes:
                db.session.commit()
                if nominations:
                    flash(f'{nominations} nominations saved.')
                flash('{} votes counted.'.format(votes))
                week = datetime.now().date().strftime('%Y-%m-%d')
                current_app.logger.info(f"Redirecting to history for week {week}")
                for paper, nominee in nomination_events:
                    send_nomination_notification(paper, nominee, current_user)
                return redirect(url_for('main.history', week=week))
            else:
                if nominations:
                    db.session.commit()
                    flash(f'{nominations} nominations saved.')
                    for paper, nominee in nomination_events:
                        send_nomination_notification(paper, nominee, current_user)
                flash('No valid votes provided.')
                current_app.logger.info('No valid votes provided.')
        else:
            if nominations:
                db.session.commit()
                flash(f'{nominations} nominations saved.')
                for paper, nominee in nomination_events:
                    send_nomination_notification(paper, nominee, current_user)
            current_app.logger.error(f"Form validation failed: {voteform.errors}")

    summary_vdict = {}
    for p in papers_v:
        v = p.volunteer.firstname
        if v not in summary_vdict:
            summary_vdict[v] = 0
        summary_vdict[v] += 1
    summary_v_sorted = sorted(summary_vdict.items(),key=operator.itemgetter(1),reverse=True)

    summary_nvdict = {}
    summary_vldict = {}
    for p in papers_:
        if p.vol_later is not None:
            v = p.vol_later.firstname
            if v not in summary_vldict:
                summary_vldict[v] = 0
            summary_vldict[v] += 1
        else:
            v = p.subber.firstname
            if v not in summary_nvdict:
                summary_nvdict[v] = 0
            summary_nvdict[v] += 1
    summary_nv_sorted = sorted(summary_nvdict.items(),key=operator.itemgetter(1),reverse=True)
    summary_vl_sorted = sorted(summary_vldict.items(),key=operator.itemgetter(1),reverse=True)

    # Build nominated_by map for display on vote page (only if table exists)
    nominated_by = {}
    try:
        inspector = inspect(db.engine)
        if inspector.has_table('nomination'):
            for p in papers:
                if p.vol_later:
                    try:
                        nm = (Nomination.query.filter_by(paper_id=p.id, nominee_id=p.vol_later.id)
                              .order_by(Nomination.timestamp.desc()).first())
                        if nm:
                            nominated_by[p.id] = nm.nominator
                    except Exception:
                        continue
    except Exception:
        pass

    # Populate nomination choices with active users
    all_users = User.query.order_by(User.firstname.asc()).all()
    nom_choices = [(u.username, f"{u.firstname} {u.lastname[0] if u.lastname else ''}") for u in all_users]
    nom_choices.insert(0, ('', 'Select user'))

    return render_template(
        'main/vote.html', title='Vote', showsub=True, voteform=voteform,
        voteforms=voteforms,
        summary_v=summary_v_sorted,
        summary_vl = summary_vl_sorted,
        summary_nv = summary_nv_sorted,
        nom_choices=nom_choices,
        extras=True
    )


@bp.route('/user/<username>', methods=['GET', 'POST'])
@login_required
def user(username):
    form = ChangePasswordForm()
    # Detect which user form was submitted by checking for its unique fields
    if 'current_pass' in request.form and form.validate_on_submit():
        current_user.set_password(form.new_pass.data)
        db.session.commit()
        flash('Password changed.')
    form2 = ChangeEmailForm()
    if 'new_email' in request.form and form2.validate_on_submit():
        current_user.email = form2.new_email.data
        db.session.commit()
        flash('Email updated.')

    form3 = ChangeNameForm()
    if form3.submit_name.data and form3.validate_on_submit():
        current_user.firstname = form3.new_firstname.data
        current_user.lastname = form3.new_lastname.data
        db.session.commit()
        flash('Name updated.')

    user = User.query.filter_by(username=username).first_or_404()
    subs = (Paper.query.filter_by(subber=user)
            .order_by(Paper.timestamp.desc()))[:10]
    vols = (Paper.query.filter_by(volunteer=user)
            .order_by(Paper.timestamp.desc()))[:10]
    ups = (Upload.query.filter_by(uploader=user)
            .order_by(Upload.timestamp.desc()))[:10]
    return render_template('main/user.html', user=user, form=form,
                           subs=subs, showsub=False, form2=form2, form3=form3,ups=ups,
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
    weeks = sorted(set(weeks), reverse=True)
    # group weeks by year -> month
    from collections import defaultdict
    grouped = defaultdict(lambda: defaultdict(list))
    for w in weeks:
        y = w.year
        m = w.strftime('%B')
        grouped[y][m].append(w)
    # convert to ordered structure
    grouped_weeks = []
    for y in sorted(grouped.keys(), reverse=True):
        months = []
        for m in sorted(grouped[y].keys(), key=lambda x: datetime.strptime(x, '%B').month, reverse=True):
            months.append((m, grouped[y][m]))
        grouped_weeks.append((y, months))
    return render_template('main/history.html', grouped_weeks=grouped_weeks)


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
        uploaded_file = request.files.get("file")
        comment = Comment(
            text=form.comment.data,
            commenter_id=current_user.id,
            paper_id=paper.id,
        )
        db.session.add(comment)
        db.session.flush()  # Get comment.id before commit
        if uploaded_file and uploaded_file.filename:
            # save into per-user folder (store_upload returns "success" or None)
            r = store_upload(uploaded_file)
            if r:
                cleaned = clean_pdf_name(uploaded_file.filename)
                if cleaned:
                    # internal filename must include the user's subdirectory,
                    # because store_upload saves to UPLOAD_PATH/<username>/<cleaned>
                    internal_path = os.path.join(current_user.username, cleaned)
                    up = Upload(
                        internal_filename=internal_path,
                        external_filename=cleaned,
                        user_filename=uploaded_file.filename,
                        uploader_id=current_user.id,
                        comment_id=comment.id
                    )
                    db.session.add(up)
        db.session.commit()
        return redirect(url_for('main.submit'))
    return render_template('main/comment_on.html', form=form, paper=paper,
                           title='Comment')


@bp.route('/edit_comment/<int:comment_id>', methods=['GET', 'POST'])
@login_required
def edit_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    if comment.commenter_id != current_user.id:
        abort(403)
    form = EditCommentForm(comment=comment.text)
    if form.validate_on_submit():
        comment.text = form.comment.data
        db.session.commit()
        flash('Comment updated.')
        return redirect(request.referrer or url_for('main.submit'))
    return render_template('main/edit_comment.html', form=form, comment=comment)


@bp.route('/message', methods=['GET', 'POST'])
@login_required
def message():
    # optional: restrict to admins
    if not getattr(current_user, 'admin', False):
        return redirect(url_for('main.index'))

    users = User.query.filter(~User.retired).order_by(User.firstname, User.lastname).all()
    if request.method == 'POST':
        subject = request.form.get('subject', '').strip()
        body = request.form.get('body', '').strip()
        mode = request.form.get('recipients_mode', 'everyone')
        user_ids = []
        manual_emails = None

        if mode == 'selected':
            raw_ids = request.form.getlist('selected_users')
            try:
                user_ids = [int(x) for x in raw_ids if x]
            except ValueError:
                user_ids = []
        elif mode == 'manual':
            manual_raw = request.form.get('manual_emails', '')
            manual_emails = [e.strip() for e in manual_raw.split(',') if e.strip()]

        # choose papers as needed; here send all papers or supply empty list
        papers = Paper.query.order_by(Paper.timestamp.desc()).all()

        sender = get_configured_sender()

        try:
            send_abstracts(sender, subject, body, papers,
                           mode=mode, user_ids=user_ids, manual_emails=manual_emails)
        except Exception:
            current_app.logger.exception('Failed to send message emails via /message route')
            flash('Email send failed. Check mail configuration and logs.')

        return redirect(url_for('main.message'))

    return render_template('main/message.html', users=users)

def validate_image(stream):
    try:
        # Pillow can open from a BytesIO stream
        image = Image.open(io.BytesIO(stream.read()))
        stream.seek(0)  # reset stream pointer after reading
        format = image.format.lower()  # 'JPEG' → 'jpeg', 'PNG' → 'png'
        return '.' + (format if format != 'jpeg' else 'jpg')
    except (IOError, ValueError):
        # Not a valid image
        stream.seek(0)
        return None

def get_clean_username():
    cur_user_name = current_user.username
    if not cur_user_name.isalnum():
        flash("username is not alnum")
        return None
    else:
        return cur_user_name

def get_upload_dir():
    cur_user_name = get_clean_username()
    if cur_user_name is None:
        return None
    else:
        p = os.path.join(current_app.config['UPLOAD_PATH'], cur_user_name)
        return p


def clean_pdf_name(fname):
    m = re.match(r"(.+)\.pdf", fname)
    if m is not None:
        f = m.groups()[0]
        allowed_chars = "_-"
        for c in f:
            if not c.isalnum() and c not in allowed_chars:
                return None

        return f+".pdf"
    else:
        return None


@bp.route('/uploads')
@login_required
def uploads():
    # uploads route removed; uploads are handled on the submit page now
    return redirect(url_for('main.submit'))

@bp.route('/uploads', methods=['POST'])
@login_required
def upload_files():
    # uploads are now handled on the submit page; redirect there
    return redirect(url_for('main.submit'))




def store_upload(uploaded_file):
    cname = clean_pdf_name(uploaded_file.filename)
    if cname is None:
        flash("bad filename")
        return None
    else:
        updir = get_upload_dir()
        os.makedirs(updir,exist_ok=True)
        cursize = 0
        for e in os.scandir(updir):
            if os.path.isfile(e):
                cursize += os.path.getsize(e)
        if cursize > 50*1024*1024:
            flash("Your uploads folder is too big.")
            return None

        uploaded_file.save(os.path.join(updir,cname))
        return "success"


# def manage_upload(uploaded_file, comment=None):
#     filename = secure_filename(uploaded_file.filename)
#     if filename != '':
#         name, file_ext = os.path.splitext(filename)
#         file_ext = file_ext.lower()
#         if file_ext not in current_app.config['UPLOAD_EXTENSIONS']:
#             print("Invalid File extension, valid extensions are "
#                   ".jpg, .png, .gif, .pdf")
#             abort(400)
#         if (file_ext != ".pdf"):
#             if (file_ext != validate_image(uploaded_file.stream)):
#                 print("Invalid Image")
#                 abort(400)
#         else:
#             try:
#                 doc = PdfFileReader(uploaded_file)
#                 print(doc.getNumPages())
#             except PyPDF2.utils.PdfReadError:
#                 print("Invalid PDF")
#                 abort(400)
#         uploaded_file.seek(0)
#         s = uuid.uuid4().hex
#         s += file_ext
#         full_filename = os.path.join(current_app.config['UPLOAD_PATH'], s)
#         uploaded_file.save(full_filename)
#         if comment:
#             comment_id = comment.id
#         else:
#             comment_id = None
#         up_file = Upload(
#             internal_filename=s,
#             external_filename=(uuid.uuid4().hex + file_ext),
#             user_filename=filename,
#             uploader_id=current_user.get_id(),
#             comment_id=comment_id,
#         )
#         db.session.add(up_file)
#         db.session.commit()
#         return up_file

@bp.route('/files/<path:path>')
@login_required
def files(path):
    return send_from_directory(current_app.config['UPLOAD_PATH'],path)

@bp.route('/download/<filename>')
@login_required
def download(filename):
    file = Upload.query.filter(Upload.external_filename == filename).first()
    if not file:
        abort(404)
    internal_filename = file.internal_filename
    return send_from_directory(current_app.config['UPLOAD_PATH'], internal_filename, as_attachment=True)
