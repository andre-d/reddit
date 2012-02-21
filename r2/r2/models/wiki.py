from r2.lib.db import tdb_cassandra
from r2.lib.merge import threeWayMerge
from pycassa.system_manager import TIME_UUID_TYPE
from pylons import c, g
from pylons.controllers.util import abort

def wiki_id(sr, page):
    return '%s.%s' % (sr, page)

class WikiPageExists(Exception):
    pass

class WikiRevision(tdb_cassandra.UuidThing):
    """ Contains content (markdown), author of the edit, page the edit belongs to, and datetime of the edit """
    
    _use_db = True
    _connection_pool = 'main'
    
    _str_props = ('pageid', 'content', 'author')
    
    @classmethod
    def get(cls, revid, pageid=None):
        wr = cls._byID(revid)
        if pageid and wr.pageid != pageid:
            raise ValueError('Revision is not for the expected page')
        return wr
    
    @classmethod
    def create(cls, pageid, content, author=None):
        kw = dict(pageid=pageid, content=content)
        if author:
            kw['author'] = author
        wr = cls(**kw)
        wr._commit()
        WikiRevisionsByPage.add_object(wr)
        WikiRevisionsRecentBySR.add_object(wr)
        return wr
    
    @classmethod
    def get_recent(cls, sr, count=100):
        raw = WikiRevisionsRecentBySR.query([sr], count=count)
        revisions = [r for r in raw]
        return revisions
    
    @property
    def is_hidden(self):
        return bool(self._get('hidden', False))
    
    @property
    def page(self):
        return self.pageid.split('.')[1]
    
    @property
    def sr(self):
        return self.pageid.split('.')[0]


class WikiPage(tdb_cassandra.Thing):
    """ Contains permissions, current content (markdown), subreddit, and current revision (ID)
        Key is subreddit-pagename """
    
    _use_db = True
    _connection_pool = 'main'
    
    _read_consistency_level = tdb_cassandra.CL.QUORUM
    _write_consistency_level = tdb_cassandra.CL.QUORUM
    
    _str_props = ('revision', 'name', 'content', 'sr', 'permlevel')
    
    @classmethod
    def get(cls, sr, name):
        name = name.lower()
        return cls._byID(wiki_id(sr, name))
    
    @classmethod
    def create(cls, sr, name):
        name = name.lower()
        kw = dict(sr=sr, name=name, permlevel=0, content='')
        page = cls(**kw)
        page._commit()
        return page
    
    def revise(self, content, previous = None, author=None, force=False):
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
        
        wr = WikiRevision.create(self._id, content, author)
        self.content = content
        self.revision = wr._id
        self._commit()
        return wr
    
    def change_permlevel(self, permlevel):
        if permlevel == self.permlevel:
            return
        if int(permlevel) not in range(3):
            raise ValueError('Permlevel not valid')
        self.permlevel = permlevel
        self._commit()
    
    def get_revisions(self, after=None, count=10):
        raw = WikiRevisionsByPage.query([self._id], after=after, count=count)
        revisions = [r for r in raw]
        return revisions
    
    def _commit(self, *a, **kw):
        if not self._id: # Creating a new page
            pageid = wiki_id(self.sr, self.name)
            try:
                WikiPage._byID(pageid)
                raise WikiPageExists()
            except tdb_cassandra.NotFound:
                self._id = pageid   
        return tdb_cassandra.Thing._commit(self, *a, **kw)

class WikiRevisionsByPage(tdb_cassandra.View):
    """ Associate revisions with pages """
    
    _use_db = True
    _connection_pool = 'main'
    _view_of = WikiRevision
    _compare_with = TIME_UUID_TYPE
    
    @classmethod
    def _rowkey(cls, wr):
        return wr.pageid

class WikiRevisionsRecentBySR(tdb_cassandra.View):
    """ Associate revisions with subreddits, store only recent """
    _use_db = True
    _connection_pool = 'main'
    _view_of = WikiRevision
    _compare_with = TIME_UUID_TYPE
    _ttl = 60*60*24*7 # One week - (Barenaked Ladies)
    
    @classmethod
    def _rowkey(cls, wr):
        return wr.sr


