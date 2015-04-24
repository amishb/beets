# This file is part of beets.
# Copyright 2015, Verrus, <github.com/Verrus/beets-plugin-featInTitle>
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.

"""Moves "featured" artists to the title from the artist field.
"""
from __future__ import (division, absolute_import, print_function,
                        unicode_literals)

import re

from beets import plugins
from beets import ui
from beets.util import displayable_path
from beets import config


def split_on_feat(text):
    """Given a text string, split the "main" artist from any artist
    on the right-hand side of a string like "feat". Return the main
    artist, which is always a string, and the featuring artist, which
    may be a string or None if none is present.
    """
    # split on the first "feat".
    regex = re.compile(plugins.feat_tokens(), re.IGNORECASE)
    parts = [s.strip() for s in regex.split(text, 1)]
    if len(parts) == 1:
        return parts[0], None
    else:
        return tuple(parts)


def contains_feat(text):
    """Determine whether the title contains a "featured" marker.
    """
    return bool(re.search(plugins.feat_tokens(), text, flags=re.IGNORECASE))


def find_feat_part(artist, albumartist):
    """Attempt to find featured artists in the item's artist fields and
    return the results. Returns None if no featured artist found.
    """
    feat_part = None

    # Look for the album artist in the artist field. If it's not
    # present, give up.
    albumartist_split = artist.split(albumartist, 1)
    if len(albumartist_split) <= 1:
        return feat_part

    # If the last element of the split (the right-hand side of the
    # album artist) is nonempty, then it probably contains the
    # featured artist.
    elif albumartist_split[-1] != '':
        # Extract the featured artist from the right-hand side.
        _, feat_part = split_on_feat(albumartist_split[-1])

    # Otherwise, if there's nothing on the right-hand side, look for a
    # featuring artist on the left-hand side.
    else:
        lhs, rhs = split_on_feat(albumartist_split[0])
        if lhs:
            feat_part = lhs

    return feat_part


class FtInTitlePlugin(plugins.BeetsPlugin):
    def __init__(self):
        super(FtInTitlePlugin, self).__init__()

        self.config.add({
            'auto': True,
            'drop': False,
            'format': u'feat. {0}',
            'pretend': False,
        })

        self._command = ui.Subcommand(
            'ftintitle',
            help='move or reformat the featured artists into the title field')

        self._command.parser.add_option(
            '-d', '--drop', dest='drop',
            action='store_true', default=False,
            help='drop featuring from artists and titles')

        self._command.parser.add_option(
            '-p', '--pretend', dest='pretend',
            action='store_true', default=False,
            help='only simulate the changes')

        if self.config['auto']:
            self.import_stages = [self.imported]

    def commands(self):

        def func(lib, opts, args):
            self.config.set_args(opts)
            write = config['import']['write'].get(bool)
            pretend = config['ftintitle']['pretend'].get(bool)

            for item in lib.items(ui.decargs(args)):
                self.process_feat(item)
                if not pretend:
                    item.store()
                    if write:
                        item.try_write()

        self._command.func = func
        return [self._command]

    def imported(self, session, task):
        """Import hook for moving featuring information automatically.
        """
        write = config['import']['write'].get(bool)
        pretend = config['ftintitle']['pretend'].get(bool)

        for item in task.imported_items():
            self.process_feat(item)
            if not pretend:
                item.store()
                if write:
                    item.try_write()

    def update_metadata(self, item, field, main_part, feat_part):
        """Update the meta data with the relevent information that
        is passed into the function. THis function will allso handle the
        dropping an formatting of the feating part of the field
        """
        drop_feat = self.config['drop'].get(bool)

        if drop_feat or feat_part == '':
            self._log.info(u'Dropping feat from {0}: {1} -> {2}',
                           field, getattr(item, field), main_part)
            setattr(item, field, main_part.strip())
        else:
            feat_format = self.config['format'].get(unicode)
            new_format = feat_format.format(feat_part)
            new_field = u"{0} {1}".format(main_part, new_format)
            self._log.info(u'Updating {0}: {1} -> {2}',
                           field, getattr(item, field), new_field)
            setattr(item, field, new_field)

    def process_feat(self, item):
        """Look into the item and determine if the artist has a featuring
        in the artist and move it into the title, or the title needs
        reformtting.
        """

        artist = item.artist.strip()
        title = item.title.strip()

        if contains_feat(item.artist):
            artist_part, feat_part = split_on_feat(artist)
            self.update_metadata(item, 'artist', artist_part, '')
            self.update_metadata(item, 'title', title, feat_part)
        elif contains_feat(item.title):
            title_part, feat_part = split_on_feat(title)
            self.update_metadata(item, 'title', title_part, feat_part)
        else:
            pass
            #self._log.info(u'No featuring artist found')
