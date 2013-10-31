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

import json

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.views.decorators.http import require_http_methods

from inboxen.models import Email, Inbox, Header
from website.views.error import permission_denied

@login_required
@require_http_methods(['GET', 'HEAD'])
def count(request, inbox=None, domain=None):
    """Count the number of unread messages in an inbox"""
    emails = grab_emails(request, inbox, domain)

    output = {'count': emails.filter(read=False).count()}

    return render_api(output)

@login_required
@require_http_methods(['GET', 'HEAD', 'DELETE'])
def emails(request, inbox=None, domain=None):
    """
    GET: Get a list of emails that have come in since last page load (or status=304 if none)
    HEAD: Find out if there are new messages (status=200 if yes, 304 if no)
    DELETE: Delete an email"""

    emails = grab_emails(request, inbox, domain)

    if request.method in ['GET','HEAD']:
        #check if-modified-since header
        since = None # some datetime object with tz info
        emails = emails.filter(recieved_date__gte=since)

        # HEAD responses have no body
        if request.method == 'HEAD':
            if emails.exist():
                return HttpResponse("", "application/json", 200)
            else:
                return HttpResponse("", "application/json", 304)

        # ... GET responses do
        elif request.method == 'GET':
            emails = emails.order_by("-recieved_date").defer('body')
            output = []
            for email in emails:
               row = {}

                row['id'] = email.eid
                row['read'] = email.read

                try:
                    row['subject'] = email.headers.get(name='subject')
                except Header.DoesNotExist:
                    row['subject'] = ""

                try:
                    row['form'] = email.headers.get(name='form')
                except Header.DoesNotExist:
                    row['form'] = ""

                output.append(row)

            return render_api(output, 200)

    elif request.method == 'DELETE':
        pass

def grab_emails(request, inbox, domain):
    #TODO: Move this in with the other helpers
    if inbox and domain:
        try:
            inbox = Inbox.objects.only('id').get(inbox=inbox, domain__domain=domain, deleted=False, user=request.user)
        except Inbox.DoesNotExist:
            return render_api({'error':"Permission denied"}, 403)

        emails = Email.objects.filter(inbox=inbox)

    else:
        emails = Email.objects.filter(user=request.user)

    return emails

def render_api(data, status=200):
    """Renders json and creates a HttpResponse object"""
    data = json.dumps(data)
    return HttpResponse(data, "application/json", status)
