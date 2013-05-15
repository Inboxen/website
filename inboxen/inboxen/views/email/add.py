##
#    Copyright (C) 2013 Jessica Tallon & Matt Molyneaux
#   
#    This file is part of Inboxen front-end.
#
#    Inboxen front-end is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Inboxen front-end is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with Inboxen front-end.  If not, see <http://www.gnu.org/licenses/>.
##

from random import choice
from string import ascii_lowercase
from datetime import datetime

from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.contrib.auth.decorators import login_required

from inboxen.models import Domain, Alias, Tag
from inboxen.helper.alias import alias_available, clean_tags


def gen_alias(count, alias=""):
    # I think this should probably be moved with the helpers?

    if count <= 0:
        return alias
    
    alias += choice(ascii_lowercase)
    
    return gen_alias(count-1, alias)

@login_required
def add(request):

    available = alias_available(request.user)
    if not available:
        return HttpResponseRedirect("/email/request")

    if request.method == "POST":
        alias = request.POST["alias"]
        domain = Domain.objects.get(domain=request.POST["domain"])
        tags = request.POST["tag"]
        
        try:
            alias_test = Alias.objects.get(alias=alias, domain=domain)
            return HttpResponseRedirect("/user/profile")
        except Alias.DoesNotExist:
            pass 

        new_alias = Alias(alias=alias, domain=domain, user=request.user, created=datetime.now())
        new_alias.save()
        
        tags = clean_tags(tags)
        for i, tag in enumerate(tags):
            tag = Tag(tag=tag)
            tag.alias = new_alias
            tag.save()
            tags[i] = tag

 
        return HttpResponseRedirect("/user/profile")

    domains = Domain.objects.all()
    
    alias = ""
    count = 0
    
    min_length = 5 # minimum length of alias
    
    while not alias and count < 15:
        alias = gen_alias(count+min_length)
        try:
            Alias.objects.get(alias=alias)
            alias = ""
            count += 1
        except Alias.DoesNotExist:
            pass
            
    context = {
        "page":"Add Alias",
        "domains":domains,
        "alias":alias,
    }
    
    return render(request, "email/add.html", context)