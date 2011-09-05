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

    def getFullWikiName(self,wikiname):
        return "%s/%s" % (self.wiki_sr,wikiname)

    def GET_wiki(self, wikiname="index", message=""):
        wiki = self.sr.get_wiki(wikiname)
        if wiki:
            num = wiki.history_size()
            num_edits = wiki.edit_count
            page = wiki.content
        else:
            num = num_edits = -1
            page = str()
        history = []
        if num > 0:
            for i in range(1,num+1):
                history.append(i)
        try:
            ver = int(request.GET['ver'])
        except:
            ver = 0

        diff = False

        if ver <= 0:
            message += "Viewing current version"
        elif ver > num:
            abort(404)
        else:
            message += "Viewing version: %d<br/>"%ver # These should be in a list instead of one long string with html line breaks
            diff = True
        
        f_wikiname = self.getFullWikiName(wikiname)
        try:
            act = request.GET['act']
        except:
            act = ""

        if diff:
            hd = difflib.HtmlDiff()
            t=hd.make_table(wiki.hist[ver-1].split('\n'), page.split('\n'), fromdesc="Version %d"%ver, todesc="Current")
            page = wiki.hist[ver-1]
            message+="<br/>"+t

        if act == "get":
            return safemarkdown(page) # Should be inside json and not filtered
        else:
            content = WikiView(wikiname = f_wikiname, history = history, can_edit = c.user_is_loggedin and self.sr.can_submit(c.user) and (not diff), message = message, num = num_edits, unedited_page_content = page, page_content = safemarkdown(page))
            return WikiPage(f_wikiname, content = content).render()

    def POST_wiki(self, wikiname = "index"):
        message="Cannot edit\n"
       # try:
        wiki = self.sr.get_wiki(wikiname)
        #except:
         #   wiki = None
        if c.user_is_loggedin and self.sr.can_submit(c.user):
            try:
                diff = wiki.edit_count != int(request.POST['orig-page'])
                # We should also just silently fail if no changes were made
            except:
                diff = False
            message="Error, old version was not the same as yours\n"
            if not diff: # We should attempt a merge, difflib cannot do that directly
                if wiki:
                    wiki.edit(request.POST['page'])
                    message="Edited\n"
                else:
                    self.sr.add_wiki(wikiname, request.POST['page'])
                    message="Added\n"
                self.sr = Subreddit._by_name(self.wiki_sr, _update = True)
                changed(self.sr)
        return self.GET_wiki(wikiname, message=message+"<br/>")
