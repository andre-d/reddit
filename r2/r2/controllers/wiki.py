from pylons import request, g, c
from reddit_base import RedditController
from r2.lib.merge import ConflictException
from r2.models.wiki import WikiPage, WikiRevision
from r2.models.subreddit import Subreddit
from r2.models.modaction import ModAction
from r2.lib.db import tdb_cassandra
from r2.lib.pages import BoringPage
from r2.lib.pages.wiki import *
from pylons.controllers.util import abort
from r2.lib.filters import safemarkdown
from validator.wiki import *
import difflib
from pylons.i18n import _

page_descriptions = {'config/stylesheet':_("This page is the subreddit css, please edit from the subreddit stylesheet interface"),
                     'config/sidebar':_("The contents of this page appear on the subreddit sidebar")}

class WikiController(RedditController):
    def make_htmldiff(self, a, b, adesc, bdesc):
        diffcontent = difflib.HtmlDiff()
        return diffcontent.make_table(a.splitlines(),
                                      b.splitlines(),
                                      fromdesc=adesc,
                                      todesc=bdesc)
    
    @validate(pv = VWikiPageAndVersion(('page', 'v'), restricted=False))
    def GET_wikiPage(self, pv):
        page, version = pv
        message = None
        if not page:
            return self.GET_wikiCreate(page=c.page, view=True)
        if not version:
            content = page.content
            if c.is_mod and page.name in page_descriptions:
                message = page_descriptions[page.name]
        else:
            content = version.content
            message = _("Viewing revision %s") % version._id
        showactions = c.is_mod or (page.name not in special_pages)
        show_settings = False if page.name in special_pages else c.is_mod
        c.allow_styles = True
        diffcontent = None
        if version:
            diffcontent = self.make_htmldiff(content, page.content, version._id, _("Current revision"))
        return WikiPageView(content, canedit=may_revise(page), showactions=showactions, show_settings=show_settings, alert=message, v=version, diff=diffcontent).render()
    
    @validate(pv = VWikiPageAndVersion(('page', 'l'), restricted=False))
    def GET_wikiRevisions(self, pv, page):
        page, after = pv
        revisions = page.get_revisions(after=after, count=11)
        if not after and revisions:
            revisions[0]._current = True
        last=None
        # We get an extra revision to determine if there will be any on the next page
        if len(revisions) > 10:
            revisions = revisions[:-1]
            try:
                last=revisions[-1]._id
            except IndexError:
                pass # Should not happen
        return WikiRevisions(revisions, last).render()
    
    @validate(may_create = VWikiPageCreate('page'))
    def GET_wikiCreate(self, may_create, page, view=False):
        if c.error:
            return BoringPage(_("Wiki error"), infotext=c.error).render()
        if view:
            return WikiNotFound().render()
        if may_create:
            WikiPage.create(c.wiki_sr.name, page)
            return self.redirect('%s/edit/%s' % (c.wiki_base_url, page))
        return self.GET_wikiPage(page=page)
    
    @validate(page = VWikiPageRevise('page', restricted=True))
    def GET_wikiRevise(self, page):
        message = None
        try:
            previous = page.revision
        except AttributeError:
            previous = None
        diffcontent = None
        revise = None
        if page.name in page_descriptions:
            message = page_descriptions[page.name]
        if self.editconflict:
            diffcontent = self.make_htmldiff(page.content, self.editconflict, _("Current edit"), _("Your edit"))
            revise = (self.editconflict, diffcontent)
        return WikiEdit(page.content, previous, revise, alert=message).render()
   
    def GET_wikiRecent(self):
        revisions = WikiRevision.get_recent(c.wiki_sr.name)
        return WikiRecent(revisions).render()
    
    @validate(page = VWikiPageRevise('page', restricted=True))
    def POST_wikiRevise(self, page):
        try:
            page.revise(request.POST['content'], request.POST['previous'], c.user.name)
            if c.is_mod:
                description = _("Page %s edited") % page
                ModAction.create(c.wiki_sr, c.user, 'wikirevise', description=description)
        except ConflictException:
            self.editconflict = request.POST['content']
            return self.GET_wikiRevise(page=page.name)
        return self.redirect('%s/%s' % (c.wiki_base_url, page.name))
    
    @validate(page = VWikiPage('page', restricted=True, modonly=True))
    def GET_wikiSettings(self, page):
        settings = {'permlevel': int(page._get('permlevel', 0))}
        return WikiSettings(settings).render()
    
    @validate(page = VWikiPage('page', restricted=True, modonly=True))
    def POST_wikiSettings(self, page):
        oldpermlevel = page.permlevel
        permlevel = request.POST['permlevel']
        try:
            page.change_permlevel(permlevel)
        except ValueError:
            abort(403)
        description = _("Page: %s, Changed from %s to %s") % (page.name, oldpermlevel, permlevel)
        ModAction.create(c.wiki_sr, c.user, 'wikipermlevel', description=description)
        return self.GET_wikiSettings(page=page.name)
    
    def pre(self):
        RedditController.pre(self)
        c.frontpage = c.site.name == ' reddit.com'
        c.wiki_sr = Subreddit._by_name(g.default_sr) if c.frontpage else c.site
        c.wiki_base_url = '/wiki' if c.frontpage else '/r/'+c.wiki_sr.name+'/wiki'
        c.is_mod = False
        self.editconflict = False
        if c.user_is_loggedin:
            c.is_mod = c.wiki_sr.is_moderator(c.user)
        c.wikidisabled = False
        mode = c.wiki_sr.wikimode
        if not mode or mode == 'disabled':
            if not c.is_mod:
                abort(403)
            else:
                c.wikidisabled = True
                
        
