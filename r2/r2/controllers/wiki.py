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
    def pre(self):
        RedditController.pre(self)
        self.wiki_sr = c.site.name if c.site.name != " reddit.com" else g.default_sr
        self.sr = Subreddit._by_name(self.wiki_sr)
        self.messages = []
        try:
            self.act = request.GET['act']
        except:
            self.act = str()
        try:
            self.ver = int(request.GET['ver'])
        except:
            self.ver = 0

    def getFullWikiName(self, wikiname):
        return "%s/%s" % (self.wiki_sr, wikiname)

    def GET_wiki(self, wikiname="index"):
        wiki = self.sr.get_wiki(wikiname)
        edit = None
        if wiki:
            num_edits = wiki.edit_count
            if wiki.content:
                edit = wiki.content
        else:
            num_edits = -1
        history = []
        try:
            ver = int(request.GET['ver'])
        except:
            ver = 0
        n = 0
        if wiki:
            for h in wiki.hist:
                if not hasattr(h, 'hidden') or not h.hidden:
                    if h._id == ver:
                        edit = h
                        n = h.when
                    history.append((h.when, h._id))
        
        if ver == 0:
            self.messages.append("Viewing current version")
            try:
                page = wiki.content.content
            except:
                page = str()
        elif not n == 0:
            hd = difflib.HtmlDiff()
            self.messages.append("Viewing version: %s"  % str(n))
            t = hd.make_table(edit.content.split('\n'), wiki.content.content.split('\n'), fromdesc="Version %d" % ver, todesc="Current")
            page = edit.content
            self.messages.append(str(t))
        else:
            abort(404)
        
        f_wikiname = self.getFullWikiName(wikiname)

        if self.act == 'get':
            return safemarkdown(page) # Should be inside json and not filtered

        content = WikiView(wikiname = f_wikiname, edit = edit, history = history, can_edit = c.user_is_loggedin and self.sr.can_submit(c.user) and ver is 0, messages = self.messages, num = num_edits, unedited_page_content = page, page_content = safemarkdown(page))
        return WikiPage(f_wikiname, content = content).render()

    def POST_wiki(self, wikiname = "index"):
        self.messages=["Cannot edit"]
        if self.act == 'hide':
            self.messages = ["cannit hide"]
        
        try:
            wiki = self.sr.get_wiki(wikiname)
        except:
            wiki = None
        
        if c.user_is_loggedin and self.sr.can_submit(c.user):
            if self.act == "hide":
                w = wiki.hist[ver-1]
                w.hidden = True
                w._commit()
            else:
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
        return self.GET_wiki(wikiname)
