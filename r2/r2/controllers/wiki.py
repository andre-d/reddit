from pylons import request, g, c, Response
from pylons.controllers.util import redirect_to
from reddit_base import RedditController
from r2.lib.utils import url_links
from reddit_base import paginated_listing
from r2.models.wiki import WikiPage, WikiRevision, ContentLengthError
from r2.models.subreddit import Subreddit
from r2.models.modaction import ModAction
from r2.models.builder import WikiRevisionBuilder, WikiRecentRevisionBuilder
from r2.config.extensions import set_extension
from r2.lib.template_helpers import add_sr
from r2.lib.db import tdb_cassandra
from r2.controllers.errors import errors
from r2.models.listing import WikiRevisionListing
from r2.lib.pages.things import default_thing_wrapper
from r2.lib.pages import BoringPage
from reddit_base import base_listing
from r2.models import IDBuilder, LinkListing, DefaultSR
from validator.validator import VInt, VExistingUname, VRatelimit
from pylons.i18n import _
from r2.lib.pages import PaneStack
from r2.lib.utils import timesince

# TODO: No import *
from r2.lib.merge import *
from validator.wiki import *
from r2.lib.pages.wiki import *

page_descriptions = {'config/stylesheet':_("This page is the subreddit stylesheet, changes here apply to the subreddit css"),
                     'config/sidebar':_("The contents of this page appear on the subreddit sidebar")}

wiki_modactions = {'config/sidebar':"Updated subreddit sidebar"}

WIKI_EDIT_RATELIMIT_SECONDS = g.wiki_edit_ratelimit_seconds

class WikiController(RedditController):
    @validate(pv = VWikiPageAndVersion(('page', 'v', 'v2'), restricted=False))
    def GET_wikiPage(self, pv):
        page, version, version2 = pv
        message = None
        
        if not page:
            return self.GET_wikiCreate(page=c.page, view=True)
        
        kw = {}
        
        if version:
            edit_by = version.author
            edit_date = version.date
        else:
            edit_by = page._get('edit_by')
            edit_date = page._get('edit_date')
        
        if edit_by:
            kw['edit_by'] = edit_by
        if edit_date:
            kw['edit_date'] = edit_date
        
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
                content = ''
            else:
                message = _("Viewing revision from %s") % timesince(version.date)
                content = version.content
        c.allow_styles = True
        if version:
            diffcontent = make_htmldiff(content, diffcontent, version._id, difftitle)
        return WikiPageView(content, alert=message, v=version, diff=diffcontent, **kw).render()
    
    @paginated_listing(max_page_size=100, backend='cassandra')
    @validate(page = VWikiPage(('page'), restricted=False))
    def GET_wikiRevisions(self, num, after, reverse, count, page):
        revisions = page.get_revisions()
        builder = WikiRevisionBuilder(revisions, num=num, reverse=reverse, count=count, after=after, skip=not c.is_mod, wrap=default_thing_wrapper())
        listing = WikiRevisionListing(builder).listing()
        return WikiRevisions(listing).render()
    
    @validate(may_create = VWikiPageCreate('page'))
    def GET_wikiCreate(self, may_create, page, view=False):
        api = c.extension == 'json'
        if c.error or api:
            if api:
                if c.error:
                    self.handle_error(403, **c.error)
                else:
                    self.handle_error(404, 'PAGE_NOT_FOUND', may_create=may_create)
            error = ''
            if c.error['reason'] == 'PAGE_NAME_LENGTH':
                error = _("This wiki cannot handle page names of that magnitude!  Please select a page name shorter than %d characters") % c.error['max_length']
            elif c.error['reason'] == 'PAGE_CREATED_ELSEWHERE':
                error = _("This page is a special page, please go into the subreddit settings and save the field once to create this special page")
            elif c.error['reason'] == 'PAGE_NAME_MAX_SEPERATORS':
                error = _('A max of %d separators "/" are allowed in a wiki page name.') % c.error['max_seperators']
            return BoringPage(_("Wiki error"), infotext=error).render()
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
        builder = WikiRecentRevisionBuilder(revisions,  num=num, reverse=reverse, count=count, after=after, skip=not c.is_mod, wrap=default_thing_wrapper())
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
        settings = {'permlevel': page._get('permlevel', 0)}
        mayedit = page.get_editors()
        return WikiSettings(settings, mayedit, show_settings=not page.special).render()
    
    @validate(page = VWikiPage('page', restricted=True, modonly=True),\
              permlevel = VInt('permlevel'))
    def POST_wikiSettings(self, page, permlevel):
        oldpermlevel = page.permlevel
        try:
            page.change_permlevel(permlevel)
        except ValueError:
            self.handle_error(403, 'INVALID_PERMLEVEL')
        description = 'Page: %s, Changed from %s to %s' % (page.name, oldpermlevel, permlevel)
        ModAction.create(c.site, c.user, 'wikipermlevel', description=description)
        return self.GET_wikiSettings(page=page.name)
    
    def handle_error(self, code, error=None, **kw):
        jsonAbort(code, error, **kw)
    
    def pre(self):
        RedditController.pre(self)
        if not c.site._should_wiki:
            self.handle_error(404, 'NOT_WIKIABLE') # /r/mod for an example
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
                self.handle_error(403, 'WIKI_DISABLED')
            else:
                c.wikidisabled = True

class WikiApiController(WikiController):
    @validate(VRatelimit(rate_user = True, rate_ip = True, prefix = "rate_wiki_"),
              pageandprevious = VWikiPageRevise(('page', 'previous'), restricted=True))
    def POST_wikiEdit(self, pageandprevious):
        if (errors.RATELIMIT, 'ratelimit') in c.errors:
            self.handle_error(429, 'WIKI_EDIT_RATELIMIT')
        page, previous = pageandprevious
        previous = previous._id if previous else None
        try:
            if page.name == 'config/stylesheet':
                report, parsed = c.site.parse_css(request.POST['content'], verify=False)
                if report is None: # g.css_killswitch
                    self.handle_error(403, 'STYLESHEET_EDIT_DENIED')
                if report.errors:
                    error_items = [x.message for x in sorted(report.errors)]
                    self.handle_error(415, 'SPECIAL_ERRORS', special_errors=error_items)
                c.site.change_css(request.POST['content'], parsed, previous, reason=request.POST['reason'])
            else:
                try:
                    page.revise(request.POST['content'], previous, c.user.name, reason=request.POST['reason'])
                except ContentLengthError as e:
                    self.handle_error(403, 'CONTENT_LENGTH_ERROR', max_length = e.max_length)
                if page.special or c.is_mod:
                    description = wiki_modactions.get(page.name, 'Page %s edited' % page.name)
                    ModAction.create(c.site, c.user, 'wikirevise', details=description)
        except ConflictException as e:
            self.handle_error(409, 'EDIT_CONFLICT', newcontent=e.new, newrevision=page.revision, diffcontent=e.htmldiff)
        if not c.is_mod:
            VRatelimit.ratelimit(rate_user = True, rate_ip = True, prefix = "rate_wiki_", seconds=WIKI_EDIT_RATELIMIT_SECONDS)
        return simplejson.dumps({})
    
    @validate(page = VWikiPage('page'), user = VExistingUname('user'))
    def POST_wikiAllowEditor(self, act, page, user):
        if not page:
            self.handle_error(404, 'UNKNOWN_PAGE')
        if not c.is_mod:
            self.handle_error(403, 'MOD_REQUIRED')
        if act == 'del':
            page.remove_editor(c.user)
        else:
            if not user:
                self.handle_error(404, 'UNKOWN_USER')
            page.add_editor(user.name)
        return simplejson.dumps({})
    
    @validate(pv = VWikiPageAndVersion(('page', 'revision')))
    def POST_wikiRevisionHide(self, pv, page, revision):
        if not c.is_mod:
            self.handle_error(403, 'MOD_REQUIRED')
        page, revision = pv
        return simplejson.dumps({'status': revision.toggle_hide()})
   
    @validate(pv = VWikiPageAndVersion(('page', 'revision')))
    def POST_wikiRevisionRevert(self, pv, page, revision):
        if not c.is_mod:
            self.handle_error(403, 'MOD_REQUIRED')
        page, revision = pv
        content = revision.content
        author = revision._get('author')
        reason = _("Reverted back %s") % timesince(revision.date)
        if page.name == 'config/stylesheet':
            report, parsed = c.site.parse_css(content)
            if report.errors:
                self.handle_error(403, 'INVALID_CSS')
            c.site.change_css(content, parsed, prev=None, reason=reason, force=True)
        else:
            try:
                page.revise(content, author=author, reason=reason, force=True)
            except ContentLengthError as e:
                self.handle_error(403, 'CONTENT_LENGTH_ERROR', e.max_length)
        return simplejson.dumps({})
    
    def pre(self):
        WikiController.pre(self)
        set_extension(request.environ, 'json')
