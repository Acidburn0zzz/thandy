import os
import sys
import getopt

from difflib import unified_diff
from string import Template

thp_template = Template("""format_version = 1
package_name = "$thp_name"
package_version = "$version"
package_version_tuple = [$version_list]
files = [ 
$files
]

additional_files = [ ]
install_order = 50
options = { "cycle-install" : False }
platform = { "os" : "$os",
             "arch" : "$arch" }
require_features = [ "pythonscripts" ]
require_packages = []
scripts = { "python2" : 
              [ $scripts ]
          }
""")

def usage():
    print "Known commands:"
    print "  thpconfig --thp_name=AppName"
    print "            --version_list=1,2,3"
    print "            --scan=path/to/folder/"
    print "            --os=linux"
    print "            --arch=x86"
    print "            --scripts=\"['script1.py', ['preinst', 'postinst']],['script2.py', ['postinst']]\""
    print "            --old_file_list=path/to/oldfiles"
    print "            --generate_file_list=0|1"
    print "            --config_file_list=path/to/configfiles"
    sys.exit(1)

def get_files(top, configs):
    ready = []
    raw = []
    for root, dirs, files in os.walk(top):
        for f in files:
            is_config = "False"
            f_value = "/".join([root, f]).replace(top, "")
            if f_value in configs:
                is_config = "True"
            ready.append("(\"%s\", %s)," % (f_value, is_config))
            raw.append("/".join([root, f]).replace(top, ""))
    return ready, raw

def thpconfig(args):
    optlist, args = getopt.getopt(args, '', ["thp_name=",
                                             "version_list=",
                                             "scan=",
                                             "os=",
                                             "arch=",
                                             "scripts=",
                                             "old_file_list=",
                                             "generate_file_list=",
                                             "config_file_list="])

    mapping = {}
    scan_dir = ""
    old_file_list = ""
    config_file_list = ""
    generate_file_list = True
    for key, val in optlist:
        if key == "--scan":
            scan_dir = val
            continue
        if key == "--generate_file_list":
            generate_file_list = (val == "1")
            continue
        if key == "--old_file_list":
            old_file_list = val
            continue
        if key == "--config_file_list":
            config_file_list = val
            continue
        mapping[key[2:]] = val

    mapping["version"] = ".".join(mapping["version_list"].split(","))

    configs = []
    if len(config_file_list) != 0:
        configs = open(config_file_list, "r").read().split("\n")
        
    files, raw = get_files(scan_dir, configs)
    mapping["files"] = "\n".join(files)

    out = open("%s-%s_thp.cfg" % (mapping["thp_name"], mapping["version"]), "w")
    try:
        out.write(thp_template.substitute(mapping))
    except KeyError, e:
        print "You are missing the following parameter:", e
        sys.exit(1)
    out.close()

    if generate_file_list:
        file_list = open("%s-%s_thp.filelist" % (mapping["thp_name"], mapping["version"]), "w")
        file_list.write("\n".join(raw))
        file_list.close()

    if len(old_file_list) != 0:
        old = open(old_file_list, "r").read().split("\n")
        new = raw
        for line in unified_diff(old, new):
            print line

def main():
    if len(sys.argv) < 2:
        usage()
    cmd = sys.argv[1]
    args = sys.argv[2:]
    if cmd in [ "thpconfig" ]:
        globals()[cmd](args)
    else:
        usage()


if __name__ == "__main__":
    main()
