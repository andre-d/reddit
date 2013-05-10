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

from r2.lib.media import upload_media

class BadImage(Exception):
    def __init__(self, error = None):
        self.error = error

def legacy_s3_url(url, site):
    if isinstance(url, int): # legacy url, needs to be generated
        bucket = g.s3_old_thumb_bucket
        baseurl = "http://%s" % (bucket)
        if g.s3_media_direct:
            baseurl = "http://%s/%s" % (s3_direct_url, bucket)
        url = "%s/%s_%d.png"\
                % (baseurl, site._fullname, url)
    return url

def url_for_image(name, site):
    url = site.images[name]
    url = legacy_s3_url(url, site)
    return url

def save_sr_image(sr, data, suffix = '.png'):
    try:
        return upload_media(data, file_type = suffix)
    except IOError as e:
        raise BadImage(e)
