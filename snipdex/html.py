#!/usr/bin/env python
"""
html.py: The "Smokey" HTML renderer.

The contents of this file are subject to the PfTijah Public License 
Version 1.1 (the "License"); you may not use this file except in 
compliance with the License. You may obtain a copy of the License at 
http://dbappl.cs.utwente.nl/Legal/PfTijah-1.1.html

Software distributed under the License is distributed on an "AS IS" 
basis, WITHOUT WARRANTY OF ANY KIND, either express or implied. See 
the License for the specific language governing rights and limitations 
under the License.

The Original Code is the SnipDex system.

The Initial Developer of the Original Code is the "University of 
Twente". Portions created by the "University of Twente" are 
Copyright (C) 2012 "University of Twente". All Rights Reserved.

Authors: Almer Tigelaar
         Djoerd Hiemstra 
"""

import snipdata
from htmlentitydefs import name2codepoint, codepoint2name
from copy import deepcopy

# ==========================================================================================================
# SMOKEY HTML RENDERING FRAMEWORK
# ==========================================================================================================


MAX_IMAGE_HEIGHT = 90
MAX_SUMMARY_LENGTH = 270


def htmlentitydecode(s):
    """Unescape HTML entities in a string
       TODO: Extend this with handling of numeric codepoints (e.g. &#39;)
    """
    return re.sub('&(%s);' % '|'.join(name2codepoint), 
        lambda m: unichr(name2codepoint[m.group(1)]), s)

def htmlentityencode(s):
    """Escape HTML entities in a string
       TODO: Perhaps this can be implemented more optimally
       TODO: Extend this with handling of numeric codepoints (e.g. &#39;)
    """
    r = ""
    for c in s:
        if codepoint2name.has_key(ord(c)):
            r += "&" + codepoint2name[ord(c)] + ";"
        else:
            r += c
    return r

def bound_text(s, limit):
    """Bounds the length of s to a specific limit.
       If the length of the text exceeds the limit it is augmented
       with a ' ...' continuation marker at the end.
       if None is passed as string, this function return None as well.

       @param s The string to bound (or None).
       @return A (possibly) bounded version of the string.
    """
    if s is None:
        return None       
    if len(s) > limit:
        return s[:limit - 4] + " ..."
    else:
        return s


def get_peer_by_id(peer_list):
    """Create a dictionary with important peer info for quick access
    """
    peer_by_id = dict()
    for (peer, status, score) in peer_list:
        if peer.html_template:
            html_template = peer.html_template[0]
        else:
            html_template = None
        peer_by_id[peer.pid] = (peer.name, peer.icon, peer.description, html_template)
    return peer_by_id 



def give_status_line(page, peer_by_id, snippet_list):

    max_names_length = 24
    status_line = str(page) + '. Results from '    
    names = ''
    nr_of_sources = 0
    sources_seen = dict()

    for snippet in snippet_list:
        for (origin_id, status, score) in snippet.origins:
            peer_name = peer_by_id[origin_id][0]
            if not origin_id in sources_seen:
                sources_seen[origin_id] = 1
                if peer_name and len(names) < max_names_length:
                    if names != '':
                        names += ', '
                    names += peer_name
                else:
                    nr_of_sources += 1
    if len(names) >= max_names_length:
        source = 'other source'
    else:
        source = 'anonymous peer'
    if names:
        status_line += names
        if nr_of_sources > 0:
            status_line += ', and '
    if nr_of_sources > 0:
        status_line += str(nr_of_sources) + ' ' + source
        if nr_of_sources > 1:
            status_line += 's'
    status_line += '.'
    return '<p class="status">' + status_line + '</p>\n'


def give_navigation_line(query_param, this_page, max_page):

    nav_line = ''
    template = '?q={q}&h={h?}&p={p?}&l={l?}'
    new_param = deepcopy(query_param) 
    if this_page > 1:
        new_param['p'] = str(this_page - 1)
        nav_line += '<a href="' + new_param.fill_template_url(template) + '">&lt; prev</a> '
    for page in range(1, max_page + 1):
        new_param['p'] = str(page)
        nav_line += '<a href="' + new_param.fill_template_url(template) + '"> '
        if page == this_page:
            nav_line += '<strong>' + str(page) + '</strong>'
        else:
            nav_line += str(page)
        nav_line += '</a> '
    if this_page < max_page:
        new_param['p'] = str(this_page + 1)
        nav_line += '<a href="' + new_param.fill_template_url(template) + '">next &gt;</a> '
    return '<div class="largeresult"><p class="status">' + nav_line + '</p></div>\n'
    
def form_from_template(html_template, name):
    """ """
    template_url = html_template[0]
    action = snipdata.html_template_to_url(template_url)
    result = '<form action="' + action + '" name="' + name + '">\n'
    result += '<input name="q" type="text" size="50" />\n'
    result += '<input type="submit" value="Zoek" />\n'
    result += '</form>\n'
    return result


def basic_render(query_param, peer_list, snippet_list):

    peer_by_id = get_peer_by_id(peer_list)

    #(origin_scores, origin_list) = snippet_list.get_origin_bins()
    # Render from most important origin to least important
    #for (origin_id, score) in reversed(origin_scores):                     
    # Stuff with renderhints, etc. to be added here:
    #    result += self.default_renderer.render(origin_list[origin_id])

    page = 1 
    max_page = min(10, 1 + int((len(snippet_list) - 1) / 10))
    try:
       page = int(query_param['p'])
    except (KeyError, ValueError):
       page = 1
    if page < 1: 
        page = 1
    if page > max_page:
        page = max_page
    first = (page - 1) * 10 # 10 results per page
    last = first + 10  
    render_snippet_list = snippet_list[first:last]

    result = give_status_line(page, peer_by_id, snippet_list)

    if page == 1:
        for (peer, status, score) in peer_list:
            if status != 'TODO' and peer.query_hints:
                if query_param.normalized_text() in peer.query_hints and peer.name and peer.html_template:
                    result += html_full_peer_render(peer)

    for snippet in render_snippet_list:
        result += html_full_snippet_render(peer_by_id, snippet)
    
    if page == max_page:
        for (peer, status, score) in peer_list:
            if status == 'TODO' and peer.name and peer.html_template:
                result += html_full_peer_render(peer)

    result += give_navigation_line(query_param, page, max_page)    

    return result


def html_full_peer_render(peer):
    
    result = '<div class="largeresult">\n'

    template = peer.html_template[0]
    location = snipdata.resolve_location(template, '', peer.name)
    title = peer.name

    result += '<a class="title" href="' + htmlentityencode(location) + '">' + htmlentityencode(title) + '</a>\n'

    # Icons
    result += ' <span class="attributes">'
    if not peer.icon:
        icon = snipdata.resolve_location(template, '/favicon.ico')
    else:
        icon = snipdata.resolve_location(template, peer.icon)
    if icon:         
        result += '<img width="16" height="16" src="' + htmlentityencode(icon) + '"'
        if title:
            result += ' alt="' + htmlentityencode(title) + '" title="' + htmlentityencode(title) + '"'
        result += ' />'
    result += '</span><br />'

    # Everything up-to location in its own div
    result += "<div>" 
    if peer.description:                     
        max_length = MAX_SUMMARY_LENGTH + 32
        result += '<span class="summary">' + htmlentityencode(bound_text(peer.description, max_length)) + '</span>\n'
    result += form_from_template(peer.html_template, title)
    result += '</div>'

    # Location / Type / Origin; This is floated under the image (if possible), see the CSS.
    content = htmlentityencode(location)
    result += '<div><span class="location" style="float: left;">' + content + '</span></div>\n' 

    result += '</div>\n'
    return result


def html_full_snippet_render(peer_by_id, snippet):
        

    result = '<div class="largeresult">\n'

    for (origin_id, status, score) in snippet.origins:
        (name, icon, description, template) = peer_by_id[origin_id]
        if template:
            break

    location = snipdata.resolve_location(template, snippet.location, snippet.title)
                
    # Preview image:
    if snippet.preview is not None:
        # If width / height info is available
        height = MAX_IMAGE_HEIGHT
        if len(snippet.preview) >= 4 and not snippet.preview[3] is None:
            try:
               height = min(int(snippet.preview[3]), height)
            except ValueError:
               pass
        preview_location = snipdata.resolve_location(template, snippet.preview[1])
        result += ('<div class="largeimage"><a class="img" href="' + htmlentityencode(location) + 
                   '"><img src="' + htmlentityencode(preview_location) + '" alt="" height="' + str(height) + '" /></a></div>\n')

    # Title and link
    if snippet.title:
        result += '<a class="title" href="' + htmlentityencode(location) + '">' + htmlentityencode(snippet.title) + '</a>\n'
    elif snippet.preview is None:
        result += '<a class="title" href="' + htmlentityencode(location) + '">' + htmlentityencode(location) + '</a>\n'


    # Icons
    result += ' <span class="attributes">'
    for (origin_id, status, score) in snippet.origins:
        (name, icon, description, template) = peer_by_id[origin_id]
        if not icon:
            icon = snipdata.resolve_location(template, '/favicon.ico')
        else:
            icon = snipdata.resolve_location(template, icon)
        if icon:         # TODO: EEEEk, hardcoded width/height ... CSS stylesheet?
            result += '<img width="16" height="16" src="' + htmlentityencode(icon) + '"'
            if name:
                result += ' alt="' + htmlentityencode(name) + '" title="' + htmlentityencode(name) + '"'
            result += ' />'
    result += '</span><br />'

    # Everything up-to location in its own div
    result += "<div>" 

    # Attributes
    if len(snippet.attributes) > 0:
        result += '<span class="attributes">'
        for key, value in snippet.attributes:
            result += htmlentityencode(key + ': ' + value + ' | ')
        result = result[:-3] # Removing trailing pipe
        result += "</span><br />\n"

    # Summary
    # NOTE: Some adaptivity here, if the title is longer than 50 chars, it probably is on two
    # lines, this means that we have less space for the summary. A line of summary is about 70 chars,
    # hence we reduce the limit by that much.
    #
    # TODO: These hard-coded defaults aren't particularly pretty, changes to the CSS might also affect
    # the code this way, which is ugly. Perhaps there are nicer solutions to do this ...
    #
    # TODO: This doesn't work when there is a wide image present (this further reduces the space for
    # the summary). We need some way to determine the space taken up by the image, or rather: the space
    # that still is left for the summary.

    if snippet.summary:                     
        max_length = MAX_SUMMARY_LENGTH
        if snippet.title:
            if len(snippet.title) > 52:
                max_length -= 70
        result += '<span class="summary">' + htmlentityencode(bound_text(snippet.summary, max_length)) + '</span>\n'

    # TODO: Extended Summary

    # Direct Links
    if len(snippet.direct_links) > 0:
        result += '<span class="direct_links">'
        for description, link in snippet.direct_links:
            result += '<a href="' + link + '" class="direct_link">' + htmlentityencode(description) + '</a> | '
        result = result[:-3] # Removing trailing pipe
        result += '</span><br />\n'
                
    result += "</div>" # Starts after the Title/Link

    # Location / Type / Origin; This is floated under the image (if possible), see the CSS.
    content = htmlentityencode(bound_text(location, 80))
    result += '<div><span class="location" style="float: left;">' + content + '</span></div>\n' 

    # Service Links
    if len(snippet.service_links) > 0:
        result += '<span class="service_links">'
        for description, link in snippet.service_links:
            result += '<a href="' + link + '" class="service_link">' + htmlentityencode(description) + '</a> | '
        result = result[:-3] # Removing trailing pipe
        result += '</span><br />\n'

    result += '</div>\n'
    return result








# IMAGES
# ======




class HTMLOriginSnippetListRenderer(object):
        """Renders the head portion of the origin.
        
           This serves as a base-class for other renderers that need this
           "by origin" head rendering.
        """

        # Dimensions of the (small) origin icon. TODO: Hard-coded dimensions. Better CSS solution?
        ORIGIN_IMAGE_WIDTH = 16
        ORIGIN_IMAGE_HEIGHT = 16

        MAX_SUMMARY_LENGTH = 270

        def render(self, snippet_list):

                # NOTE: We assume that all snippets in the snippet_list were generated
                # by the same origin, and thus they can all be found on the same HTML page
                # as well. Hence, we use the pagelink of the first item as link and
                # the origin of the first item for other info.
                # (whether this is true needs to be established at a higher level).

                # TODO: I am thinking whether it might be nicer to simply only use the pagelink
                # if it's consistent across snippets (omitting it in other cases). This way we
                # can better aggregate search results yielded by slightly different queries.

                origin = snippet_list[0].origin
                url    = snippet_list[0].pagelink

                result = '<a class="title" href="' + htmlentityencode(url) + '" target="_' + origin.safe_name + '">' + htmlentityencode(origin.name) + '</a>\n'
                if origin.image is not None:
                        result += '<span class="attributes"><img src="' + htmlentityencode(origin.image[1]) + '" alt='' title="' + htmlentityencode(origin.name) + '" width="' + str(self.ORIGIN_IMAGE_WIDTH) + '" height="' + str(self.ORIGIN_IMAGE_HEIGHT) + '" /></span>'
                result += '<br />\n'

                # Body with the description of the origin
                if origin.description is not None:
                        description = bound_text(origin.description, self.MAX_SUMMARY_LENGTH)
                        result += '<span class="summary">' + htmlentityencode(description) + '</span><br />\n'
                result += '<span class="location">' + htmlentityencode(url) + '</span>\n'

                return result

class HTMLImageSnippetListRenderer(HTMLOriginSnippetListRenderer):
        """Aggregates search results provided by one origin which consists of all images
           as one search result in the list.
        """

        IMAGE_COUNT = 10 # (Max) Number of images to show side-by-side (two rows of 5)

        def render(self, snippet_list):

                # Header with the name of the origin and optional image
                result = '<div class="largeresult">\n'
                
                # Render the origin head (see parent class)
                result += super(HTMLImageSnippetListRenderer, self).render(snippet_list)

                snippet_renderer = HTMLImageSnippetRenderer()
                result += '<div style="clear: both;">'
                for snippet in snippet_list[:self.IMAGE_COUNT]: 
                        result += snippet_renderer.render(snippet)
                result += '</div>'

                result += '</div>\n'

                return result

class HTMLImageSnippetRenderer(object):

        MAX_IMAGE_HEIGHT = 75 # Pixels, TODO: Hmmm, hard-coded stuff, put it in the CSS or somesuch?
        MAX_TOOLTIP_LENGTH = 120

        def render(self, snippet):
                titlelink = '<div class="mediumimage"><a href="' + htmlentityencode(snippet.location) + '">'

                height = self.MAX_IMAGE_HEIGHT
                preview = 'http://www.snipdex.org/woops.png'
                if snippet.preview is not None:
                        preview = snippet.preview[1]

                tooltip = snippet.title
                if snippet.summary is not None and len(snippet.summary) > 0:
                        tooltip += "\n" + snippet.summary[:self.MAX_TOOLTIP_LENGTH - len(snippet.title) - 1] # Include some sizeable part of the summary

                imagelink = '<img src="' + htmlentityencode(preview) + '" height="' + str(height) + '" alt="' + htmlentityencode(snippet.title) + '" title="' + htmlentityencode(tooltip) + '"/>'
                return titlelink + imagelink + '</a></div>\n'

# SUGGESTIONS
# ===========

# TODO: Quasi-identical to the SmallSnippetListRenderer below ... Hmmm, perhaps
# we could share even more base class stuff here :)
class HTMLSuggestionSnippetListRenderer(HTMLOriginSnippetListRenderer):

        RENDER_LIMIT    = 10 # Maximum number of suggestions to render
        ROWS_PER_COLUMN = 5  # Number of Rows per column of search suggestions

        def render(self, snippet_list):
                """Renders the snippet list in the space of a normal full snippet."""

                snippet_renderer = HTMLSuggestionSnippetRenderer()

                result = '<div class="largeresult">'

                # Render the origin head (see parent class)
                result += super(HTMLSuggestionSnippetListRenderer, self).render(snippet_list)

                result += '<div>'

                result += '<span class="direct_links" style="float: left; margin-right: 5px;">\n'
                render_count = 0
                for snippet in snippet_list:

                        if render_count % self.ROWS_PER_COLUMN == 0:
                                result += '</span>\n<span class="direct_links" style="float: left; margin-right: 5px;">\n'
        
                        result += snippet_renderer.render(snippet)
                        render_count += 1
                        if render_count >= self.RENDER_LIMIT:
                                break
                result += '</span></div></div>\n'
                return result

class HTMLSuggestionSnippetRenderer(object):

        MAX_TITLE_LENGTH = 40

        def render(self, snippet):
                """Renders Query Suggestions. Probably the most bare renderer."""

                title = snippet.title
                if len(title) > self.MAX_TITLE_LENGTH: 
                        title = title[:self.MAX_TITLE_LENGTH - 3] + '...'

                return '<a class="direct_link" href="' + htmlentityencode(snippet.location) + '">' + htmlentityencode(title) + '</a><br/>\n'

# SMALL
# =====

class HTMLSmallSnippetListRenderer(HTMLOriginSnippetListRenderer):
        
        RENDER_LIMIT = 6 # Maximum number of snippets to render.

        def render(self, snippet_list):
                """Renders the snippet list in the space of a normal full snippet."""

                snippet_renderer = HTMLSmallSnippetRenderer()

                result = '<div class="largeresult">'

                # Render the origin head (see parent class)
                result += super(HTMLSmallSnippetListRenderer, self).render(snippet_list)

                result += '<div>'
                render_count = 0
                for snippet in snippet_list:
                        result += snippet_renderer.render(snippet)
                        render_count += 1
                        if render_count >= self.RENDER_LIMIT:
                                break
                result += '</div></div>'
                return result

class HTMLSmallSnippetRenderer(object):

        # TODO: Restricting the length of the text works somewhat, but yields variable
        # sized looking summaries, as we are not using monospaced fonts. Perhaps there is
        # some way to get a better impression of the rendered size (especially the rendered
        # number of lines) and then variabely adjust the rendered amount of text?
        # [This also holds true for all other HTML text renderings]

        MAX_IMAGE_HEIGHT = 45  # TODO: *Yuck* hard-coded pixel sizes :( CSS?
        MAX_TITLE_AND_SUMMARY_LENGTH = 170

        def render(self, snippet):

                title = snippet.title
                if len(title) > 40: 
                        title = title[0:37] + '...'

                result = '<div class="smallresult">'
                summary = snippet.summary
                if summary is not None and len(summary) + len(title) > self.MAX_TITLE_AND_SUMMARY_LENGTH:
                        summary = bound_text(summary, self.MAX_TITLE_AND_SUMMARY_LENGTH - len(title))

                if snippet.preview is not None:
                        # If width / height info is available
                        height = self.MAX_IMAGE_HEIGHT
                        if len(snippet.preview) >= 4 and not snippet.preview[3] is None:
                                height = min(snippet.preview[3], height)
                        result += '<div class="smallimage"><a class="img" href="' + htmlentityencode(snippet.location) + '"><img src="' + htmlentityencode(snippet.preview[1]) + '" alt="" height="' + str(height) + '" /></a></div>'
                result += '<span class="direct_links">'
                result += '<a class="direct_link" href="' + htmlentityencode(snippet.location) + '">' + htmlentityencode(title) + '</a>\n'
                
                if summary is not None and len(summary) > 0:
                        result += htmlentityencode(summary)
                result += '</span><br />\n'

                # Attributes
                if len(snippet.attributes) > 0:
                        result += '<span class="attributes">'
                        for key, value in snippet.attributes:
                                result += htmlentityencode(key + ': ' + value + ' | ')
                        result = result[:-3] # Removing trailing pipe
                        result += '</span><br />\n'
                result += '</div>\n'
                return result

# FULL
# ====

class HTMLFullSnippetListRenderer(object):
        
        def render(self, snippet_list):
                """Renders the snippet list"""

                snippet_renderer = HTMLFullSnippetRenderer()

                result = ""
                for snippet in snippet_list:
                        result += snippet_renderer.render(snippet)
                return result

                
# Testing...
if (__name__ == '__main__'): 
    import logging
    logger = logging.getLogger("SnipdexHTML")
    logging.basicConfig(level=logging.DEBUG, format="%(name)-11s %(message)s")
    logger.debug("Testing. ")

    # Open cache
    query_param = snipdata.Query({'q': 'vrijhof'})
    cache = snipdata.SnipdexCache('/tmp/snipdex-cache', logger)
    (peer_list, snippet_list) = cache.response_by_query(query_param) 
    print basic_render('Testing...', query_param, peer_list, snippet_list)

