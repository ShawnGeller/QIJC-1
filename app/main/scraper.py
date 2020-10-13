import requests
from xml.etree import ElementTree as et
from flask import flash
import re
import arxiv

class Scraper(object):
    failed = 0
    error = 0

    def arxiv_scrape(self, link):
        # id = link.split('/')[-1]
        m = re.match(".*/([0-9.]+).*", link)
        if m is not None:
            id = m.groups()[0]
        q = arxiv.query(id_list=[id])[0]
        authors = q['authors']
        title = q['title']
        abstract = q['summary']
        return authors, abstract, title
    
    def get(self, link):
        authors = abstract = title = ''
        if 'arxiv' in link:
            authors, abstract, title = self.arxiv_scrape(link)
        self.authors = authors
        self.abstract = abstract
        self.title = title
        if (authors=='') and (abstract=='') and (title==''):
            self.failed = 1
        if title == 'error':
            self.error = 1
