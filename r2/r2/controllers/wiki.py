from reddit_base import RedditController
from r2.lib.pages.wiki import *
from r2.lib.pages import *
from r2.models.subreddit import Subreddit
from r2.models.wiki import Wiki
from r2.lib.filters import safemarkdown
from pylons import c, request, g
import difflib
from r2.lib.db.queries import changed

class WikiController(RedditController):
    def get_request_var(self, name):
        ret = ""
        try:
            ret = request.GET[name]
        except:
            try:
                ret = request.POST[name]
            except:
                pass
        return ret
    
    def pre(self):
        RedditController.pre(self)
        self.wiki_sr = c.site.name if c.site.name != " reddit.com" else g.default_sr
        self.base_url = '/wiki' if c.site.name == " reddit.com" else '/r/'+c.site.name+'/wiki'
        self.sr = Subreddit._by_name(self.wiki_sr)
        self.messages = []
        try:
            self.messages.append(request.GET['message'])
        except:
            pass
        self.act = self.get_request_var('act')

    def getFullWikiName(self, wikiname):
        return "%s/%s" % (self.wiki_sr, wikiname)

    def GET_wiki(self, wikiname="index", edit_id = None):
        try:
            self.ver = int(edit_id)
        except:
            self.ver = 0
        wiki = self.sr.get_wiki(wikiname)
        edit = None
        if wiki:
            num_edits = wiki.edit_count
            if wiki.content:
                edit = wiki.content
        else:
            num_edits = -1
        history = []
        n = 0
        if wiki:
            for h in wiki.hist:
                if h is not None:
                    if not hasattr(h, 'hidden') or not h.hidden:
                        if h._id == self.ver:
                            edit = h
                            n = h.when
                        history.append((h.when, h._id))
        
        if self.ver == 0:
            self.messages.append("Viewing current version")
            try:
                page = wiki.content.content
            except:
                page = str()
        elif not n == 0:
            hd = difflib.HtmlDiff()
            self.messages.append("Viewing version: %s"  % str(n))
            t = hd.make_table(edit.content.split('\n'), wiki.content.content.split('\n'), fromdesc="Version %d" % self.ver, todesc="Current")
            page = edit.content
            self.messages.append(str(t))
        else:
            abort(404)
        
        f_wikiname = self.getFullWikiName(wikiname)

        content = WikiView(wikiname = f_wikiname, s_wikiname = wikiname, wiki_id = wiki._id, base_url = self.base_url, edit = edit, history = history, can_edit = c.user_is_loggedin and self.sr.can_submit(c.user) and self.ver is 0, messages = self.messages, num = num_edits, unedited_page_content = page, page_content = safemarkdown(page))
        return WikiPage(f_wikiname, content = content).render()

    def POST_edit(self, wiki_id):
        self.messages=["Cannot edit"]
        if self.act == 'hide':
            self.messages = ["cannit hide"]
        
        wiki = Wiki._by_id(wiki_id)
        
        if c.user_is_loggedin and self.sr.can_submit(c.user):
            try:
                diff = wiki.edit_count != int(request.POST['orig-page'])
                # We should also just silently fail if no changes were made
            except:
                diff = False
            message = ["Error, old version was not the same as yours\n"]
            if not diff: # We should attempt a merge, difflib cannot do that directly
                if wiki:
                    wiki.edit(c.user, request.POST['page'])
                    self.messages = ["Edited"]
                else:
                    self.sr.add_wiki(wikiname, request.POST['page'])
                    self.messages = ["Added"]
        self.sr = Subreddit._by_name(self.wiki_sr, _update = True)
        return self.redirect(request.POST['redirect']+"?message="+self.messages[0])
    
    def POST_hide(self, edit_id):
        edit = WikiEdit._by_id(edit_id)
        edit.hidden = True
        edit._commit()
        
