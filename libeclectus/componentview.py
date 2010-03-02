# -*- coding: utf-8 -*-
u"""
Provides HTML formatting services for component (aka multi-radical) searches.

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License
as published by the Free Software Foundation; either version 2
of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
"""

from libeclectus import chardb
from libeclectus import util
from libeclectus.locale import gettext, ngettext

class ComponentView:
    def __init__(self, charDbInst=None, **options):
        self.charDB = charDbInst or chardb.CharacterDB(**options)

        self.radicalFormEquivalentCharacterMap \
            = self.charDB.radicalFormEquivalentCharacterMap

    def getComponentSearchTable(self, components=[],
        includeEquivalentRadicalForms=False, includeSimilarCharacters=False):
        """
        Gets a table of minimal components for searching characters by
        component. Annotates given characters and characters that would
        result in zero results if selected.
        """
        componentsByStrokeCount = self.charDB.minimalCharacterComponents

        # TODO replace
        selected = components
        #selected = set([self.charDB.preferRadicalFormForCharacter(char) \
            #for char in components])

        if components:
            currentResultRadicals = self.charDB.getComponentsWithResults(
                components,
                includeEquivalentRadicalForms=includeEquivalentRadicalForms,
                includeSimilarCharacters=includeSimilarCharacters)
        else:
            currentResultRadicals = None

        htmlList = []
        htmlList.append('<table class="component">')

        strokeCountList = componentsByStrokeCount.keys()
        strokeCountList.sort()
        for strokeCount in strokeCountList:
            htmlList.append('<tr><th>%d</th><td>' % strokeCount)
            for form in sorted(componentsByStrokeCount[strokeCount]):
                if form in selected:
                    formClass = 'selectedComponent'
                elif currentResultRadicals != None \
                    and form not in currentResultRadicals:
                    formClass = 'zeroResultComponent'
                else:
                    formClass = ''

                formBase64 = util.encodeBase64(form)
                htmlList.append(
                    '<a class="character" href="#component(%s)">' % formBase64 \
                    + '<span class="component %s" id="c%s">%s</span>' \
                        % (formClass, formBase64, form) \
                    + '</a>')
            htmlList.append('</td></tr>')
        htmlList.append('</table>')

        return "\n".join(htmlList)

    def getComponentSearchResult(self, components,
        includeEquivalentRadicalForms=False, includeSimilarCharacters=False):
        """Gets a list of characters containing the given components."""
        chars = self.charDB.getCharactersForComponents(components,
            includeEquivalentRadicalForms=includeEquivalentRadicalForms,
            includeSimilarCharacters=includeSimilarCharacters)

        if chars:
            charLinks = []
            for char in chars:
                charLinks.append(
                    '<a class="character" href="#lookup(%s)">%s</a>' \
                        % (util.encodeBase64(char), char))
            html = '<span class="character">%s</span>' % ' '.join(charLinks)
        else:
            html = '<p class="meta">%s</p>' % gettext('No entries')

        return html, len(chars)

