from r2.lib.pages.pages import Reddit
from pylons import c
from r2.lib.wrapped import Templated
from r2.lib.menus import PageNameNav
from r2.lib.filters import safemarkdown

class WikiView(Templated):
    def __init__(self, content, actions):
        self.page_content = safemarkdown(content)
        self.page = c.page
        self.actions = actions
        self.base_url = c.wiki_base_url
        Templated.__init__(self)

class WikiEditPage(Templated):
    def __init__(self, page_content, previous, conflict = False):
        self.page_content = page_content
        self.previous = previous
        self.conflict = conflict
        Templated.__init__(self)

class WikiPageSettings(Templated):
    def __init__(self, settings):
        self.permlevel = settings['permlevel']
        Templated.__init__(self)

class WikiPageRevisions(Templated):
    def __init__(self, revisions, last):
        self.page = c.page
        self.revisions = revisions
        self.last = last
        self.base_url = c.wiki_base_url
        Templated.__init__(self)

class WikiBasePage(Templated):
    def __init__(self, content, action, showtitle=False):
        if showtitle:
            self.title = "%s wiki (%s) - %s" % (action, c.sr, c.page)
        else:
            self.title = ""
        self.content = content
        Templated.__init__(self)

class WikiBase(Reddit):
    def __init__(self, content, **context):
        action = context.get('wikiaction', 'Viewing')
        context['title'] = c.sr
        if context.get('alert', None):
            context['infotext'] = context['alert']
        context['content'] = WikiBasePage(content, action, context.get('showtitle', True))
        Reddit.__init__(self, **context)

class WikiBasic(WikiBase):
    def __init__(self, content, actions, **context):
        content = WikiView(content, actions)
        WikiBase.__init__(self, content, **context)

class WikiPageView(WikiBasic):
    def __init__(self, content, canedit=False, showactions=True, **context):
        actions = []
        if showactions:
            if canedit:
                actions += [('edit','Edit this page', 'contributors')]
            actions += [('revisions', 'View Revisions', 'moderationlog')]
            if c.is_mod:
                actions += [('settings', 'Page settings', 'edit')]
        if not content:
            context["alert"] = "This page is empty, edit it to add some content."
        WikiBasic.__init__(self, content, actions, **context)

class WikiNotFound(WikiBasic):
    def __init__(self, **context):
        actions = [('create','Page does not exist - Create', 'contributors')]
        context["alert"] = "Page %s does not exist in this subreddit" % c.page
        WikiBasic.__init__(self, '', actions, showtitle=False, **context)

class WikiEdit(WikiBase):
    def __init__(self, content, previous, conflict, **context):
        content = WikiEditPage(content, previous, conflict)
        context["wikiaction"] = "Editing"
        if conflict:
            context["alert"] = "There was a conflict, later on this will have usefull info and not destroy your edit :D"
        WikiBase.__init__(self, content, **context)

class WikiSettings(WikiBase):
    def __init__(self, settings, **context):
        content = WikiPageSettings(settings)
        context["wikiaction"] = "Settings for"
        WikiBase.__init__(self, content, **context)

class WikiRevisions(WikiBase):
    def __init__(self, revisions, last, **context):
        content = WikiPageRevisions(revisions, last)
        context["wikiaction"] = "Revisions for"
        WikiBase.__init__(self, content, **context)
