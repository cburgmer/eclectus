# -*- coding: utf-8 -*-
u"""
Provides HTML formatting services for a radical table.

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

class RadicalView:
    def __init__(self, charDbInst=None, **options):
        self.charDB = charDbInst or chardb.CharacterDB(**options)

    def getRadicalTable(self):
        """Gets a table of Kangxi radicals, sorted by radical index."""
        htmlList = []
        htmlList.append('<table id="radicaltable" class="radical">')

        lastStrokeCount = None
        radicalForms = self.charDB.kangxiRadicalForms
        radicalEntryDict = self.charDB.getRadicalDictionaryEntries()

        for radicalIdx in range(1, 215):
            mainForm, strokeCount, variants, _ = radicalForms[radicalIdx]

            if lastStrokeCount != strokeCount:
                lastStrokeCount = strokeCount
                htmlList.append(
                    '<tr class="strokeCount" id="strokecount%d">' \
                        % strokeCount \
                    + '<td colspan="3"><h2>%s</h2></td>' \
                        % (ngettext('%(strokes)d stroke', '%(strokes)d strokes',
                            strokeCount) % {'strokes': strokeCount})
                    + '</tr>')

            htmlList.append(
                '<tr class="radicalEntry" id="radical%d">' \
                    % radicalIdx \
                + '<td class="radicalIndex">%s</td>' % radicalIdx)

            if variants:
                htmlList.append('<td class="radical">' \
                    + '<a class="character" href="#radical(%s)">' % radicalIdx \
                    + '<span class="radical">%s</span><br/>' % mainForm \
                    + '<span class="radicalVariant">%s</span>' \
                        % ''.join(variants) \
                    + '</a></td>')
            else:
                htmlList.append('<td class="radical">' \
                    + '<a class="character" href="#radical(%s)">' % radicalIdx \
                    + '<span class="radical">%s</span><br/>' % mainForm \
                    + '</a></td>')

            if radicalIdx in radicalEntryDict:
                _, meaning = radicalEntryDict[radicalIdx] # TODO remove reading
                htmlList.append(
                    '<td class="translation">%s</td>' % meaning)
            else:
                htmlList.append('<td class="translation"></td>')

            htmlList.append('</tr>')

        htmlList.append('</table>')

        # TODO
        radicalEntries = {}
        for radicalIdx in range(1, 215):
            if radicalIdx in radicalEntryDict:
                _, meaning = radicalEntryDict[radicalIdx] # TODO remove reading
            else:
                meaning = None
            _, _, _, representatives = radicalForms[radicalIdx]
            radicalEntries[radicalIdx] = (representatives, meaning)

        return "\n".join(htmlList), radicalEntries

    def getCharacterForRadical(self, radicalIndex, includeAllComponents=False):
        """Gets a list of characters classified under the given radical."""
        # group by residual stroke count
        characterGroups = self.charDB.getCharacterListForKangxiRadicalIndex(
            radicalIndex, includeAllComponents=includeAllComponents)

        htmlList = []

        # show main radical form
        htmlList.append('<h3>%s</h3>' \
            % (gettext('Radical %(radical_index)d') \
                % {'radical_index': radicalIndex}))

        charLinks = []
        for strokeCount in sorted(characterGroups['radical'].keys()):
            for char in sorted(characterGroups['radical'][strokeCount]):
                charLinks.append('<span class="character">' \
                    + '<a class="character" href="#lookup(%s)">%s</a>' \
                        % (util.encodeBase64(char), char) \
                    + '</span>')

        htmlList.append(' '.join(charLinks))

        radicalEntryDict = self.charDB.getRadicalDictionaryEntries()
        _, meaning = radicalEntryDict.get(radicalIndex, (None, None))
        if meaning:
            htmlList.append(' <span class="translation">%s</span>' % meaning)

        radicalForms = self.charDB.kangxiRadicalForms
        _, strokeCount, _, _ = radicalForms[radicalIndex]
        if strokeCount:
            htmlList.append(' <span class="strokecount">(%s)</span>' \
                % (ngettext('%(strokes)d stroke', '%(strokes)d strokes',
                    strokeCount) % {'strokes': strokeCount}))


        htmlList.append('<h3>%s</h3>' % gettext('Characters'))

        # list sorted by residual stroke count
        if not characterGroups[None]:
            htmlList.append('<span class="meta">%s</span>' \
                % gettext('no results found for the selected character domain'))
        else:
            htmlList.append('<table class="searchResult">')
            for strokeCount in sorted(characterGroups[None].keys()):
                if type(strokeCount) not in (type(0), type(0L)):
                    # sort out non stroke count groups
                    continue

                htmlList.append('<tr>' \
                    + '<th class="strokeCount">+%s</th><td>' % strokeCount)
                charLinks = []
                for char in sorted(characterGroups[None][strokeCount]):
                    charLinks.append('<span class="character">' \
                        + '<a class="character" href="#lookup(%s)">%s</a>' \
                            % (util.encodeBase64(char), char) \
                        + '</span>')
                htmlList.append(' '.join(charLinks))

                htmlList.append('</td></tr>')

            # Add characters without stroke count information
            if None in characterGroups[None]:
                htmlList.append('<tr>' \
                    + '<th class="strokeCount">%s</th><td>' % gettext('Unknown'))
                charLinks = []
                for char in sorted(characterGroups[None][None]):
                    charLinks.append('<span class="character">' \
                        + '<a class="character" href="#lookup(%s)">%s</a>' \
                            % (util.encodeBase64(char), char) \
                        + '</span>')
                htmlList.append(' '.join(charLinks))

                htmlList.append('</td></tr>')

            htmlList.append('</table>')

        return "\n".join(htmlList)
