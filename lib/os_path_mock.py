#!/usr/bin/python2.4
# -*- python -*-
#
# Copyright (C) 2007  Google, Inc. All Rights Reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

'''Mock os.path module.'''

import posixpath

import os_mock


def dirname(path):
  return posixpath.dirname(path)


def basename(path):
  return posixpath.basename(path)


def isfile(path):
  f = os_mock._findFileFromPath(path)
  return type(f) == os_mock.FakeFile


def islink(path):
  f = os_mock._findFileFromPath(path)
  return type(f) == os_mock.FakeSymlink


def isdir(path):
  f = os_mock._findFileFromPath(path)
  return type(f) == os_mock.FakeDir


def join(path, *parts):
  return posixpath.join(path, *parts)
