from pages import Reddit
from r2.lib.wrapped import Templated
from pylons import c, request, g
from r2.lib.menus import PageNameNav
from pylons.i18n import _

class WikiView(Templated):
    """Compose message form."""
    def __init__(self, wikiname=None, edit = None, history={}, num=0, message = None, can_edit = False, unedited_page_content=None, page_content=None):
        self.page_content = page_content
        self.history = history
        self.num = num
        self.edit_id = -1
        self.edit_username = "Unknown"
        try:
            self.edit_id = edit._id
            self.edit_username = edit.account.name
        except:
            pass
        self.unedited_page_content = unedited_page_content
        self.page_title = wikiname
        self.message = message
        self.can_edit = can_edit
        Templated.__init__(self)

class WikiPage(Reddit):
    def __init__(self, pagename, content=WikiView()):
        context={}
        self.wikiPage = pagename
        self.pageTitle = "%s - Wiki" % (c.site.name or g.default_sr)
        if self.wikiPage:
            self.pageTitle+=": %s" % (self.wikiPage)
        context['title'] = self.pageTitle
        name = c.site.name or g.default_sr
        context['content'] = content
        context['show_sidebar'] = False
        Reddit.__init__(self, **context)
    
    def build_toolbars(self):
        return [PageNameNav('nomenu', title = self.pageTitle)]

