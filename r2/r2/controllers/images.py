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

from pylons.i18n import _
from pylons import c, g

from r2.controllers.reddit_base import RedditController
from r2.controllers.oauth2 import OAuth2ResourceController, require_oauth2_scope
from r2.lib.validator import (
    VCssName,
    VImageType,
    VInt,
    VLength,
    VModhash,
    VSrModerator,
    validate,
    validatedForm,
)
from r2.controllers.api_docs import api_doc, api_section
from r2.models.modaction import ModAction
from r2.models.images import BadImage, save_sr_image
from r2.lib.scraper import str_to_image
from r2.lib.pages import UploadedImage
from r2.lib import cssfilter

class ImagesController(RedditController, OAuth2ResourceController):
    def GET_upload_sr_img(self, *a, **kw):
        """
        Completely unnecessary method which exists because safari can
        be dumb too.  On page reload after an image has been posted in
        safari, the iframe to which the request posted preserves the
        URL of the POST, and safari attempts to execute a GET against
        it.  The iframe is hidden, so what it returns is completely
        irrelevant.
        """
        return "nothing to see here."

    @require_oauth2_scope("modconfig")
    @validate(VSrModerator(perms='config'),
              VModhash(),
              file = VLength('file', max_length=1024*500),
              name = VCssName("name"),
              img_type = VImageType('img_type'),
              form_id = VLength('formid', max_length = 100), 
              header = VInt('header', max=1, min=0))
    @api_doc(api_section.subreddits)
    def POST_upload_sr_img(self, file, header, name, form_id, img_type):
        """
        Called on /about/stylesheet when an image needs to be replaced
        or uploaded, as well as on /about/edit for updating the
        header.  Unlike every other POST in this controller, this
        method does not get called with Ajax but rather is from the
        original form POSTing to a hidden iFrame.  Unfortunately, this
        means the response needs to generate an page with a script tag
        to fire the requisite updates to the parent document, and,
        more importantly, that we can't use our normal toolkit for
        passing those responses back.

        The result of this function is a rendered UploadedImage()
        object in charge of firing the completedUploadImage() call in
        JS.
        """

        # default error list (default values will reset the errors in
        # the response if no error is raised)
        errors = dict(BAD_CSS_NAME = "", IMAGE_ERROR = "")
        add_image_to_sr = False
        size = None
        
        if not header:
            add_image_to_sr = True
            if not name:
                # error if the name wasn't specified and the image was not for a sponsored link or header
                # this may also fail if a sponsored image was added and the user is not an admin
                errors['BAD_CSS_NAME'] = _("bad image name")
        
        if c.site.images and add_image_to_sr:
            if c.site.get_num_images() >= g.max_sr_images:
                errors['IMAGE_ERROR'] = _("too many images (you only get %d)") % g.max_sr_images

        if any(errors.values()):
            return UploadedImage("", "", "", errors=errors, form_id=form_id).render()
        else:
            try:
                new_url = save_sr_image(c.site, file, suffix ='.' + img_type)
            except BadImage:
                errors['IMAGE_ERROR'] = _("Invalid image or general image error")
                return UploadedImage("", "", "", errors=errors, form_id=form_id).render()
            size = str_to_image(file).size
            if header:
                c.site.header = new_url
                c.site.header_size = size
            if add_image_to_sr:
                c.site.add_image(name, url = new_url)
            c.site._commit()

            if header:
                kw = dict(details='upload_image_header')
            else:
                kw = dict(details='upload_image', description=name)
            ModAction.create(c.site, c.user, action='editsettings', **kw)

            return UploadedImage(_('saved'), new_url, name, 
                                 errors=errors, form_id=form_id).render()

    @require_oauth2_scope("modconfig")
    @validatedForm(VSrModerator(perms='config'),
                   VModhash(),
                   name = VCssName('img_name'))
    @api_doc(api_section.subreddits)
    def POST_delete_sr_img(self, form, jquery, name):
        """
        Called called upon requested delete on /about/stylesheet.
        Updates the site's image list, and causes the <li> which wraps
        the image to be hidden.
        """
        # just in case we need to kill this feature from XSS
        if g.css_killswitch:
            return self.abort(403,'forbidden')
        c.site.del_image(name)
        c.site._commit()
        ModAction.create(c.site, c.user, action='editsettings', 
                         details='del_image', description=name)

    @require_oauth2_scope("modconfig")
    @validatedForm(VSrModerator(perms='config'),
                   VModhash())
    @api_doc(api_section.subreddits)
    def POST_delete_sr_header(self, form, jquery):
        """
        Called when the user request that the header on a sr be reset.
        """
        # just in case we need to kill this feature from XSS
        if g.css_killswitch:
            return self.abort(403,'forbidden')
        if c.site.header:
            c.site.header = None
            c.site.header_size = None
            c.site._commit()
            ModAction.create(c.site, c.user, action='editsettings', 
                             details='del_header')

        # hide the button which started this
        form.find('.delete-img').hide()
        # hide the preview box
        form.find('.img-preview-container').hide()
        # reset the status boxes
        form.set_html('.img-status', _("deleted"))
