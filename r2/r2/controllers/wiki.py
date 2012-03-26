from pylons import request, g, c, Response
from reddit_base import RedditController
from r2.lib.utils import url_links
from r2.models.wiki import WikiPage, WikiRevision
from r2.models.subreddit import Subreddit
from r2.models.modaction import ModAction
from r2.models.builder import WikiRevisionBuilder
from r2.config.extensions import set_extension
from r2.lib.template_helpers import add_sr
from r2.lib.db import tdb_cassandra
from r2.models.listing import WikiRevisionListing
from r2.lib.merge import *
from r2.lib.pages.things import default_thing_wrapper
from r2.lib.pages import BoringPage
from r2.lib.pages.wiki import *
from reddit_base import base_listing
from r2.models import IDBuilder, LinkListing
from pylons.controllers.util import abort
from r2.lib.filters import safemarkdown
from validator.wiki import *
from pylons.i18n import _
from r2.lib.pages import PaneStack

import simplejson

page_descriptions = {'config/stylesheet':_("This page is the subreddit stylesheet, changes here apply to the subreddit css"),
                     'config/sidebar':_("The contents of this page appear on the subreddit sidebar")}

class WikiController(RedditController):
    @validate(pv = VWikiPageAndVersion(('page', 'v', 'v2'), restricted=False))
    def GET_wikiPage(self, pv):
        page, version, version2 = pv
        message = None
        if not page:
            return self.GET_wikiCreate(page=c.page, view=True)
        diffcontent = None
        if not version:
            content = page.content
            if c.is_mod and page.name in page_descriptions:
                message = page_descriptions[page.name]
        else:
            content = version.content
            message = _("Viewing revision %s") % version._id
            diffcontent = page.content
            difftitle = _("Current revision")
            if version2:
                diffcontent = version2.content
                difftitle = version2._id
        showactions = c.is_mod or (page.name not in special_pages)
        show_settings = False if page.name in special_pages else c.is_mod
        c.allow_styles = True
        if version:
            diffcontent = make_htmldiff(content, diffcontent, version._id, difftitle)
        return WikiPageView(content, canedit=may_revise(page), showactions=showactions, show_settings=show_settings, alert=message, v=version, diff=diffcontent).render()
    
    @validate(pv = VWikiPageAndVersion(('page', 'l'), restricted=False))
    def GET_wikiRevisions(self, pv, page):
        page, after = pv
        revisions = page.get_revisions(after=after, count=10)
        builder = WikiRevisionBuilder(revisions, skip=not c.is_mod, wrap=default_thing_wrapper())
        listing = WikiRevisionListing(builder)
        return WikiRevisions(listing.listing()).render()
    
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
    def GET_wikiRevise(self, page, message=None, **kw):
        previous = kw.get('previous', page._get('revision'))
        content = kw.get('content', page.content)
        if not message and page.name in page_descriptions:
            message = page_descriptions[page.name]
        return WikiEdit(content, previous, alert=message).render()
   
    def GET_wikiRecent(self):
        revisions = WikiRevision.get_recent(c.wiki_sr.name)
        builder = WikiRevisionBuilder(revisions, skip=not c.is_mod, wrap=default_thing_wrapper())
        listing = WikiRevisionListing(builder).listing()
        return WikiRecent(listing).render()
    
    @base_listing
    @validate(page = VWikiPage('page', restricted=True))
    def GET_wikiDiscussions(self, page, num, after, reverse, count):
        page_url = add_sr("%s/%s" % (c.wiki_base_url, page.name))
        links = url_links(page_url)
        builder = IDBuilder([ link._fullname for link in links ],
                            num = num, after = after, reverse = reverse,
                            count = count, skip = False)
        listing = LinkListing(builder).listing()
        return WikiDiscussions(listing).render()
    
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
        description = 'Page: %s, Changed from %s to %s' % (page.name, oldpermlevel, permlevel)
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

class WikiapiController(WikiController):
    @validate(page = VWikiPageRevise('page', restricted=True))
    def POST_wikiEdit(self, page):
        try:
            if page.name == 'config/stylesheet':
                report, parsed = c.wiki_sr.parse_css(request.POST['content'])
                if report.errors:
                    error_items = [x.message for x in sorted(report.errors)]
                    c.response = Response()
                    c.response.status_code = 415
                    c.response.content = simplejson.dumps({'special_errors': error_items})
                    return c.response
                c.wiki_sr.change_css(request.POST['content'], parsed, request.POST['previous'], reason=request.POST['reason'])
            else:
                page.revise(request.POST['content'], request.POST['previous'], c.user.name, reason=request.POST['reason'])
                if c.is_mod:
                    description = 'Page %s edited' % page.name
                    ModAction.create(c.wiki_sr, c.user, 'wikirevise', description=description)
        except ConflictException as e:
            c.response = Response()
            c.response.status_code = 409
            c.response.content = simplejson.dumps({'newcontent': e.new, 'newrevision': page.revision, 'diffcontent': e.htmldiff})
            return c.response
        return simplejson.dumps({'success': True})
    
    @validate(pv = VWikiPageAndVersion(('page', 'revision')))
    def POST_wikiRevisionHide(self, pv, page, revision):
        if not c.is_mod:
            abort(403)
        page, revision = pv
        return simplejson.dumps({'status': revision.toggle_hide()})
    
    def pre(self):
        WikiController.pre(self)
        set_extension(request.environ, 'json')
