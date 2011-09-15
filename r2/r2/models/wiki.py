from printable import Printable
from r2.lib.db.thing import Thing
from r2.models.account import Account
from datetime import datetime
from pylons import c, request, g

class Wiki(Thing):
    _defaults = dict(content = None, name = str(), sr = None, edit_count = -1, hist = [])
    
    @classmethod
    def _by_name(cls, name, sr):
        w = cls._query(cls.c.name == name, cls.c.sr == sr, limit = 1)
        return list(w)[0]
    
    @classmethod
    def _by_id(cls, edit_id):
        e = cls._query(cls.c._id == edit_id, limit = 1)
        return list(e)[0]
    
    @classmethod
    def _new(cls, name, sr, text, account):
        w = Wiki(name = name, sr = sr._id)
        w._commit()
        w.content = WikiEdit._new(text, account, w)
        w._commit()
        return w
    
    def edit(self, account, text):
        new_hist = self.hist
        self.hist = []
        new_hist.append(self.content)
        self.hist = new_hist
        self.content = WikiEdit._new(text, account, self)
        self.edit_count += 1
        self._commit()

    def get_edit(edit_id, include_hidden):
        return
    
    def history_size(self):
        return len(self.hist)

class WikiEdit(Thing):
    _defaults = dict(content = str(), hidden = False, when = None, account = None, wiki = None)
    
    @classmethod
    def _by_id(cls, edit_id):
        e = cls._query(cls.c._id == edit_id, limit = 1)
        return list(e)[0]
    
    @classmethod
    def _new(cls, content, account, wiki):
        e = WikiEdit(content = content, account = account, wiki = wiki)
        e.when = datetime.now(g.tz)
        e._commit()
        return e
