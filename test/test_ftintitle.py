# This file is part of beets.
# Copyright 2015, Fabrice Laporte.
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

"""Tests for the 'ftintitle' plugin."""

from __future__ import (division, absolute_import, print_function,
                        unicode_literals)

from test._common import unittest
from test.helper import TestHelper
from beetsplug import ftintitle


class FtInTitlePluginFunctional(unittest.TestCase, TestHelper):
    def setUp(self):
        """Set up configuration"""
        self.setup_beets()
        self._ft_set_config()
        self.load_plugins('ftintitle')

    def tearDown(self):
        self.unload_plugins()
        self.teardown_beets()

    def _ft_add_item(self, path, artist, title, aartist):
        return self.add_item(path=path,
                             artist=artist,
                             title=title,
                             albumartist=aartist)

    def _ft_set_config(self):
        # Add my own defaults as they may change in the plugin
        self.config['ftintitle']['format'] = 'feat. {0}'
        self.config['ftintitle']['drop'] = False
        self.config['ftintitle']['auto'] = True
        self.config['ftintitle']['pretend'] = False
        self.config['ftintitle']['smart'] = False

    def test_functional_general_functionality(self):
        # Test 1
        self._ft_set_config()
        item = self._ft_add_item('/', u'Alice ft Bob', u'Song 1', 'David')
        self.run_command('ftintitle')
        item.load()
        self.assertEqual(item['artist'], u'Alice')
        self.assertEqual(item['title'], u'Song 1 feat. Bob')

        # Test 2
        item = self._ft_add_item('/', u'Alice', u'Song 1 ft. Bob', u'Bob')
        self.run_command('ftintitle')
        item.load()
        self.assertEqual(item['artist'], u'Alice')
        self.assertEqual(item['title'], u'Song 1 feat. Bob')

    def test_functional_drop(self):
        # Test 1
        self._ft_set_config()
        item = self._ft_add_item('/', u'Alice ft Bob', u'Song 1', u'Alice')
        self.run_command('ftintitle', '-d')
        item.load()
        self.assertEqual(item['artist'], u'Alice')
        self.assertEqual(item['title'], u'Song 1')

        # Test 2
        item = self._ft_add_item('/', u'Alice', u'Song 1 ft. Bob', u'Alice')
        self.run_command('ftintitle', '-d')
        item.load()
        self.assertEqual(item['artist'], u'Alice')
        self.assertEqual(item['title'], u'Song 1')

        # Test 3
        self._ft_set_config()
        self.config['ftintitle']['drop'] = True
        item = self._ft_add_item('/', u'Alice ft Bob', u'Song 1', u'Alice')
        item.load()
        self.run_command('ftintitle')
        self.assertEqual(item['artist'], u'Alice')
        self.assertEqual(item['title'], u'Song 1')

    def test_functional_pretend(self):
        # Test 1
        self._ft_set_config()
        self.config['ftintitle']['format'] = 'featuring {0}'
        item = self._ft_add_item('/', u'Alice', u'Song 1 ft. Bob', u'Bob')
        item.load()
        self.run_command('ftintitle', '-p')
        self.assertEqual(item['artist'], u'Alice')
        self.assertEqual(item['title'], u'Song 1 ft. Bob')

        # Test 2
        self._ft_set_config()
        item = self._ft_add_item('/', u'Alice feat Bob', u'Song 1', u'Bob')
        item.load()
        self.run_command('ftintitle', '-p')
        self.assertEqual(item['artist'], u'Alice feat Bob')
        self.assertEqual(item['title'], u'Song 1')

        # Test 3
        self._ft_set_config()
        self.config['ftintitle']['format'] = 'featuring. {0}'
        self.config['ftintitle']['pretend'] = True
        item.load()
        item = self._ft_add_item('/', u'Alice ft Bob', u'Song 1', u'Alice')
        self.run_command('ftintitle')
        self.assertEqual(item['artist'], u'Alice ft Bob')
        self.assertEqual(item['title'], u'Song 1')

    def test_functional_smart(self):
        item = self._ft_add_item('/', u'Bob ft Alice', u'Song1 ft. Bob',
                                 u'Alice')
        self.run_command('ftintitle', '-s')
        item.load()
        self.assertEqual(item['artist'], u'Alice')
        self.assertEqual(item['title'], u'Song 1 ft. Bob')

        item = self._ft_add_item('/', u'Alice feat Bob', u'Song 1', u'Bob')
        self.run_command('ftintitle', '-s')
        item.load()
        self.assertEqual(item['artist'], u'Alice')
        self.assertEqual(item['title'], u'Song 1 ft. Bob')

        self._ft_set_config('feat. {0}', False, True, False, True)
        item = self._ft_add_item('/', u'Alice ft Bob', u'Song 1', u'Alice')
        self.run_command('ftintitle')
        item.load()
        self.assertEqual(item['artist'], u'Alice feat. Bob')
        self.assertEqual(item['title'], u'Song 1')

    def test_functional_custom_format(self):
        # Test 1
        self._ft_set_config()
        item = self._ft_add_item('/', u'Alice ft Bob', u'Song 1', u'Alice')
        self.run_command('ftintitle')
        item.load()
        self.assertEqual(item['artist'], u'Alice')
        self.assertEqual(item['title'], u'Song 1 feat. Bob')

        # Test 2
        self._ft_set_config()
        self.config['ftintitle']['format'] = 'featuring {0}'
        item = self._ft_add_item('/', u'Alice feat. Bob', u'Song 1', u'Alice')
        self.run_command('ftintitle')
        item.load()
        self.assertEqual(item['artist'], u'Alice')
        self.assertEqual(item['title'], u'Song 1 featuring Bob')

        # Test 3
        self._ft_set_config()
        self.config['ftintitle']['format'] = 'with {0}'
        item = self._ft_add_item('/', u'Alice feat Bob', u'Song 1', u'Alice')
        self.run_command('ftintitle')
        item.load()
        self.assertEqual(item['artist'], u'Alice')
        self.assertEqual(item['title'], u'Song 1 with Bob')


class FtInTitlePluginTest(unittest.TestCase):
    def setUp(self):
        """Set up configuration"""
        ftintitle.FtInTitlePlugin()

    def test_find_feat_part(self):
        test_cases = [
            {
                'artist': 'Alice ft. Bob',
                'album_artist': 'Alice',
                'feat_part': 'Bob'
            },
            {
                'artist': 'Alice feat Bob',
                'album_artist': 'Alice',
                'feat_part': 'Bob'
            },
            {
                'artist': 'Alice featuring Bob',
                'album_artist': 'Alice',
                'feat_part': 'Bob'
            },
            {
                'artist': 'Alice & Bob',
                'album_artist': 'Alice',
                'feat_part': 'Bob'
            },
            {
                'artist': 'Alice and Bob',
                'album_artist': 'Alice',
                'feat_part': 'Bob'
            },
            {
                'artist': 'Alice With Bob',
                'album_artist': 'Alice',
                'feat_part': 'Bob'
            },
            {
                'artist': 'Alice defeat Bob',
                'album_artist': 'Alice',
                'feat_part': None
            },
            {
                'artist': 'Alice & Bob',
                'album_artist': 'Bob',
                'feat_part': 'Alice'
            },
            {
                'artist': 'Alice ft. Bob',
                'album_artist': 'Bob',
                'feat_part': 'Alice'
            },
        ]

        for test_case in test_cases:
            feat_part = ftintitle.find_feat_part(
                test_case['artist'],
                test_case['album_artist']
            )
            self.assertEqual(feat_part, test_case['feat_part'])

    def test_split_on_feat(self):
        parts = ftintitle.split_on_feat('Alice ft. Bob')
        self.assertEqual(parts, ('Alice', 'Bob'))
        parts = ftintitle.split_on_feat('Alice feat Bob')
        self.assertEqual(parts, ('Alice', 'Bob'))
        parts = ftintitle.split_on_feat('Alice feat. Bob')
        self.assertEqual(parts, ('Alice', 'Bob'))
        parts = ftintitle.split_on_feat('Alice featuring Bob')
        self.assertEqual(parts, ('Alice', 'Bob'))
        parts = ftintitle.split_on_feat('Alice & Bob')
        self.assertEqual(parts, ('Alice', 'Bob'))
        parts = ftintitle.split_on_feat('Alice and Bob')
        self.assertEqual(parts, ('Alice', 'Bob'))
        parts = ftintitle.split_on_feat('Alice With Bob')
        self.assertEqual(parts, ('Alice', 'Bob'))
        parts = ftintitle.split_on_feat('Alice defeat Bob')
        self.assertEqual(parts, ('Alice defeat Bob', None))

    def test_contains_feat(self):
        self.assertTrue(ftintitle.contains_feat('Alice ft. Bob'))
        self.assertTrue(ftintitle.contains_feat('Alice feat. Bob'))
        self.assertTrue(ftintitle.contains_feat('Alice feat Bob'))
        self.assertTrue(ftintitle.contains_feat('Alice featuring Bob'))
        self.assertTrue(ftintitle.contains_feat('Alice & Bob'))
        self.assertTrue(ftintitle.contains_feat('Alice and Bob'))
        self.assertTrue(ftintitle.contains_feat('Alice With Bob'))
        self.assertFalse(ftintitle.contains_feat('Alice defeat Bob'))
        self.assertFalse(ftintitle.contains_feat('Aliceft.Bob'))


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == b'__main__':
    unittest.main(defaultTest='suite')
