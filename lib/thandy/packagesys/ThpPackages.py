# Copyright 2011 The Tor Project, Inc.  See LICENSE for licensing information.

import logging
import os

import thandy.util
import thandy.packagesys.PackageSystem as PS
import thandy.packagesys.PackageDB as PDB

json = thandy.util.importJSON()

class ThpDB(object):
    def __init__(self):
        self._thp_root = os.environ.get("THP_INSTALL_ROOT")
        if self._thp_root is None:
          raise Exception("There is no THP_INSTALL_ROOT variable set")

    def insert(self, pkg):
        thandy.util.replaceFile(os.path.join(self._thp_root,
                                             pkg['package_name']),
                                pkg)

    def delete(self, pkg):
        try:
          os.unlink(os.path.join(self._thp_root,
                                 pkg['package_name']))
        except Exception as e:
          print e

    def update(self, pkg):
        self.insert(pkg)

    def exists(self, name):
        fname = os.path.join(self._thp_root, name)
        fexists = os.path.exists(fname)

        version = -1
        if fexists:
            contents = open(fname, "r").read()
            metadata = json.loads(contents)
            version = metadata['package_version']
        return exists, version

class ThpChecker(PS.Checker):
    def __init__(self, name, version):
        PS.Checker.__init__(self)
        self._name = name
        self._version = version
        self._db = ThpDB()

    def __repr__(self):
        return "ThpChecker(%r, %r)"%(self._name, self._version)

    def getInstalledVersions(self):
        versions = []
        (exists, version) = self._db.exists(self._name):

        if exists:
            versions.append(version)

        return versions

    def isInstalled(self):
        return self._version in self.getInstalledVersions()

class ThpInstaller(PS.Installer):
    def __init__(self, relPath, installCommand, removeCommand=None):
        PS.Installer.__init__(self, relPath)
        self._db = ThpDB()

    def __repr__(self):
        return "ThpInstaller(%r)" %(self._relPath)

    def install(self):
        self._thp_root = os.environ.get("THP_INSTALL_ROOT")
        if self._thp_root is None:
          raise Exception("There is no THP_INSTALL_ROOT variable set")

#        shutil.copytree()

    def remove(self):
        if self._removeCommand:
            raise thandy.RemoveNotSupported()
        self._runCommand(self._removeCommand)
