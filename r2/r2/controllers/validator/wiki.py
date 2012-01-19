from validator import Validator
from validator import validate
from pylons import c, g
from os.path import normpath
from r2.lib.db import tdb_cassandra
from r2.models.wiki import WikiPage, WikiRevision 
from pylons.controllers.util import abort
from pylons.i18n import _

# Namespaces in which access is denied to do anything but view
restricted_namespaces = ('reddit/', 'config/', 'special/')
# Pages which may only be edited by mods, must be within restricted namespaces
special_pages = ('config/stylesheet', 'config/sidebar')

MAX_PAGE_NAME_LENGTH = 128

MAX_SEPERATORS = 2

def may_revise(page=None):
    if c.is_mod:
        return True
    if not c.user_is_loggedin:
        return False
    if c.site.is_wikibanned(c.user):
        return False
    if not c.site.can_submit(c.user):
        if page and c.user.name in page.get_editors():
            return True
        return False
    if c.user.can_wiki() is False:
        return False
    if not c.is_mod and c.user.can_wiki() is not True:
        if c.site.is_wikicontribute(c.user):
            return True
        if c.user.karma('link', c.site) < c.site.wiki_edit_karma:
            return False
    if c.site.wikimode == 'modonly' and not c.is_mod:
        return False
    if page:
        level = int(page.permlevel)
        if level == 0:
            return True
        if level == 1:
            if c.user.name in page.get_editors():
                return True
        return False
    return True
   

def may_view(page):
    if c.user_is_admin:
        return True
    level = int(page.permlevel)
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
            abort(403)
        wp = self.ValidPage(page)
        c.page_obj = wp
        return wp
    
    def ValidPage(self, page):
        try:
            wp = WikiPage.get(c.wiki_id, page)
            if c.user_is_admin:
                return wp # Pages are always valid for admins
            if not may_view(wp):
                abort(403)
            if self.restricted and ("%s/" % page in restricted_namespaces or page.startswith(restricted_namespaces)):
                if not(c.is_mod and page in special_pages):
                    abort(403)
            return wp
        except tdb_cassandra.NotFound:
            if not c.user_is_loggedin:
                abort(404)
            if c.user_is_admin:
                return # admins may always create
            if page.startswith(restricted_namespaces):
                if not(c.is_mod and page in special_pages):
                    abort(403)
    
    def ValidVersion(self, version, pageid=None):
        if not version:
            return
        try:
            r = WikiRevision.get(version, pageid)
            if r.is_hidden and not c.is_mod:
                abort(403)
            return r
        except (tdb_cassandra.NotFound, ValueError):
            abort(404)

class VWikiPageAndVersion(VWikiPage):    
    def run(self, page, *versions):
        wp = VWikiPage.run(self, page)
        validated = []
        for v in versions:
            validated += [self.ValidVersion(v, wp._id) if v else None]
        return tuple([wp] + validated)

class VWikiPageRevise(VWikiPage):
    def run(self, page, previous=None):
        wp = VWikiPage.run(self, page)
        if not wp:
            abort(404)
        if not may_revise(wp):
            abort(403)
        if previous:
            prev = self.ValidVersion(previous, wp._id)
            return (wp, prev)
        return (wp, None)

class VWikiPageCreate(Validator):
    def run(self, page):
        page = normalize_page(page)
        if page.count('/') > MAX_SEPERATORS:
            c.error = _('A max of %d separators "/" are allowed in a wiki page name.') % MAX_SEPERATORS
            return False
        try:
            if not len(page) > MAX_PAGE_NAME_LENGTH:
                WikiPage.get(c.wiki_id, page)
            else:
                c.error = _('This wiki cannot handle page names of that magnitude!  Please select a page name shorter than %d characters') % MAX_PAGE_NAME_LENGTH
            return False
        except tdb_cassandra.NotFound:
            if not may_revise():
                abort(403)
            else:
                return True
