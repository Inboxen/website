##
#    This file is part of Inboxen.
#
#    Inboxen is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Inboxen is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Inboxen.  If not, see <http://www.gnu.org/licenses/>.
##

"""
Parts of this file have been taken from TastyPie[0], and thus the following terms
apply to them:

    Copyright (c) 2010, Daniel Lindsley
    All rights reserved.

    Redistribution and use in source and binary forms, with or without
    modification, are permitted provided that the following conditions are met:
        * Redistributions of source code must retain the above copyright
          notice, this list of conditions and the following disclaimer.
        * Redistributions in binary form must reproduce the above copyright
          notice, this list of conditions and the following disclaimer in the
          documentation and/or other materials provided with the distribution.
        * Neither the name of the tastypie nor the
          names of its contributors may be used to endorse or promote products
          derived from this software without specific prior written permission.

    THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
    ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
    WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
    DISCLAIMED. IN NO EVENT SHALL tastypie BE LIABLE FOR ANY
    DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
    (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
    LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
    ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
    (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
    SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

[0] https://github.com/toastdriven/django-tastypie
"""

from django.utils.translation import ugettext as _
from tastypie.authentication import SessionAuthentication
from tastypie.authorization import DjangoAuthorization
from tastypie.resources import ModelResource, Resource

from inboxen.models import Inbox
from queue.delete.tasks import delete_inbox

class InboxesResource(ModelResource):
    """Handle Inbox related requests"""
    #TODO: make tags updatable as a child of this resource?
    #TODO: allow creation of new Inbox

    def dehydrate(self, bundle):
        bundle.data['unread'] = bundle.obj.email_set.filter(read=False).count()
        return bundle

    def obj_delete(self, bundle, **kwargs):
        """Delete object, partly taken from TastyPie source"""
        if not hasattr(bundle.obj, 'delete'):
            try:
                bundle.obj = self.obj_get(bundle=bundle, **kwargs)
            except Inbox.DoesNotExist:
                raise NotFound(_("Inbox not found"))

        self.authorized_delete_detail(self.get_object_list(bundle.request), bundle)

        bundle.obj.deleted = True
        bundle.obj.save()
        delete_inbox.delay(bundle.obj)

    def obj_delete_list(self, bundle, **kwargs):
        """Delete list of objects, partly taken from TastyPie source"""
        objects_to_delete = self.obj_get_list(bundle=bundle, **kwargs)
        deletable_objects = self.authorized_delete_list(objects_to_delete, bundle)

        for authed_obj in deletable_objects:
            authed_obj.deleted = True
            authed_obj.save()
            delete_inbox.delay(authed_obj)

    class Meta:
        resource_name = 'inbox'
        queryset = Inbox.objects.filter(deleted=False)
        list_allowed_methods = ['get', 'delete']
        exclude =['deleted', 'user']

        authentication = SessionAuthentication()
        authorization = InboxenAuth()

class EmailsResource(ModelResource):
    """Handle Email related requests"""
    #TODO: implement

    pass

class InboxenAuth(DjangoAuthorization):
    """Do Inboxen style user checking"""
    #TODO: implement

    pass
