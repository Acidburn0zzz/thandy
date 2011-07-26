# Copyright 2008 The Tor Project, Inc.  See LICENSE for licensing information.

import os

def getItemsFromPackage(pkg):
    """Given a Thandy package decoded from its json format, return a dict
       with an entry for each installable item in the path, mapping the
       item's relative path to a PackageItem object that can check or
       install that item.
    """
    result = {}
    format = pkg.get('format')
    for item in pkg['files']:
        relPath = item[0]
        if len(item) >= 3:
            extra = item[2]
        else:
            extra = {}
        checker = getChecker(relPath, extra, defaultFormat=format,
                             package=pkg)
        installer = getInstaller(relPath, extra,
                                 defaultFormat=format, package=pkg)
        result[relPath] = PackageItem(relPath, checker, installer)
    return result

def getChecker(relPath, extra, defaultFormat, package):
    """Return a Checker instance for an item in a package, or None if we
       don't know how to check that item.

         relPath -- the item's relative path in the repository.
         extra -- the info part of the item's entry in the package.
         defaultFormat -- the value of the package's "format" field.
            Only used for obsolete checker types.
         package -- the package object itself.  Only used for obsolete
            checker types.
    """
    checkType = extra.get("check_type")
    if checkType == None:
        # This part is for obsolete packages.
        if defaultFormat == 'rpm':
            import thandy.packagesys.RPMPackages
            return thandy.packagesys.RPMPackages.RPMChecker(
                os.path.split(relPath)[1],
                extra['rpm_version'])
        elif defaultFormat == 'exe':
            if extra.has_key('registry_ent'):
                import thandy.packagesys.ExePackages
                k,v=extra['registry_ent']
                return thandy.packagesys.ExePackages.RegistryChecker(k, v)
            else:
                import thandy.packagesys.PackageDB
                return thandy.packagesys.PackageDB.DBChecker(
                    package['name'], package['version'])
        elif defaultFormat == 'thp':
            # TODO: create checker here!
            pass
        else:
            return None
    elif checkType == 'rpm':
        import thandy.packagesys.RPMPackages
        return thandy.packagesys.RPMPackages.RPMChecker(
            os.path.split(relPath)[1],
            extra['rpm_version'])
    elif checkType == 'db':
        import thandy.packagesys.PackageDB
        return thandy.packagesys.PackageDB.DBChecker(
            extra['item_name'], extra['item_version'])
    elif checkType == 'registry':
        import thandy.packagesys.ExePackages
        k,v=extra['registry_ent']
        return thandy.packagesys.ExePackages.RegistryChecker(k,v)
    elif checkType == 'thp':
        print "Getting thp checker"
        import thandy.packagesys.ThpPackages
        return thandy.packagesys.ThpPackages.ThpChecker(
            extra['thp_name'], extra['thp_version'])
    else:
        return None

def getInstaller(relPath, extra, defaultFormat, package):
    """Return an Installer for an item in a package, or None if we don't
       know how to install that item.  Arguments are as for getChecker().
    """
    installType = extra.get("install_type")

    if installType == None:
        # This part is for obsolete packages.
        if defaultFormat == 'rpm':
            import thandy.packagesys.RPMPackages
            return thandy.packagesys.RPMPackages.RPMInstaller(
                relPath, os.path.split(relPath)[1])
        elif defaultFormat == 'exe':
            import thandy.packagesys.ExePackages
            installer = thandy.packagesys.ExePackages.CommandInstaller(
                relPath, [ "${FILE}" ] + extra.get('exe_args', []))
            if not extra.has_key('registry_ent'):
                import thandy.packagesys.PackageDB
                installer = thandy.packagesys.PackageDB.DBInstaller(
                    package['name'], package['version'], relPath, installer)
            return installer
        else:
            return None
    elif installType == 'rpm':
        import thandy.packagesys.RPMPackages
        installer = thandy.packagesys.RPMPackages.RPMInstaller(
            relPath, os.path.split(relPath)[1])
    elif installType == 'command':
        import thandy.packagesys.ExePackages
        installer = thandy.packagesys.ExePackages.CommandInstaller(
            relPath, extra['cmd_install'], extra.get('cmd_remove'))
    elif installType == 'thp':
        print "Getting thp installer"
        import thandy.packagesys.ThpPackages
        installer = thandy.packagesys.ThpPackages.ThpInstaller(
            relPath)
    else:
        return None

    if extra.get('check_type') == 'db':
        import thandy.packagesys.PackageDB
        installer = thandy.packagesys.PackageDB.DBInstaller(
            extra['item_name'], extra['item_version'], installer)

    return installer

class PackageItem:
    """Represents a single item from a package."""
    def __init__(self, relativePath, checker, installer):
        self._relPath = relativePath
        self._checker = checker
        self._installer = installer

    def getRelativePath(self):
        """DOCDOC"""
        return self._relPath

    def setTransaction(self, transaction):
        """Set the transaction context for this item to 'transaction'.
        """
        if self._checker is not None:
            self._checker.setTransaction(transaction)
        if self._installer is not None:
            self._installer.setTransaction(transaction)
    def setCacheRoot(self, cacheRoot):
        """Tell this item to look for files relative to 'cacheRoot'."""
        if self._installer is not None:
            self._installer.setCacheRoot(cacheRoot)

    def canCheck(self):
        """Return true iff we know how to check if this item is installed."""
        return self._checker != None
    def canInstall(self):
        """Return true iff we know how to install this item."""
        return self._installer != None
    def getChecker(self):
        return self._checker
    def getInstaller(self):
        return self._installer

class Checker:
    """Abstract base class.  A Checker knows how to detect whether a given
       installable item is installed, and how to tell what version is installed.

       All version checking functions may raise CheckNotSupported if they need
       an OS-dependent package detection mechanism that we don't have.
       Examples include checking the Windows Registry on a non-win32 platform.
    """
    def __init__(self):
        self._transaction = None

    def setTransaction(self, transaction):
        """Associate this Checker with a given transaction.  Future actions
           will take place in the given transaction context, if this Checker
           supports transactions.
        """
        self._transaction = transaction

#    def checkInstall(self):
#        raise NotImplemented()

    def anyVersionInstalled(self):
        """Return true iff any version of this item is installed."""
        raise len(self.getInstalledVersions()) > 1

    def getInstalledVersions(self):
        """Return a list of all versions of this item that are
           installed.  Version types are item-dependent: a tuple or a
           string is most common.
        """
        raise NotImplemented()

    def isInstalled(self):
        """Return true iff this particular version of this item is installed.
        """
        raise NotImplemented()

class Installer:
    """Abstract base class.  An Installer knows how to install or remove an
       installable item.
    """
    def __init__(self, relativePath):
        self._transaction = None
        self._cacheRoot = None
        self._relPath = relativePath

    def setTransaction(self, transaction):
        """Associate this Installer with a given transaction.  Future actions
           will take place in the given transaction context, if this Checker
           supports transactions.
        """
        self._transaction = transaction

    def setCacheRoot(self, cacheRoot):
        """Associate this Installer with a given cache root directory.  It
           looks for downloaded files under this directory.
        """
        self._cacheRoot = cacheRoot

    def getFilename(self):
        """Return the absolute pathname for this installable item as cached
           on disk.
        """
        rp = self._relPath
        if rp.startswith('/'):
            rp = rp[1:]
        return os.path.normpath(os.path.join(self._cacheRoot, rp))

    def install(self):
        """Install the item from the cache.  May raise InstallFailed if we
           the installation failed.
        """
        raise NotImplemented()

    def remove(self):
        """Remove the installed item.  May raise RemoveNotSupported"""
        raise NotImplemented()

    def getInstallResult(self):
        "DOCDOC params, manifest"
        return None, None


