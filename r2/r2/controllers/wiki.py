from pylons import request, g, c, Response
from pylons.controllers.util import redirect_to
from reddit_base import RedditController
from r2.lib.utils import url_links
from reddit_base import paginated_listing
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
from r2.models import IDBuilder, LinkListing, DefaultSR
from pylons.controllers.util import abort
from validator.wiki import *
from validator.validator import VInt, VExistingUname
from pylons.i18n import _
from r2.lib.pages import PaneStack
from r2.lib.utils import timesince

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
            message = _("Viewing revision from %s") % timesince(version.date)
            diffcontent = page.content
            difftitle = _("Current revision")
            if version2:
                message = _("Comparing revisions from %s ago and %s ago") % (timesince(version.date), timesince(version2.date))
                diffcontent = version2.content
                difftitle = version2._id
                content = ""
            else:
                message = _("Viewing revision from %s") % timesince(version.date)
                content = version.content
        c.allow_styles = True
        if version:
            diffcontent = make_htmldiff(content, diffcontent, version._id, difftitle)
        return WikiPageView(content, alert=message, v=version, diff=diffcontent).render()
    
    @paginated_listing(max_page_size=100, backend='cassandra')
    @validate(page = VWikiPage(('page'), restricted=False))
    def GET_wikiRevisions(self, num, after, reverse, count, page):
        revisions = page.get_revisions()
        builder = WikiRevisionBuilder(revisions, num=num, reverse=reverse, count=count, after=after, skip=not c.is_mod, wrap=default_thing_wrapper())
        listing = WikiRevisionListing(builder).listing()
        return WikiRevisions(listing).render()
    
    @validate(may_create = VWikiPageCreate('page'))
    def GET_wikiCreate(self, may_create, page, view=False):
        if c.error:
            return BoringPage(_("Wiki error"), infotext=c.error).render()
        if view:
            return WikiNotFound().render()
        if may_create:
            WikiPage.create(c.site.name, page)
            return self.redirect('%s/edit/%s' % (c.wiki_base_url, page))
        return self.GET_wikiPage(page=page)
    
    @validate(page = VWikiPageRevise('page', restricted=True))
    def GET_wikiRevise(self, page, message=None, **kw):
        page = page[0]
        previous = kw.get('previous', page._get('revision'))
        content = kw.get('content', page.content)
        if not message and page.name in page_descriptions:
            message = page_descriptions[page.name]
        return WikiEdit(content, previous, alert=message).render()
    
    @paginated_listing(max_page_size=100, backend='cassandra')
    def GET_wikiRecent(self, num, after, reverse, count):
        revisions = WikiRevision.get_recent(c.site.name)
        builder = WikiRevisionBuilder(revisions,  num=num, reverse=reverse, count=count, after=after, skip=not c.is_mod, wrap=default_thing_wrapper())
        listing = WikiRevisionListing(builder).listing()
        return WikiRecent(listing).render()
    
    def GET_wikiListing(self):
        pages = WikiPage.get_listing(c.site.name)
        return WikiListing(pages).render()
    
    def GET_wiki_redirect(self, page):
        return redirect_to(str("%s/%s" % (c.wiki_base_url, page)), _code=301)
    
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
        mayedit = page.get_editors()
        return WikiSettings(settings, mayedit).render()
    
    @validate(page = VWikiPage('page', restricted=True, modonly=True),\
              permlevel = VInt('permlevel'))
    def POST_wikiSettings(self, page, permlevel):
        oldpermlevel = page.permlevel
        try:
            page.change_permlevel(permlevel)
        except ValueError:
            abort(403)
        description = 'Page: %s, Changed from %s to %s' % (page.name, oldpermlevel, permlevel)
        ModAction.create(c.site, c.user, 'wikipermlevel', description=description)
        return self.GET_wikiSettings(page=page.name)
    
    def pre(self):
        RedditController.pre(self)
        if not c.site._should_wiki:
            abort(404) # /r/mod for an example
        frontpage = isinstance(c.site, DefaultSR)
        c.wiki_base_url = '/wiki' if frontpage else '/r/%s/wiki' % c.site.name
        c.wiki_id = g.default_sr if frontpage else c.site.name
        c.is_mod = False
        c.page = None
        self.editconflict = False
        if c.user_is_loggedin:
            c.is_mod = c.site.is_moderator(c.user)
        c.wikidisabled = False
        mode = c.site.wikimode
        if not mode or mode == 'disabled':
            if not c.is_mod:
                abort(403)
            else:
                c.wikidisabled = True

class WikiApiController(WikiController):
    @validate(pageandprevious = VWikiPageRevise(('page', 'previous'), restricted=True))
    def POST_wikiEdit(self, pageandprevious):
        page, previous = pageandprevious
        previous = previous._id if previous else None
        try:
            if page.name == 'config/stylesheet':
                report, parsed = c.site.parse_css(request.POST['content'])
                if report.errors:
                    error_items = [x.message for x in sorted(report.errors)]
                    c.response = Response()
                    c.response.status_code = 415
                    c.response.content = simplejson.dumps({'special_errors': error_items})
                    return c.response
                c.site.change_css(request.POST['content'], parsed, previous, reason=request.POST['reason'])
            else:
                page.revise(request.POST['content'], previous, c.user.name, reason=request.POST['reason'])
            
                if c.is_mod:
                    description = 'Page %s edited' % page.name
                    ModAction.create(c.site, c.user, 'wikirevise', description=description)
        except ConflictException as e:
            c.response = Response()
            c.response.status_code = 409
            c.response.content = simplejson.dumps({'newcontent': e.new, 'newrevision': page.revision, 'diffcontent': e.htmldiff})
            return c.response
        return simplejson.dumps({'success': True})
    
    @validate(page = VWikiPage('page'), user = VExistingUname('user'))
    def POST_wikiAllowEditor(self, act, page, user):
        if not page:
            abort(404)
        if not c.is_mod:
            abort(403)
        if act == 'del':
            page.remove_editor(c.user)
        else:
            if not user:
                abort(404)
            try:
                page.add_editor(user.name)
            except ValueError:
                abort(403)
        return simplejson.dumps({'success': True})
    
    @validate(pv = VWikiPageAndVersion(('page', 'revision')))
    def POST_wikiRevisionHide(self, pv, page, revision):
        if not c.is_mod:
            abort(403)
        page, revision = pv
        return simplejson.dumps({'status': revision.toggle_hide()})
   
    @validate(pv = VWikiPageAndVersion(('page', 'revision')))
    def POST_wikiRevisionRevert(self, pv, page, revision):
        if not c.is_mod:
            abort(403)
        page, revision = pv
        content = revision.content
        author = revision._get('author')
        reason = _("Reverted back %s") % timesince(revision.date)
        if page.name == 'config/stylesheet':
            report, parsed = c.site.parse_css(content)
            if report.errors:
                abort(403)
            c.site.change_css(content, parsed, prev=None, reason=reason, force=True)
        else:
            page.revise(content, author=author, reason=reason, force=True)
        return simplejson.dumps({'success': True})
    
    def pre(self):
        WikiController.pre(self)
        set_extension(request.environ, 'json')
