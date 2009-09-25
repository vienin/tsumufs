#!/usr/bin/python
# -*- python -*-
#
# Copyright (C) 2008  Google, Inc. All Rights Reserved.
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

'''TsumuFS, a fs-based caching filesystem.'''

import os
import os.path
import sys
import errno
import stat
import traceback
import shutil
import time
import threading

import pygtk
pygtk.require('2.0')

import gtk
import gobject
import egg.trayicon
import pynotify
import xattr

__version__  = (0, 1)

import fuse
#import tsumufs

import dbus
import dbus.glib
import gobject

# required
import dbus.glib
import gtk

gobject.threads_init()
dbus.glib.init_threads()

import gettext
gettext.install('TsumuFS', 'locale', unicode=1) 

class TrayIconThread():
  _trayIcon = None
  _tooltips = None
  _eventBox = None
  _displayImage = None

  _mountPointPath = '.'

  _isUnmounted    = True
  _isConnected    = True
  _isConflicted   = False
  _isSynchronized = True

  _iconPathPrefix ="/usr/share/tsumufs/icons"
  
  _syncQueue = []
  

  def __init__(self):

    # TODO: ping tsumufs and retreive default infos via dbus
    if os.system("/bin/touch " + os.path.join(os.path.expanduser("~"), ".tsumufs", ".overlay/")):
      self._isUnmounted = False

    # Initializing TrayIcon object.
    pynotify.init('TsumuFS')

    self._trayIcon = egg.trayicon.TrayIcon('TsumuFS')
    self._tooltips = gtk.Tooltips()
    self._eventBox = gtk.EventBox()
    self._eventBox.set_events(gtk.gdk.BUTTON_PRESS_MASK)
    self._displayImage = gtk.Image()
    self._eventBox.add(self._displayImage)
    self._eventBox.connect('button_press_event', self._buttonPress)
    self._trayIcon.connect('delete-event', self._cleanup)
    self._trayIcon.add(self._eventBox)
    self._trayIcon.show_all()

    self._updateIcon()

  def _updateIcon(self):
    """
    Choose the trayIcon according to connexion state. 
    If SyncWork event is set, then _isSynchronized is True
    SyncWork is set during propogate changes
    """
    
    if self._isUnmounted:
      path = os.path.join(self._iconPathPrefix, 'unmounted.png')
    elif not self._isConnected:
      path = os.path.join(self._iconPathPrefix, 'disconnected.png')
    elif self._isSynchronized:
      path = os.path.join(self._iconPathPrefix, 'connected.png')
    else:
      path = os.path.join(self._iconPathPrefix, 'syncro_file.png')

    pixbuf = gtk.gdk.pixbuf_new_from_file(path)

    if self._isConflicted:
      path = os.path.join(self._iconPathPrefix, 'conflicted.png')
      pixbuf.blit_from_file(path)

    size = self._trayIcon.get_size()
    pixbuf.scale_simple(size[0], size[1], gtk.gdk.INTERP_BILINEAR)
    self._displayImage.set_from_pixbuf(pixbuf)

  def _cleanup(self):
    gtk.main_quit()

  def _buttonPress(self, widget, event):
    """
    Creating gtkMenu to get informations about files which are not synchronized
    We don't care about Event.type
    """

    menu = gtk.Menu()
    if self._isSynchronized:
        item1 = gtk.ImageMenuItem(_("Synchronized"))
    elif self._isConnected:
        item1 = gtk.ImageMenuItem(_("Connected"))
    else:
        item1 = gtk.ImageMenuItem(_("Disconnected"))
        
    path = os.path.join(self._iconPathPrefix, 'ufo_icon.png')
    pImage = gtk.image_new_from_file(path)
    item1.set_image(pImage)
    menu.append(item1)
    
    bar = gtk.SeparatorMenuItem()
    menu.append(bar)
    
    """
    We're looking for if an item is sending to distant file system server
    In that case, we display its name
    """
    if len(self._syncQueue) > 0:
      syncitem = self._syncQueue[0]
      name = syncitem['file']
      item3 = gtk.ImageMenuItem(str(name))
      path = os.path.join(self._iconPathPrefix, 'syncro_file.png')
      pImage = gtk.image_new_from_file(path)
      item3.set_image(pImage)   
      menu.append(item3) 
        
    # Edit a submenu to show all items which are in the syncQueue
    item2 = gtk.ImageMenuItem(_("Files not synchronized"))
    path = os.path.join(self._iconPathPrefix, 'synchronized.png')
    pImage = gtk.image_new_from_file(path)
    item2.set_image(pImage)   
    menu.append(item2)
    
    # Show an icon depending to type of changing (add, delete, modify, etc)
    submenu = gtk.Menu()
    if len(self._syncQueue) > 0:
      for item in self._syncQueue:
        file = item['file']
        change = item['type']

        subitem = gtk.ImageMenuItem(str(file))
        if str(change) == "new":
          path = os.path.join(self._iconPathPrefix, 'new_file.png')
        elif str(change) == "link":
          path = os.path.join(self._iconPathPrefix, 'new_file.png')
        elif str(change) == "unlink":
          path = os.path.join(self._iconPathPrefix, 'delete_file.png')
        elif str(change) == "change":
          path = os.path.join(self._iconPathPrefix, 'update_file.png')
        elif str(change) == "rename":
          path = os.path.join(self._iconPathPrefix, 'rename_file.png')

        pImage = gtk.image_new_from_file(path)
        subitem.set_image(pImage)
        submenu.append(subitem)
        subitem.show()

    else:
      file = (_("No files queued"))
      subitem = gtk.MenuItem(str(file))
      submenu.append(subitem)
      subitem.show()

    # Appending submenu to mainMenu        
    item2.set_submenu(submenu)
    item1.show()
    bar.show()
    if len(self._syncQueue) > 0:
      item3.show()
    item2.show()
    menu.popup(None, None, None, event.button, event.time)
    menu.attach_to_widget(self._trayIcon, None)

  def _notifyDisconnected(self):
    summary = 'Disconnected from server'
    body = (_('You have been disconnected, file synchronisation paused'))
    uri = os.path.join(self._iconPathPrefix, 'ufo.png')

    notification = pynotify.Notification(summary, body, uri)
    notification.attach_to_widget(self._trayIcon)
    notification.show()

  def _handleSynchronisationItemSignal(self, item):
    print "_handleSynchronisationItemSignal " + str(item)
    if item['action'] == 'append':
      self._syncQueue.append({'file' : item['file'], 
                              'type' : item['type']})
      if len(self._syncQueue) == 1:
        self._isSynchronized = False
        self._updateIcon()
    else:
      try:
        self._syncQueue.remove({'file' : item['file'], 
                                'type' : item['type']})
      except:
        print str(item) + " not found in sync queue"

      if len(self._syncQueue) == 0:
        self._isSynchronized = True
        self._updateIcon()

  def _handleConnectionStatusSignal(self, status):
    print "_handleConnectionStatusSignal " + str(status)
    old_isConnected = self._isConnected
    self._isConnected = status

    if self._isConnected != old_isConnected:
      self._updateIcon()
      if self._isConnected == False:
         self._notifyDisconnected()

  def _handleSynchronisationStatusSignal(self, status):
    print "_handleSynchronisationStatusSignal " + str(status)
    self._updateIcon()

  def _handleUnmountedStatusSignal(self, status):
    print "_handleUnmountedStatusSignal " + str(status)
    self._isUnmounted = status
    self._updateIcon()


class DbusMainLoopThread(threading.Thread):

  def __init__(self):
    threading.Thread.__init__(self, name='DbusMainLoopThread')

  def run(self):
    bus = dbus.SystemBus()
    bus.add_signal_receiver(icon._handleConnectionStatusSignal, 
                            dbus_interface = "org.tsumufs.NotificationService", 
                            signal_name = "_notifyConnectionStatus")
    # bus.add_signal_receiver(icon._handleSynchronisationStatusSignal, 
    #                        dbus_interface = "org.tsumufs.NotificationService", 
    #                        signal_name = "_notifySynchronisationStatus")
    bus.add_signal_receiver(icon._handleUnmountedStatusSignal, 
                            dbus_interface = "org.tsumufs.NotificationService", 
                            signal_name = "_notifyUnmountedStatus")
    bus.add_signal_receiver(icon._handleSynchronisationItemSignal, 
                            dbus_interface = "org.tsumufs.NotificationService", 
                            signal_name = "_notifySynchronisationItem")

    loop = gobject.MainLoop()
    loop.run()

def daemonize():
  if os.fork() > 0:
    sys.exit(0)

  sys.stderr.close()
  sys.stdout.close()
  sys.stdin.close()

if __name__ == '__main__':

  # daemonize()

  icon = TrayIconThread()

  _dbusThread = DbusMainLoopThread()
  _dbusThread.start()

  gtk.main()

