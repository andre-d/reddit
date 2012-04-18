from r2.lib.pages.pages import Reddit
from pylons import c
from r2.lib.wrapped import Templated
from r2.lib.menus import PageNameNav
from r2.controllers.validator.wiki import may_revise
from r2.lib.filters import wikimarkdown
from pylons.i18n import _

class WikiView(Templated):
    def __init__(self, content, edit_by, edit_date, diff=None):
        self.page_content = wikimarkdown(content) if content else ''
        self.page_content_md = content
        self.diff = diff
        self.edit_by = edit_by
        self.edit_date = edit_date
        self.base_url = c.wiki_base_url
        self.may_revise = may_revise(c.page_obj)
        Templated.__init__(self)

class WikiPageListing(Templated):
    def __init__(self, pages):
        self.pages = pages
        self.base_url = c.wiki_base_url
        Templated.__init__(self)

class WikiEditPage(Templated):
    def __init__(self, page_content, previous):
        self.page_content = page_content
        self.previous = previous
        self.base_url = c.wiki_base_url
        Templated.__init__(self)

class WikiPageSettings(Templated):
    def __init__(self, settings, mayedit, show_settings=True, **context):
        self.permlevel = settings['permlevel']
        self.show_settings = show_settings
        self.base_url = c.wiki_base_url
        self.mayedit = mayedit
        Templated.__init__(self)

class WikiPageRevisions(Templated):
    def __init__(self, revisions):
        self.revisions = revisions
        Templated.__init__(self)

class WikiPageDiscussions(Templated):
    def __init__(self, listing):
        self.listing = listing
        Templated.__init__(self)

class WikiBasePage(Templated):
    def __init__(self, content, action, pageactions, globalactions, showtitle=True, description=None, **context):
        self.pageactions = pageactions
        self.globalactions = globalactions
        self.base_url = c.wiki_base_url
        self.action = action
        self.description = description
        if showtitle:
            self.title = action[1]
        else:
            self.title = None
        self.content = content
        Templated.__init__(self)

class WikiBase(Reddit):
    def __init__(self, content, actionless=False, alert=None, **context):
        pageactions = []
        globalactions = []
        if not actionless and c.page:
            pageactions += [(c.page, _("view"), False)]
            if may_revise(c.page_obj):
                pageactions += [('edit', _("edit"), True)]
            pageactions += [('revisions/%s' % c.page, _("history"), False)]
            pageactions += [('discussions', _("talk"), True)]
            if c.is_mod:
                pageactions += [('settings', _("settings"), True)]
        globalactions += [('index', _("wiki home"), False),
                          ('revisions', _("view recent revisions"), False),
                          ('pages', _("list of pages"), False)]
        action = context.get('wikiaction', (c.page, 'wiki'))
        
        context['title'] = c.site.name
        if alert:
            context['infotext'] = alert
        elif c.wikidisabled:
            context['infotext'] = _("this wiki is currently disabled, only mods may interact with this wiki")
        context['content'] = WikiBasePage(content, action, pageactions, globalactions, **context)
        Reddit.__init__(self, **context)

class WikiPageView(WikiBase):
    def __init__(self, content, diff=None, **context):
        if not content and not context.get('alert') and may_revise(c.page_obj):
            context['alert'] = _("this page is empty, edit it to add some content.")
        content = WikiView(content, context.get('edit_by'), context.get('edit_date'), diff=diff)
        WikiBase.__init__(self, content, **context)

class WikiNotFound(WikiPageView):
    def __init__(self, **context):
        context['alert'] = _("page %s does not exist in this subreddit") % c.page
        context['actionless'] = True
        create_link = '%s/create/%s' % (c.wiki_base_url, c.page)
        text =  _("a page with that name does not exist in this subreddit.\n\n[Create a page called %s](%s)") % (c.page, create_link)
        WikiPageView.__init__(self, text, **context)

class WikiEdit(WikiBase):
    def __init__(self, content, previous, **context):
        content = WikiEditPage(content, previous)
        context['wikiaction'] = ('edit', _("editing"))
        WikiBase.__init__(self, content, **context)

class WikiSettings(WikiBase):
    def __init__(self, settings, mayedit, **context):
        content = WikiPageSettings(settings, mayedit, **context)
        context['wikiaction'] = ('settings', _("settings"))
        WikiBase.__init__(self, content, **context)

class WikiRevisions(WikiBase):
    def __init__(self, revisions, **context):
        content = WikiPageRevisions(revisions)
        context['wikiaction'] = ('revisions/%s' % c.page, _("revisions"))
        WikiBase.__init__(self, content, **context)

class WikiRecent(WikiBase):
    def __init__(self, revisions, **context):
        content = WikiPageRevisions(revisions)
        context['wikiaction'] = ('revisions', _("Viewing recent revisions for subreddit"))
        WikiBase.__init__(self, content, **context)

class WikiListing(WikiBase):
    def __init__(self, pages, **context):
        content = WikiPageListing(pages)
        context['wikiaction'] = ('pages', _("Viewing pages for subreddit"))
        WikiBase.__init__(self, content, **context)

class WikiDiscussions(WikiBase):
    def __init__(self, listing, **context):
        content = WikiPageDiscussions(listing)
        context['wikiaction'] = ('discussions', _("discussions"))
        WikiBase.__init__(self, content, **context)

