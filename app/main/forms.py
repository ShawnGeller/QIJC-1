from flask import flash
from flask_wtf import FlaskForm
from flask_login import current_user
from wtforms import (StringField, PasswordField, BooleanField,
                     SubmitField, IntegerField, FieldList, FormField,
                     SelectField, TextAreaField)
from wtforms.validators import (DataRequired, ValidationError, Email,
                                EqualTo, Regexp)
from app.models import User, Paper

class SearchForm(FlaskForm):
    title = StringField('Title')
    authors = StringField('Authors')
    abstract = StringField('Abstract')
    subber = SelectField('Submitter', validate_choice=False)
    presenter = SelectField('Presenter', validate_choice=False)
    sd_label = 'Submission date range (format MM/DD/YYYY-MM/DD/YYYY)'
    sub_date = StringField(sd_label)
    vd_label = 'Vote date range (format MM/DD/YYYY-MM/DD/YYYY)'
    vote_date = StringField(vd_label)
    submit = SubmitField('Search')

    def validate_date(self, date):
        if date.data == '':
            return
        try:
            for i in date.data.split('-'):
                date = [int(j) for j in i.split('/')]
                if (1>date[0] or 12<date[0]
                    or 1>date[1] or 31<date[1]
                    or 1850>date[2] or 2100<date[2]):
                    raise ValidationError('Date formatting error.')
        except:
            raise ValidationError('Date formatting error.')

    def validate_sub_date(self, sub_date):
        self.validate_date(sub_date)
    def validate_vote_date(self, vote_date):
        self.validate_date(vote_date)
        
class PaperSubmissionForm(FlaskForm):
    link = StringField('Link', validators=[DataRequired()])
    volunteering = BooleanField("I'm volunteering to discuss this paper.")
    comments = StringField('Comments (optional)')
    submit = SubmitField('Submit URL')

    def validate_link(self, link):
        # Validate arxiv.org
        if not 'arxiv' in link.data.lower():
            raise ValidationError('Only arxiv.org links are accepted.'
                                  + 'Consider submitting manually.')

        # Validate uniqueness among non-voted papers
        link_str = link.data.split('?')[0]
        paper = (Paper.query.filter(Paper.voted==None)
                 .filter_by(link=link_str).first())
        if paper is not None:
            print('Validation error raised.')
            raise ValidationError('Link already submitted.')

class ManualSubmissionForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired()])
    link = StringField('Link', validators=[DataRequired()])
    authors = StringField('Authors', validators=[DataRequired()])
    abstract = StringField('Abstract', validators=[DataRequired()])
    volunteering = BooleanField("I'm volunteering to discuss this paper.")
    comments = StringField('Comments (optional)')
    submit = SubmitField('Submit paper.')

    def validate_link(self, link):
        paper = Paper.query.filter_by(link=link.data).first()
        if paper is not None:
            raise ValidationError('Link already submitted.')

    def validate_title(self, title):
        paper = Paper.query.filter_by(title=title.data).first()
        if paper is not None:
            raise ValidationError('Paper with this title already submitted.')

class VoteForm(FlaskForm):
    vote_num = IntegerField()
    vote_den = IntegerField()
    lock = SubmitField('Read vote.')

class FullVoteForm(FlaskForm):
    master_den = IntegerField()
    votes = FieldList(FormField(VoteForm))
    submit = SubmitField('Submit votes.')

class EditForm(FlaskForm):
    comment = SubmitField('Comment')
    volunteer = SubmitField('Volunteer Now')
    vol_later = SubmitField('Volunteer Later')
    unvolunteer = SubmitField('unVolunteer Now')
    unvol_later = SubmitField('unVolunteer Later')
    unsubmit = SubmitField('unSubmit')

class FullEditForm(FlaskForm):
    edits = FieldList(FormField(EditForm))

class CommentForm(FlaskForm):
    comment = StringField('Comment', validators=[DataRequired()])
    submit = SubmitField('Submit.')

class MessageForm(FlaskForm):
    e_from = StringField('From', validators=[DataRequired(), Email()])
    subject = StringField('Subject', validators=[DataRequired()])
    body = TextAreaField('Body', validators=[DataRequired()])
    abstracts = BooleanField('Attach abstracts:', default=True)
    submit = SubmitField('Send.')
