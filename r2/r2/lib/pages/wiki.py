from r2.lib.pages.pages import Reddit
from pylons import c
from r2.lib.wrapped import Templated
from r2.lib.menus import PageNameNav
from r2.lib.filters import wikimarkdown
from pylons.i18n import _

class WikiView(Templated):
    def __init__(self, content, diff=None):
        self.page_content = wikimarkdown(content)
        self.diff = diff
        self.base_url = c.wiki_base_url
        Templated.__init__(self)

class WikiEditPage(Templated):
    def __init__(self, page_content, previous):
        self.page_content = page_content
        self.previous = previous
        self.base_url = c.wiki_base_url
        Templated.__init__(self)

class WikiPageSettings(Templated):
    def __init__(self, settings):
        self.permlevel = settings['permlevel']
        self.base_url = c.wiki_base_url
        Templated.__init__(self)

class WikiPageRevisions(Templated):
    def __init__(self, revisions):
        self.revisions = revisions
        Templated.__init__(self)

class WikiBasePage(Templated):
    def __init__(self, content, action, actions=[], showtitle=False):
        self.actions = actions[:]
        self.actions += [('revisions', _("Recent Edits"), 'moderationlog', False)]
        if not c.frontpage and c.is_mod:
            self.actions += [('../about/wikibanned', _("Ban Users From Contributing To This Wiki"), 'ban', False)]
            self.actions += [('../about/wikicreate', _("Approve Users For Submitting"), 'contributors', False)]
            self.actions += [('../about/wikirevise', _("Approve Users For Editing"), 'contributors', False)]
        self.base_url = c.wiki_base_url
        if showtitle:
            self.title = _("%s wiki (%s)") % (action, c.wiki_sr.name)
            if c.page:
                self.title +=  ' - %s' % c.page
        else:
            self.title = ''
        self.content = content
        Templated.__init__(self)

class WikiBase(Reddit):
    def __init__(self, content, actions=[], **context):
        action = context.get('wikiaction', _("Viewing"))
        context['title'] = c.wiki_sr.name
        if context.get('alert', None):
            context['infotext'] = context['alert']
        elif c.wikidisabled:
            context['infotext'] = _("This wiki is currently disabled, only mods may interact with this wiki")
        context['content'] = WikiBasePage(content, action, actions, context.get('showtitle', True))
        Reddit.__init__(self, **context)

class WikiPageView(WikiBase):
    def __init__(self, content, diff=None, canedit=False, **context):
        actions = []
        if not content and not context['alert']:
            if canedit:
                context['alert'] = _("This page is empty, edit it to add some content.")
        if context.get('v'):
            actions += [(c.page, _("View Current"), 'moderators', False)]
        elif context.get('showactions'):
            if canedit:
                actions += [('edit', _("Edit This Page"), 'contributors', True)]
            actions += [('revisions', _("View Revisions"), 'moderationlog', True)]
            if context.get('show_settings'):
                actions += [('settings', _("Page Settings"), 'edit', True)]
        actions += [('discussions', _("Discussions For This Page"), 'moderationlog', True)]
        content = WikiView(content, diff=diff)
        WikiBase.__init__(self, content, actions=actions, **context)

class WikiNotFound(WikiBase):
    def __init__(self, **context):
        actions = [('create',_("Page does not exist - Create"), 'contributors', True)]
        context['alert'] = _("Page %s does not exist in this subreddit") % c.page
        WikiBase.__init__(self, '', actions=actions, showtitle=False, **context)

class WikiEdit(WikiBase):
    def __init__(self, content, previous, **context):
        content = WikiEditPage(content, previous)
        context['wikiaction'] = 'Editing'
        WikiBase.__init__(self, content, **context)

class WikiSettings(WikiBase):
    def __init__(self, settings, **context):
        content = WikiPageSettings(settings)
        context['wikiaction'] = _("Settings for")
        WikiBase.__init__(self, content, **context)

class WikiRevisions(WikiBase):
    def __init__(self, revisions, **context):
        content = WikiPageRevisions(revisions)
        context['wikiaction'] = _("Revisions for")
        WikiBase.__init__(self, content, **context)

class WikiRecent(WikiBase):
    def __init__(self, revisions, **context):
        content = WikiPageRevisions(revisions)
        context['wikiaction'] = _("Revisions for")
        WikiBase.__init__(self, content, **context)

class WikiDiscussions(WikiBase):
    def __init__(self, listing, **context):
        context['wikiaction'] = _("Discussions for")
        actions = [(c.page, _("View Page"), 'moderators', False)]
        WikiBase.__init__(self, listing, actions=actions, **context)

