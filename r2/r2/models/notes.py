from r2.lib.db import tdb_cassandra
from r2.models import Account, Printable

class ModerationNote(tdb_cassandra.UuidThing, Printable):
    _read_consistency_level = tdb_cassandra.CL.ONE
    _use_db = True
    _connection_pool = 'main'
    _str_props = ('sr_id36', 'account_id36', 'creator_id36',
                  'context', 'content')
    _defaults = {}

    @classmethod
    def get_notes(cls, sr, user, **kw):
        key = '%s_%s' % (sr._id36, user._id36)
        return ModerationNotesBySRAccount.query([key], **kw)

    def _on_create(self):
        self._on_commit()

    def _on_commit(self):
        ModerationNotesBySRAccount.add_object(self)

    @classmethod
    def create(cls, sr, account, content, creator=None, context=None):
        kw = dict(sr_id36=sr._id36, account_id36=account._id36)
        if creator:
            kw['creator_id36'] = creator._id36
        if context:
            kw['context'] = context
        note = cls(**kw)
        note._commit()
        return note

    @classmethod
    def add_props(cls, user, wrapped):
        creators = Account._byID36(set(w.creator_id36 for w in wrapped)) 
        for item in wrapped:
            item._spam = False
            item.reported = False
            item.creator = creators[creator.creator_id36]

class ModerationNotesByAccount(tdb_cassandra.DenormalizedView):
    _use_db = True
    _connection_pool = 'main'
    _compare_with = tdb_cassandra.TIME_UUID_TYPE
    _view_of = ModerationNote
    _read_consistency_level = tdb_cassandra.CL.ONE

    @classmethod
    def _rowkey(cls, note):
        return note.account_id36

class ModerationNotesBySRAccount(tdb_cassandra.DenormalizedView):
    _use_db = True
    _connection_pool = 'main'
    _compare_with = tdb_cassandra.TIME_UUID_TYPE
    _view_of = ModerationNote
    _read_consistency_level = tdb_cassandra.CL.ONE

    @classmethod
    def _rowkey(cls, note):
        return '%s_%s' % (note.sr_id36, note.account_id36)
