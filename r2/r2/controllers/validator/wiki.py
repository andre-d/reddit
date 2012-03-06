from validator import Validator
from validator import validate
from pylons import c, g
from r2.lib.db import tdb_cassandra
from r2.models.wiki import WikiPage, WikiRevision 
from pylons.controllers.util import abort
from pylons.i18n import _

# Namespaces in which access is denied
restricted_namespaces = ('reddit/', 'config/', 'special/')
# Pages which may only be edited by mods, may be in restricted namespaces
special_pages = ('config/stylesheet', 'config/sidebar')

MAX_PAGE_NAME_LENGTH = 128


def may_revise(page):
    if not c.is_mod and not c.user.can_wiki():
        if c.user.karma('link', c.wiki_sr) < c.site.wiki_edit_karma:
            return False
    if c.wiki_sr.wikimode == 'modonly' and not c.is_mod:
        if not c.frontpage: # The front page cannot be modonly
            return False
    level = int(page.permlevel)
    if not c.user_is_loggedin:
        return False
    if c.user.can_wiki() == False:
        return False
    if level == 0:
        return True
    if level >= 1:
        return c.is_mod
    return False

def may_view(page):
    level = int(page.permlevel)
    if level < 2:
        return True
    if level == 2:
        return c.is_mod
    return False

class VWikiPage(Validator):
    def __init__(self, param, restricted=True, modonly=False, **kw):
        self.restricted = restricted
        self.modonly = modonly
        Validator.__init__(self, param, **kw)
    
    def run(self, page):
        page = page.lower()
        if not page:
            page="index"
        c.page = page
        if not c.is_mod and self.modonly:
            abort(403)
        wp = self.ValidPage(page)
        return wp
    
    def ValidPage(self, page):
        try:
            wp = WikiPage.get(c.wiki_sr.name, page)
            if not may_view(wp):
                abort(403)
            if self.restricted and page.startswith(restricted_namespaces):
                if not(c.is_mod and page in special_pages):
                    abort(403)
            return wp
        except tdb_cassandra.NotFound:
            if not c.user_is_loggedin:
                abort(404)
            if page.startswith(restricted_namespaces):
                if not(c.is_mod and page in special_pages):
                    abort(403)
    
    def ValidVersion(self, version, pageid=None):
        try:
            return WikiRevision.get(version, pageid)
        except (tdb_cassandra.NotFound, ValueError):
            abort(404)

class VWikiPageAndVersion(VWikiPage):
    def run(self, page, version=None):
        wp = VWikiPage.run(self, page)
        if version:
            version = self.ValidVersion(version, wp._id)
        return (wp, version)

class VWikiPageRevise(VWikiPage):
    def run(self, page):
        wp = VWikiPage.run(self, page)
        if not wp:
            abort(404)
        if not may_revise(wp):
            abort(403)
        return wp

class VWikiPageCreate(Validator):
    def run(self, page):
        try:
            if not len(page) > MAX_PAGE_NAME_LENGTH:
                WikiPage.get(c.wiki_sr.name, page)
            else:
                c.error = _('This wiki cannot handle page names of that magnitude!  Please select a page name shorter than %d characters') % MAX_PAGE_NAME_LENGTH
            return False
        except tdb_cassandra.NotFound:
            return True
