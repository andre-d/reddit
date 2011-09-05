from printable import Printable
from r2.lib.db.thing import Thing

class Wiki(Thing, Printable):
    _defaults = dict(content = str(), name = str(), sr = None, edit_count = -1, hist = [])
    
    @classmethod
    def _by_name(cls, name, sr):
        w = cls._query(cls.c.name == name, cls.c.sr == sr, limit = 1)
        return list(w)[0]
        
    @classmethod
    def _new(cls, name, sr_id, text):
        w = Wiki(content = text, name = name, sr = sr_id)
        w._commit()
        return w
    
    def edit(self, text):
        new_hist = self.hist
        self.hist = []
        new_hist.append(self.content)
        self.hist = new_hist
        self.content = text
        self._commit()
    
    def history_size(self):
        return len(self.hist)
