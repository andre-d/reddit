from validator import Validator
from validator import validate
from pylons import c, g, request
from os.path import normpath
from r2.lib.db import tdb_cassandra
from r2.models.wiki import WikiPage, WikiRevision
from pylons.controllers.util import abort
import datetime
import simplejson

MAX_PAGE_NAME_LENGTH = 128

MAX_SEPERATORS = 3

def jsonAbort(code, reason=None, **data):
    data['code'] = code
    data['reason'] = reason if reason else 'UNKNOWN_ERROR'
    if c.extension == 'json':
        request.environ['usable_error_content'] = simplejson.dumps(data)
    abort(code)

def may_revise(page=None):
    if c.is_mod:
        return True
    if page and page.restricted and not page.special:
            return False
    if not c.user_is_loggedin:
        return False
    if c.site.is_wikibanned(c.user):
        return False
    if not may_view(page):
        return False
    if not c.user.can_wiki():
        return False
    if page and c.user.name in page.get_editors():
        return True
    if not c.site.can_submit(c.user):
        return False
    if page and page.special:
        return False
    elif page and page.permlevel > 0:
        return False
    if c.site.is_wikicontributor(c.user):
        return True
    karma = max(c.user.karma('link', c.site), c.user.karma('comment', c.site))
    if karma < c.site.wiki_edit_karma:
        return False
    age = (datetime.datetime.now(g.tz) - c.user._date).days
    if age < c.site.wiki_edit_age:
        return False
    return True

def may_view(page):
    if not page:
        return True
    if c.is_mod:
        return True
    if page.special:
        return True
    level = page.permlevel
    if level < 2:
        return True
    if level == 2:
        return c.is_mod
    return False

def normalize_page(page):
    # Case insensitive page names
    page = page.lower()
    # Normalize path
    page = normpath(page)
    # Chop off initial "/", just in case it exists
    page = page[1:] if page.startswith('/') else page
    return page

class VWikiPage(Validator):
    def __init__(self, param, restricted=True, modonly=False, **kw):
        self.restricted = restricted
        self.modonly = modonly
        Validator.__init__(self, param, **kw)
    
    def run(self, page):
        if not page:
            page = "index"
        
        page = normalize_page(page)
        
        c.page = page
        if not c.is_mod and self.modonly:
            jsonAbort(403, 'MOD_REQUIRED')
        wp = self.ValidPage(page)
        c.page_obj = wp
        return wp
    
    def ValidPage(self, page):
        try:
            wp = WikiPage.get(c.wiki_id, page)
            if self.restricted and wp.restricted:
                if not wp.special:
                    jsonAbort(403, 'RESTRICTED_PAGE')
            if not may_view(wp):
                jsonAbort(403, 'MAY_NOT_VIEW')
            return wp
        except tdb_cassandra.NotFound:
            if not c.user_is_loggedin:
                jsonAbort(404, 'LOGIN_REQUIRED')
            if c.user_is_admin:
                return # admins may always create
            if WikiPage.is_restricted(page):
                if not(c.is_mod and WikiPage.is_special(page)):
                    jsonAbort(404, 'PAGE_NOT_FOUND', may_create=False)
    
    def ValidVersion(self, version, pageid=None):
        if not version:
            return
        try:
            r = WikiRevision.get(version, pageid)
            if r.is_hidden and not c.is_mod:
                jsonAbort(403, 'HIDDEN_REVISION')
            return r
        except (tdb_cassandra.NotFound, ValueError):
            jsonAbort(404, 'INVALID_REVISION')

class VWikiPageAndVersion(VWikiPage):    
    def run(self, page, *versions):
        wp = VWikiPage.run(self, page)
        validated = []
        for v in versions:
            validated += [self.ValidVersion(v, wp._id) if v and wp else None]
        return tuple([wp] + validated)

class VWikiPageRevise(VWikiPage):
    def run(self, page, previous=None):
        wp = VWikiPage.run(self, page)
        if not wp:
            jsonAbort(404, 'INVALID_PAGE')
        if not may_revise(wp):
            jsonAbort(403, 'MAY_NOT_REVISE')
        if previous:
            prev = self.ValidVersion(previous, wp._id)
            return (wp, prev)
        return (wp, None)

class VWikiPageCreate(Validator):
    def run(self, page):
        page = normalize_page(page)
        if page.count('/') > MAX_SEPERATORS:
            c.error = {'reason': 'PAGE_NAME_MAX_SEPERATORS', 'max_seperators': MAX_SEPERATORS}
            return False
        try:
            if not len(page) > MAX_PAGE_NAME_LENGTH:
                WikiPage.get(c.wiki_id, page)
            else:
                c.error = {'reason': 'PAGE_NAME_LENGTH', 'max_length': MAX_PAGE_NAME_LENGTH}
            return False
        except tdb_cassandra.NotFound:
            if not may_revise():
                jsonAbort(403, 'MAY_NOT_CREATE')
            else:
                return True
