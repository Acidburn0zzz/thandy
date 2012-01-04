from string import Template
import sys
import getopt

package_template = Template("""name = "$app_name"
version = [$version_list]
location = "$location"
relpath = "$data"
ShortDesc('en',  "$short_desc")
LongDesc('en',
\"\"\"$long_desc\"\"\")
format = "$format"
thp_name = "$app_name"
thp_version = "$version"
thp_dest = "$dest" """)

bundle_template = Template("""name = "$bundle_name"
version = [$version_list]
location = "$bundle_location"
os = "$os"
arch = "$arch"
$packages
ShortGloss("en", "$short_gloss")
LongGloss("en", "$long_gloss") """)

package_list_template = Template("""Package(name="$app_name",
	order=(10,10,10),
	optional=False)""")

def packageconfig(args):
    optlist, args = getopt.getopt(args, '', ["app_name=",
                                             "version_list=",
                                             "location=",
                                             "short_desc=",
                                             "long_desc=",
                                             "dest="])

    mapping = {}
    for key, val in optlist:
        mapping[key[2:]] = val

    mapping["version"] = ".".join(mapping["version_list"].split(","))
    mapping["data"] = "/data/%s-%s.thp" % (mapping["app_name"], 
                                           mapping["version"])
    mapping["format"] = "thp"

    out = open("%s-%s_package.cfg" % (mapping["app_name"], mapping["version"]), "w")
    try:
        out.write(package_template.substitute(mapping))
    except KeyError, e:
        print "You are missing the following parameter:", e
        sys.exit(1)

    out.close()

def bundleconfig(args):
    optlist, args = getopt.getopt(args, '', ["bundle_name=",
                                             "version_list=",
                                             "bundle_location=",
                                             "os=",
                                             "arch=",
                                             "pkg_names=",
                                             "short_gloss=",
                                             "long_gloss="])

    mapping = {}
    pkg_names = []
    for key, val in optlist:
        if key == "--pkg_names":
            pkg_names = val.split(",")
            continue
        mapping[key[2:]] = val

    packages = ""
    for pkg in pkg_names:
        packages += "%s\n" % package_list_template.substitute({'app_name': pkg})

    mapping["packages"] = packages

    out = open("%s-%s_bundle.cfg" % (mapping["bundle_name"], ".".join(mapping["version_list"].split(","))), "w")
    try:
        out.write(bundle_template.substitute(mapping))
    except KeyError, e:
        print "You are missing the following parameter:", e
        sys.exit(1)

    out.close()

def usage():
    print "Known commands:"
    print "  packageconfig --app_name=AppName"
    print "                --version_list=1,2,3"
    print "                --location=/path/to/package.txt"
    print "                --short_desc=\"Short description\""
    print "                --long_desc=\"Long description\""
    print "                --dest=\"/relative/path/to/install/\""
    print "  bundleconfig  --bundle_name=BundleName"
    print "                --version_list=1,2,3"
    print "                --bundle_location=/path/to/bundle.txt"
    print "                --os=lin"
    print "                --arch=x86"
    print "                --pkg_names=\"package1,package2\""
    print "                --short_gloss=\"This is the short gloss\""
    print "                --long_gloss=\"This is the large glossary\""
    sys.exit(1)

def main():
    if len(sys.argv) < 2:
        usage()
    cmd = sys.argv[1]
    args = sys.argv[2:]
    if cmd in [ "packageconfig", "bundleconfig" ]:
        globals()[cmd](args)
    else:
        usage()

if __name__ == '__main__':
    main()
