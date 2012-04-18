from validator import Validator
from pylons import c, g, request
from os.path import normpath
from r2.lib.db import tdb_cassandra
from r2.models.wiki import WikiPage, WikiRevision
from pylons.controllers.util import abort
import datetime
import json

MAX_PAGE_NAME_LENGTH = g.wiki_max_page_name_length

MAX_SEPERATORS = g.wiki_max_page_seperators

def jsonAbort(code, reason=None, **data):
    data['code'] = code
    data['reason'] = reason if reason else 'UNKNOWN_ERROR'
    if c.extension == 'json':
        request.environ['usable_error_content'] = json.dumps(data)
    abort(code)

def may_revise(page=None):
    if not c.user_is_loggedin:
        # Users who are not logged in may not contrubute
        return False
    
    if c.is_mod:
        # Mods may always contribute
        return True
    
    if page and page.restricted and not page.special:
        # People may not contribute to restricted pages
        # (Except for special pages)
        return False

    if c.site.is_wikibanned(c.user):
        # Users who are wiki banned in the subreddit may not contribute
        return False
    
    if page and not may_view(page):
        # Users who are not allowed to view the page may not contribute to the page
        return False
    
    if not c.user.can_wiki():
        # Global wiki contributute ban
        return False
    
    if page and c.user.name in page.get_editors():
        # If the user is an editor on the page, they may edit
        return True
    
    if not c.site.can_submit(c.user):
        # If the user can not submit to the subreddit
        # They should not be able to contribute
        return False
    
    if page and page.special:
        # If this is a special page
        # (and the user is not a mod or page editor)
        # They should not be allowed to revise
        return False
    
    if page and page.permlevel > 0:
        # If the page is beyond "anyone may contribute"
        # A normal user should not be allowed to revise
        return False
    
    if c.site.is_wikicontributor(c.user):
        # If the user is a wiki contributor, they may revise
        return True
    
    karma = max(c.user.karma('link', c.site), c.user.karma('comment', c.site))
    if karma < c.site.wiki_edit_karma:
        # If the user has too few karma, they should not contribute
        return False
    
    age = (datetime.datetime.now(g.tz) - c.user._date).days
    if age < c.site.wiki_edit_age:
        # If they user's account is too young
        # They should not contribute
        return False
    
    # Otherwise, allow them to contribute
    return True

def may_view(page):
    if c.is_mod:
        # Mods may always view
        return True
    
    if page.special:
        # Special pages may always be viewed
        # (Permission level ignored)
        return True
    
    level = page.permlevel
    
    if level < 2:
        # Everyone may view in levels below 2
        return True
    
    if level == 2:
        # Only mods may view in level 2
        return c.is_mod
    
    # In any other obscure level,
    # (This should not happen but just in case)
    # nobody may view.
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
            # If no page is specified, give the index page
            page = "index"
        
        page = normalize_page(page)
        
        c.page = page
        if (not c.is_mod) and self.modonly:
            jsonAbort(403, 'MOD_REQUIRED')
        
        wp = self.ValidPage(page)
        
        # TODO: MAKE NOT REQUIRED
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
        if c.is_mod and WikiPage.is_special(page):
            c.error = {'reason': 'PAGE_CREATED_ELSEWHERE'}
            return False
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
