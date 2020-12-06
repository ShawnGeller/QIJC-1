# Quantum Information Journal Club Website

## Accessing the QIJC web application

A mockup of this website (with relaxed user permissions) can be found deployed on [Heroku](https://qijcmockup.herokuapp.com). \
The actual deployment is used by a NIST research lab at CU Boulder. \
The app can be launched on a local machine after installing dependencies and executing "flask run" from the command line, then accessing http://localhost:5000. More detailed instructions are below.

## Features

QIJC serves a journal club. Users request accounts from the administrator. Once approved, users submit research paper links. The application scrapes the metadata using the arXiv.org API or users submit the metadata manually if the scraper fails. Users can volunteer to present papers and comment on the papers directly. Submitted papers are periodically emailed out to the full list, voted on by the collective group and archived by vote instance. Users can search through submitted papers by any combination of fields. Users can view each others profiles, which list submitted papers and a point ranking system for engagement. Administrators have access to a management page for changing user permissions or retiring users.

### QIJC is a responsive full-stack flask application written with the use of Flask libraries:
* User authentication with Flask-Login
* WTForms with Flask-WTF
* Bootstrap with Flask-Bootstrap
* Blueprints with Flask-Blueprint
* SQLite with Flask-SQLAlchemy
* Outgoing mail service with Flask-Mail
* Sessions with Flask-Session
* Views rendered with HTML, CSS, Bootstrap & Jinja2

## Maintenance Specifications & Testing
This application is written in Python 3.6. All package requirements are kept up to date in the requirements.txt file.

All unit and integration tests can be run together from the root directory using `python -m pytest`.

## Licensing
This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details.

## Detailed instructions to run application on local machine:

Clone repo: 
```
git clone https://github.com/aradox66/QIJC.git
cd QIJC
```

Create virtual environmental and install dependencies:
```
python3.6 -m venv venv/
source venv/bin/activate
pip install -r requirements.txt
```

Launch with flask from main folder:
```
export FLASK_APP = main.py
flask run
```
