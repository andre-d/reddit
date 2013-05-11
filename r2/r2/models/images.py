# The contents of this file are subject to the Common Public Attribution
# License Version 1.0. (the "License"); you may not use this file except in
# compliance with the License. You may obtain a copy of the License at
# http://code.reddit.com/LICENSE. The License is based on the Mozilla Public
# License Version 1.1, but Sections 14 and 15 have been added to cover use of
# software over a computer network and provide for limited attribution for the
# Original Developer. In addition, Exhibit A has been modified to be consistent
# with Exhibit B.
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License for
# the specific language governing rights and limitations under the License.
#
# The Original Code is reddit.
#
# The Original Developer is the Initial Developer.  The Initial Developer of
# the Original Code is reddit Inc.
#
# All portions of the code written by reddit are Copyright (c) 2006-2013 reddit
# Inc. All Rights Reserved.
###############################################################################

import json

from r2.lib.db import tdb_cassandra

class BadImage(Exception):
    def __init__(self, error = None):
        self.error = error

IMAGE_ID_SEP = '\t'

def url_for_image(name, owner):
    return ImagesByOwner.get(owner, name).url

class Image(object):
    _attrs = ['owner', 'name', 'storageurl']
    
    def __init__(self, owner=None, name=None, storageurl=None):
        self.owner = owner
        self.name = name
        self.storageurl = storageurl
    
    @property
    def url(self):
        return self.storageurl
    
    @property
    def _id(self):
        return self.name
    
    @classmethod
    def new(cls, owner, data, name, suffix = '.png'):
        from r2.lib.media import upload_media
        try:
            owner = owner._fullname if owner else None
            image = cls(owner, name, upload_media(data, file_type = suffix))
            return image
        except IOError as e:
            raise BadImage(e)

class GenericDenormalizedView(tdb_cassandra.DenormalizedView):
    @classmethod
    def _thing_dumper(cls, thing):
        props = {}
        for prop in cls._view_of._attrs:
            props[prop] = getattr(thing, prop, None)
        return json.dumps(props)
    
    @classmethod
    def _byID(cls, row, id):
        dump = cls._cf.get(row, columns=[id]).get(id, None)
        if dump == None:
            return None
        return cls._thing_loader(id, dump)
    
    @classmethod
    def _thing_loader(cls, _id, dump):
        serialized_props = json.loads(dump)
        new = cls._view_of()
        for prop in cls._view_of._attrs:
            value = serialized_props.get(prop, None)
            setattr(new, prop, value)
        return new

class ImagesByOwner(GenericDenormalizedView):
    
    _use_db = True
    _connection_pool = 'main'
    _view_of = Image
    
    @classmethod
    def delete(cls, owner, name):
        cls._remove(owner._fullname, [name])
    
    @classmethod
    def delete_object(cls, image):
        cls._remove(owner._fullname, [image.name])
    
    @classmethod
    def get(cls, owner, name):
        return cls._byID(owner._fullname, name)
    
    @classmethod
    def getall(cls, owner):
        return cls.query([owner._fullname])
    
    @classmethod
    def _rowkey(cls, image):
        return image.owner

