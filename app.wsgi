to_activate = '/data/virtualenv/qijc/bin/activate_this.py'
with open(to_activate) as f_:
    exec(f_.read(), dict(__file__=to_activate))

import sys
sys.path.insert(-1, '/data/wsgi/qijc/app')

from app import create_app, db
from app.models import User, Paper

app = create_app()
application = app

@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'User': User, 'Paper': Paper}

if __name__ == '__main__':
    app.run()
