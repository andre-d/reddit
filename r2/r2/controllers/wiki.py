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

restricted_pages = {"config/stylesheet":"This page is the subreddit css, this is not a normal wiki page, be carefull editing..currently this should be edited in the normal stylesheet location..and will not apply from here",
                    "config/sidebar":"The contents of this page appear on the subreddit sidebar"}

restricted_namespaces = ('reddit/', 'config/', 'special/')

class WikiController(RedditController):
    def GET_wikiPage(self, page="index"):
        version = request.GET.get('v')
        c.page = page
        message = None
        try:
            wp = WikiPage.get(c.sr, page)
            if not wp.may_view():
                abort(403)
        except tdb_cassandra.NotFound:
            if page.startswith(restricted_namespaces):
                abort(403)
            else:
                return WikiNotFound().render()
                
        if not version:
            content = wp.content
        else:
            try:
                content = WikiRevision.get(version, wp._id).content
                message = "Viewing revision %s" % version
            except:
                abort(404)
        showactions = c.is_mod or (page not in restricted_pages)
        c.allow_styles = True
        return WikiPageView(content, canedit=wp.may_revise(), showactions=showactions, alert=message).render()
   
    def POST_wikiPage(self, page="index"):
        return self.GET_wikiPage(page)
    
    def GET_wikiRevisions(self, page="index"):
        after = request.GET.get('l')
        if not c.is_mod and page in restricted_pages:
            abort(403)
        c.page = page
        try:
            if after:
                after=WikiRevision.get(after)
            wp = WikiPage.get(c.sr, page)
            if not wp.may_view():
                abort(403)
        except tdb_cassandra.NotFound:
                abort(404)
        revisions = [r for r in wp.get_revisions(after=after)]
        last=None
        if len(revisions) > 10:
            revisions = revisions[:-1]
            try:
                last=revisions[-2]._id
            except IndexError:
                pass
        return WikiRevisions(revisions, last).render()
   
    def POST_wikiRevisions(self, page="index"):
        return self.GET_wikiRevisions(page)
    
    def GET_wikiCreate(self, page="index"):
        if page.startswith(restricted_namespaces):
            abort(403)
        try:
            wp = WikiPage.get(c.sr, page)
        except tdb_cassandra.NotFound:
            WikiPage.create(c.sr, page)
            return self.redirect("%s/edit/%s" % (c.wiki_base_url, page))
        return self.GET_wikiPage(page)
    
    def POST_wikiCreate(self, page="index"):
        return self.GET_wikiCreate(page)
    
    def GET_wikiRevise(self, page="index"):
        message = None
        if page in restricted_pages:
            if not c.is_mod:
                abort(403)
            else:
                message = restricted_pages[page]
        c.page = page
        try:
            wp = WikiPage.get(c.sr, page)
        except tdb_cassandra.NotFound:
            abort(404)
        if not wp.may_revise():
            abort(403)
        try:
            previous = wp.revision
        except AttributeError:
            previous = None
        return WikiEdit(wp.content, previous, self.editconflict, alert=message).render()
    
    def POST_wikiRevise(self, page="index"):
        if not c.is_mod and page in restricted_pages:
            abort(403)
        try:
            wp = WikiPage.get(c.sr, page)
        except tdb_cassandra.NotFound:
            abort(404)
        if not wp.may_revise():
            abort(403)
        try:
            wp.revise(request.POST["content"], request.POST["previous"], c.user.name)
            if c.is_mod:
                description = "Page %s edited" % page
                ModAction.create(c.wiki_sr, c.user, 'wikirevise', description=description)
        except ConflictException:
            self.editconflict = True
            return self.GET_wikiRevise(page)
        return self.redirect("%s/%s" % (c.wiki_base_url, page))
    
    def GET_wikiSettings(self, page="index"):
        c.page = page
        try:
            wp = WikiPage.get(c.sr, page)
        except tdb_cassandra.NotFound:
            abort(404)
        if not c.is_mod:
            abort(403)
        settings = {'permlevel': int(wp.permlevel)}
        return WikiSettings(settings).render()
    
    def POST_wikiSettings(self, page="index"):
        try:
            wp = WikiPage.get(c.sr, page)
        except tdb_cassandra.NotFound:
            abort(404)
        if not c.is_mod:
            abort(403)
        oldpermlevel = wp.permlevel
        permlevel = request.POST["permlevel"]
        try:
            wp.change_permlevel(permlevel)
        except:
            abort(403)
        description = "Page: %s, Changed from %s to %s" % (page, oldpermlevel, permlevel)
        ModAction.create(c.wiki_sr, c.user, 'wikipermlevel', description=description)
        return self.GET_wikiSettings(page)
    
    def pre(self):
        RedditController.pre(self)
        frontpage = c.site.name == " reddit.com"
        c.wiki_sr = Subreddit._by_name(g.default_sr) if frontpage else c.site
        c.wiki_base_url = '/wiki' if frontpage else '/r/'+c.site.name+'/wiki'
        c.sr = c.wiki_sr.name
        c.is_mod = False
        self.editconflict = False
        if c.user_is_loggedin:
            c.is_mod = bool(c.wiki_sr.is_moderator(c.user))
        
