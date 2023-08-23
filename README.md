# Quantum Information Journal Club Website

## Licensing
This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details.

## Detailed instructions to run application on local machine:

Clone repo: 
```
git clone https://github.com/ShawnGeller/QIJC-1.git
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
