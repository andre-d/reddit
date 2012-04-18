from datetime import datetime
from r2.lib.db import tdb_cassandra
from r2.lib.db.thing import NotFound
from r2.lib.merge import *
from pycassa.system_manager import TIME_UUID_TYPE
from pylons import c, g
from pylons.controllers.util import abort
from r2.models.printable import Printable
from r2.models.account import Account
from collections import OrderedDict

# Used for the key/id for pages,
#   must not be a character allowed in subreddit name
PAGE_ID_SEP = '\t'

# Number of days to keep recent revisions for
WIKI_RECENT_DAYS = g.wiki_keep_recent_days

# Max length of a single page in bytes
MAX_PAGE_LENGTH_BYTES = g.wiki_max_page_length_bytes

# Namespaces in which access is denied to do anything but view
restricted_namespaces = ('reddit/', 'config/', 'special/')

# Pages which may only be edited by mods, must be within restricted namespaces
special_pages = ('config/stylesheet', 'config/sidebar', 'config/description')

# Pages which have a special length restrictions (In bytes)
special_length_restrictions_bytes = {'config/stylesheet': 128*1024, 'config/sidebar': 5120, 'config/description': 500}

# Page "index" in the subreddit "reddit.com" and a seperator of "\t" becomes:
#   "reddit.com\tindex"
def wiki_id(sr, page):
    return '%s%s%s' % (sr, PAGE_ID_SEP, page)

class ContentLengthError(Exception):
    def __init__(self, max_length):
        Exception.__init__(self)
        self.max_length = max_length

class WikiPageExists(Exception):
    pass

class WikiPageEditors(tdb_cassandra.View):
    _use_db = True
    _value_type = 'str'
    _connection_pool = 'main'

def get_author_name(author_name):
    if not author_name:
        return "[unknown]"
    try:
        return Account._by_name(author_name).name
    except NotFound:
        return '[deleted]'

class WikiRevision(tdb_cassandra.UuidThing, Printable):
    """ Contains content (markdown), author of the edit, page the edit belongs to, and datetime of the edit """
    
    _use_db = True
    _connection_pool = 'main'
    
    _str_props = ('pageid', 'content', 'author', 'reason')
    _bool_props = ('hidden')
    
    cache_ignore = set(['subreddit'] + list(_str_props)).union(Printable.cache_ignore)
    
    def author_name(self):
        return get_author_name(self._get('author'))
    
    @classmethod
    def add_props(cls, user, wrapped):
        for item in wrapped:
            item._hidden = item.is_hidden
            item._fullname = item._id
            item._spam = False
            item.reported = False
    
    @classmethod
    def get(cls, revid, pageid):
        wr = cls._byID(revid)
        if wr.pageid != pageid:
            raise ValueError('Revision is not for the expected page')
        return wr
    
    def toggle_hide(self):
        self.hidden = not self.is_hidden
        self._commit()
        return self.hidden
    
    @classmethod
    def create(cls, pageid, content, author=None, reason=None):
        kw = dict(pageid=pageid, content=content)
        if author:
            kw['author'] = author
        if reason:
            kw['reason'] = reason
        wr = cls(**kw)
        wr._commit()
        WikiRevisionsByPage.add_object(wr)
        WikiRevisionsRecentBySR.add_object(wr)
        return wr
    
    def _on_commit(self):
        WikiRevisionsByPage.add_object(self)
        WikiRevisionsRecentBySR.add_object(self)
    
    @classmethod
    def get_recent(cls, sr, count=100):
        return WikiRevisionsRecentBySR.query([sr], count=count)
    
    @property
    def is_hidden(self):
        return bool(self._get('hidden', False))
    
    @property
    def info(self, sep=PAGE_ID_SEP):
        info = self.pageid.split(sep, 1)
        try:
            return {'sr': info[0], 'page': info[1]}
        except IndexError:
            g.log.error('Broken wiki page ID "%s" did PAGE_ID_SEP change?', self.pageid)
            return {'sr': 'broken', 'page': 'broken'}
    
    @property
    def page(self):
        return self.info['page']
    
    @property
    def sr(self):
        return self.info['sr']


class WikiPage(tdb_cassandra.Thing):
    """ Contains permissions, current content (markdown), subreddit, and current revision (ID)
        Key is subreddit-pagename """
    
    _use_db = True
    _connection_pool = 'main'
    
    _read_consistency_level = tdb_cassandra.CL.QUORUM
    _write_consistency_level = tdb_cassandra.CL.QUORUM
    
    _date_props = ('last_edit_date')
    _str_props = ('revision', 'name', 'last_edit_by', 'content', 'sr')
    _int_props = ('permlevel')
    _bool_props = ('listed_')
    
    def author_name(self):
        return get_author_name(self._get('last_edit_by'))
    
    @classmethod
    def get(cls, sr, name):
        name = name.lower()
        return cls._byID(wiki_id(sr, name))
    
    @classmethod
    def create(cls, sr, name):
        name = name.lower()
        kw = dict(sr=sr, name=name, permlevel=0, content='', listed_=False)
        page = cls(**kw)
        page._commit()
        return page
    
    @property
    def restricted(self):
        return WikiPage.is_restricted(self.name)
    
    @classmethod
    def is_restricted(cls, page):
        return ("%s/" % page) in restricted_namespaces or page.startswith(restricted_namespaces)
    
    @classmethod
    def is_special(cls, page):
        return page in special_pages
    
    @property
    def special(self):
        return WikiPage.is_special(self.name)
    
    def add_to_listing(self):
        WikiPagesBySR.add_object(self)
        self.listed_ = True
    
    def _on_create(self):
        self.add_to_listing()
        self._committed = True # Prevent infinite loop
        self._commit()
    
    def _on_commit(self):
        if not self._get('listed_'):
            self.add_to_listing()
            self._commit()
    
    def remove_editor(self, user):
        WikiPageEditors._remove(self._id, [user])
    
    def add_editor(self, user):
        WikiPageEditors._set_values(self._id, {user: ''})
    
    @classmethod
    def get_pages(cls, sr, after=None):
        NUM_AT_A_TIME = 1000
        pages = WikiPagesBySR.query([sr], after=after, count=NUM_AT_A_TIME)
        pages = [p for p in pages]
        if len(pages) == NUM_AT_A_TIME:
            return pages + self.get_listing(sr, after=pages[-1])
        return pages
    
    @classmethod
    def get_listing(cls, sr):
        """
            Create a tree of pages from their path.
        """
        page_tree = OrderedDict()
        pages = sorted(cls.get_pages(sr), key=lambda page: page.name)
        for page in pages:
            p = page.name.split('/')
            cur_node = page_tree
            # Loop through all elements of the path except the page name portion
            for name in p[:-1]:
                next_node = cur_node.get(name)
                # If the element did not already exist in the tree, create it
                if not next_node:
                    new_node = dict()
                    cur_node[name] = [None, new_node]
                else:
                    # Otherwise, continue through
                    new_node = next_node[1]
                cur_node = new_node
            # Get the actual page name portion of the path
            pagename = p[-1]
            node = cur_node.get(pagename)
            # The node may already exist as a path name in the tree
            if node:
                node[0] = page
            else:
                cur_node[pagename] = [page, dict()]
                
        return page_tree
    
    def get_editors(self):
        try:
            return WikiPageEditors._byID(self._id)._values() or []
        except tdb_cassandra.NotFoundException:
            return []
    
    def revise(self, content, previous = None, author=None, force=False, reason=None):
        if self.content == content:
            return
        max_length = special_length_restrictions_bytes.get(self.name, MAX_PAGE_LENGTH_BYTES)
        if len(content) > max_length:
            raise ContentLengthError(max_length)
        try:
            revision = self.revision
        except:
            revision = None
        if not force and (revision and previous != revision):
            if previous:
                origcontent = WikiRevision.get(previous, pageid=self._id).content
            else:
                origcontent = ''
            content = threeWayMerge(origcontent, content, self.content)
        
        wr = WikiRevision.create(self._id, content, author, reason)
        self.content = content
        self.last_edit_by = author
        self.last_edit_date = wr.date
        self.revision = wr._id
        self._commit()
        return wr
    
    def change_permlevel(self, permlevel, force=False):
        if permlevel == self.permlevel:
            return
        if not force and int(permlevel) not in range(3):
            raise ValueError('Permlevel not valid')
        self.permlevel = permlevel
        self._commit()
    
    def get_revisions(self, after=None, count=100):
        return WikiRevisionsByPage.query([self._id], after=after, count=count)
    
    def _commit(self, *a, **kw):
        if not self._id: # Creating a new page
            pageid = wiki_id(self.sr, self.name)
            try:
                WikiPage._byID(pageid)
                raise WikiPageExists()
            except tdb_cassandra.NotFound:
                self._id = pageid   
        return tdb_cassandra.Thing._commit(self, *a, **kw)

class WikiRevisionsByPage(tdb_cassandra.DenormalizedView):
    """ Associate revisions with pages """
    
    _use_db = True
    _connection_pool = 'main'
    _view_of = WikiRevision
    _compare_with = TIME_UUID_TYPE
    
    @classmethod
    def _rowkey(cls, wr):
        return wr.pageid

class WikiPagesBySR(tdb_cassandra.DenormalizedView):
    """ Associate revisions with subreddits, store only recent """
    _use_db = True
    _connection_pool = 'main'
    _view_of = WikiPage
    
    @classmethod
    def _rowkey(cls, wp):
        return wp.sr

class WikiRevisionsRecentBySR(tdb_cassandra.DenormalizedView):
    """ Associate revisions with subreddits, store only recent """
    _use_db = True
    _connection_pool = 'main'
    _view_of = WikiRevision
    _compare_with = TIME_UUID_TYPE
    _ttl = 60*60*24*WIKI_RECENT_DAYS
    
    @classmethod
    def _rowkey(cls, wr):
        return wr.sr


