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

from datetime import datetime

from django.conf.urls import url
from django.utils.translation import ugettext as _
from pytz import utc
from tastypie.authentication import SessionAuthentication
from tastypie.authorization import DjangoAuthorization
from tastypie.bundle import Bundle
from tastypie.exceptions import Unauthorized
from tastypie.resources import ModelResource, Resource

from inboxen.helper.inbox import inbox_available, clean_tags, gen_inbox
from inboxen.models import Domain, Inbox, Tag
from queue.delete.tasks import delete_inbox

class InboxenAuth(DjangoAuthorization):
    """Authorisation for Inboxen"""
    def read_list(self, object_list, bundle):
        if not self.base_checks(bundle.request, object_list.model):
            raise Unauthorized(_("You're not logged in"))

        if hasattr(object_list.model, 'user'):
            return object_list.filter(user=bundle.request.user)
        elif hasattr(object_list.model, 'inbox'):
            return object_list.filter(inbox__user=bundle.request.user)
        else:
            return []

    def read_detail(self, object_list, bundle):
        if not self.base_checks(bundle.request, bundle.obj.__class__):
            raise Unauthorized(_("You're not logged in"))

        if hasattr(bundle.obj.__class__, 'user'):
            return bundle.obj.user == bundle.request.user
        elif hasattr(object_list.__class__, 'inbox'):
            return bundle.obj.inbox.user == bundle.request.user
        else:
            return False

    def create_list(self, object_list, bundle):
        if not self.base_checks(bundle.request, object_list.model):
            raise Unauthorized(_("You're not logged in"))

        # deadlox
        raise Unauthorized(_("Don't do dis"))

    def create_detail(self, object_list, bundle):
        if not self.base_checks(bundle.request, bundle.obj.__class__):
            raise Unauthorized(_("You're not logged in"))

        # for Inboxes
        if hasattr(bundle.obj.__class__, 'user'):
            return bundle.obj.user == bundle.request.user
        else:
            return False

    def update_list(self, object_list, bundle):
        if not self.base_checks(bundle.request, object_list.model):
            raise Unauthorized(_("You're not logged in"))

        return []

    def update_detail(self, object_list, bundle):
        if not self.base_checks(bundle.request, bundle.obj.__class__):
            raise Unauthorized(_("You're not logged in"))

        return False

    def delete_list(self, object_list, bundle):
        if not self.base_checks(bundle.request, object_list.model):
            raise Unauthorized(_("You're not logged in"))

        if hasattr(object_list.model, 'user'):
            return object_list.filter(user=bundle.request.user)
        else:
            return []

    def delete_detail(self, object_list, bundle):
        if not self.base_checks(bundle.request, bundle.obj.__class__):
            raise Unauthorized(_("You're not logged in"))

        if hasattr(bundle.obj.__class__, 'user'):
            return bundle.obj.user == bundle.request.user
        else:
            return False

class InboxesResource(ModelResource):
    """Handle Inbox related requests"""
    #TODO: make tags updatable as a child of this resource?

    def dehydrate(self, bundle):
        """Add and overwrite fields"""
        bundle.data['unread'] = bundle.obj.email_set.filter(read=False).count()

        inbox = "%s@%s" % (bundle.obj.inbox, bundle.obj.domain.domain)
        bundle.data['inbox'] = inbox

        tags = [tag.tag for tag in bundle.obj.tag_set.only("tag")]
        bundle.data['tags'] = tags

        return bundle

    def detail_uri_kwargs(self, bundle_or_obj):
        """Expose 'inbox@domain' as the PK"""
        kwargs = {}

        if isinstance(bundle_or_obj, Bundle):
            obj = bundle_or_obj.obj
        else:
            obj = bundle_or_obj

        kwargs['inbox'] = obj.inbox
        kwargs['domain__domain'] = obj.domain.domain

        return kwargs

    def obj_create(self, bundle, **kwargs):
        #TODO: allow choosing of domain

        domain = Domain.objects.only('id')[0]
        inbox = gen_inbox(5)

        new_inbox = Inbox(inbox=inbox, domain=domain, user=bundle.request.user, created=datetime.now(utc))
        new_inbox.save()

        tags = bundle.data.get('tags',[])
        for tag in tags:
            tag = Tag(tag=tag)
            tag.inbox = new_inbox
            tag.save()

        bundle.obj = new_inbox
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
        objects_to_delete = self.obj_get_list(bundle=bundle, **kwargs).only('id','user')
        deletable_objects = self.authorized_delete_list(objects_to_delete, bundle)

        for authed_obj in deletable_objects:
            authed_obj.deleted = True
            authed_obj.save()
            delete_inbox.delay(authed_obj)

    def prepend_urls(self):
        return [
            url(r"^(?P<resource_name>%s)/(?P<inbox>[a-zA-Z0-9\.]+)@(?P<domain__domain>[a-zA-Z0-9\.]+)/$" % self._meta.resource_name, self.wrap_view('dispatch_detail'), name="api_dispatch_detail"),
        ]

    def rollback(self, bundles):
        """Disabled"""
        pass

    class Meta:
        resource_name = 'inbox'
        queryset = Inbox.objects.filter(deleted=False)
        always_return_data = True
        list_allowed_methods = ['get', 'post', 'delete']
        detail_allowed_methods = ['get', 'delete']
        excludes = ['deleted', 'id', 'user']

        authentication = SessionAuthentication()
        authorization = InboxenAuth()

class EmailsResource(ModelResource):
    """Handle Email related requests"""
    #TODO: implement

    pass
