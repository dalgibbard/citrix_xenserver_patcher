#!/usr/bin/python
#
# Citrix XenServer Patcher
version = 1.3
# -- Designed to automatically review available patches from Citrix's XML API,
#    compare with already installed patches, and apply as necessary- prompting the user
#    to reboot if necessary.
#
# Written by: Darren Gibbard
# URL:        http://dgunix.com
# Github:     http://github.com/dalgibbard/citrix_xenserver_patcher
#
# To Do: 
#   * Improve code layout
#   * Increase code comments to help others understand WTF is going on.
#
# Written for Python 2.4 which is present in current XenServer 6.1/6.2+ Builds, but also
# tested against Python2.7 and 3.2 where possible for future compatibility.
#
# LICENSE:
# This code is goverened by The WTFPL (Do What the F**k You Want to Public License).
# Do whatever you like, but I would of course appreciate it if you fork this code and commit back
# with any good updates though :)
#

### IMPORT MODULES
import sys, re, subprocess, os, getopt, time, pprint
from xml.dom import minidom
from operator import itemgetter
try:
    # Python v2
    from urllib2 import urlopen
except ImportError:
    # Python v3
    from urllib.request import urlopen

### USER VARS
# Where we can find the XML page of available updates from Citrix
patchxmlurl = 'http://updates.xensource.com/XenServer/updates.xml'
# Where we can store some temporary data
tmpfile = '/var/tmp/xml.tmp'

### INITIAL VARS
# Setup empty List for later
L = []
# Specify empty excludes file -- when specified, this is a list of patches to IGNORE [opt: -e FILENAME ]
exclude_file = False
exclusions = False
# Define "auto" as False by default -- when true, apply patches without question. [opt: -a ]
auto = False
# Define "reboot" as False by default. -- when true, if patches installed require host reboot, this will be done automatically!
autoreboot = False
# Define "listonly" as False by Default -- when true, list patches needed, but quit straight after. [opt: -l ]
listonly = False

## Define usage text
def usage():
    print("Usage: %s [-e /path/to/exclude_file] [-a] [-r] [-l] [-v]" % sys.argv[0])
    print("")
    print("-e /path/to/exclude_file    => Allows user to define a Python List of Patches NOT to install.")
    print("-a                          => Enables auto-apply of patches - will NOT reboot host without below option.")
    print("-r                          => Enables automatic reboot of Host on completion of patching without prompts.")
    print("-l                          => Just list available patches, and Exit. Cannot be used with '-a' or '-r'.")
    print("-v                          => Display Version and Exit.")
    sys.exit(1)


# Parse Args:
try:
    myopts, args = getopt.getopt(sys.argv[1:],"ve:alr")
except getopt.GetoptError:
    usage()

for o, a in myopts:
    if o == '-v':
        print("Citrix_XenServer_Patcher_Version: " + str(version))
        sys.exit(0)
    elif o == '-e':
        exclude_file = str(a)
        if not os.path.exists(exclude_file):
            print("Failed to locate requested excludes file: " + exclude_file)
            sys.exit(1)
	try:
            execfile(exclude_file)
        except Exception:
            print("An error occured whilst loading the exclude file: " + exclude_file)
            sys.exit(1)
        if exclusions == False:
            print("No exclusions found in the loaded exceptions file...")
            sys.exit(1)
    elif o == '-a':
        auto = True
        if listonly == True:
            print("Cannot use 'list' with 'auto' or 'autoreboot' arguments.")
            print("")
            usage()
    elif o == '-r':
        autoreboot = True
        if listonly == True:
            print("Cannot use 'list' with 'auto' or 'autoreboot' arguments.")
            print("")
            usage()
    elif o == '-l':
        listonly = True
        if auto == True or autoreboot == True:
            print("Cannot use 'list' with 'auto' or 'autoreboot' arguments.")
            print("")
            usage()
    else:
        usage()

### FUNCTIONS START
def listappend(name_label, patch_url, uuid, name_description="None", after_apply_guidance="None", timestamp="0", url="None"):
    ''' Function for placing collected/parsed Patch File information into a dictionary, and then into a List '''
    dict = { "name_label": name_label, "name_description": name_description, "patch_url": patch_url, "uuid": uuid, "after_apply_guidance": after_apply_guidance, "timestamp": timestamp, "url": url }
    L.append(dict)

def listremovedupe(uuid):
    ''' Function to compare the list formed by the function above, to see if a passed patch UUID already exists; and
        if it does, remove it from the list (as it's already installed.) '''
    try:
        # Python v2
        patch_to_remove = (patch for patch in L if patch["uuid"] == uuid ).next()
    except AttributeError:
        # Python v3
        patch_to_remove = next((patch for patch in L if patch["uuid"] == uuid ), None)
    except StopIteration:
        pass
    try:
        L.remove(patch_to_remove)
    except UnboundLocalError:
        pass

def listremoveexclude(namelabel):
    ''' Similar to above function - but this will remove items from the "to_be_installed" list based on name-label
        instead of UUID. '''
    try:
        # Python v2
        patch_to_remove = (patch for patch in L if patch["name_label"] == namelabel ).next()
    except AttributeError:
        # Python v3
        patch_to_remove = next((patch for patch in L if patch["name_label"] == namelabel ), None)
    except StopIteration:
        pass
    try:
        L.remove(patch_to_remove)
    except UnboundLocalError:
        pass
    

def which(program):
    ''' Function for establishing if a particular executable is available in the System Path; returns full
        exec path+name on success, or None on fail. '''
    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            path = path.strip('"')
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file

    return None

def download_patch(patch_url):
    url = patch_url
    file_name = url.split('/')[-1]
    print("Downloading: " + str(file_name))
    try:
        u = urlopen(url)
    except Exception, err:
        print("Failed to Download Patch!")
        print("Error: " + str(err))
        sys.exit(3)
        
    try:
        f = open(file_name, 'wb')
    except IOError:
        print("Failed to open/write to " + file_name)
        sys.exit(2)

    meta = u.info()
    file_size = int(meta.getheaders("Content-Length")[0])
    print "Download Size: %s Bytes" % (file_size)
    
    file_size_dl = 0
    block_sz = 8192
    while True:
        buffer = u.read(block_sz)
        if not buffer:
            break
        file_size_dl += len(buffer)
        f.write(buffer)
        status = r"%10d  [%3.2f%%]" % (file_size_dl, file_size_dl * 100. / file_size)
        status = status + chr(8)*(len(status)+1)
        print status,
    f.close()
    if not os.path.isfile(file_name):
        print("\nERROR: File download for " + str(file_name) + " unsuccessful.")
        sys.exit(15)
    return file_name

def apply_patch(name_label, uuid, file_name, host_uuid):
    print("\nApplying: " + str(name_label))
    print("Uncompressing...")
    patch_unzip_cmd = str("unzip -u ") + str(file_name)
    ### Ready for patch extract
    out = None
    err = None
    do_patch_unzip = subprocess.Popen([patch_unzip_cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    (out, err) = do_patch_unzip.communicate()
    if (err and out != None ):
        print("Error extracting compressed patchfile: " + str(file_name))
    os.remove(file_name)
    uncompfile = str(name_label) + str(".xsupdate")
    # Check {name_label}.xsupdate exists
    if not os.path.isfile(uncompfile):
        print("Failed to locate unzipped patchfile: " + str(uncompfile))
        sys.exit(16)
    # Internal upload to XS patcher
    print("Internal Upload...")
    patch_upload_cmd = str(xecli) + str(" patch-upload file-name=") + str(uncompfile)
    do_patch_upload = subprocess.Popen([patch_upload_cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    # On Python 2.4 check_* functions have not been yet implemented. Lets wait until Popen completes and read out the return code
    do_patch_upload.wait()
    (out, err) = do_patch_upload.communicate()
    # Upload may fail if file has previously already been uploaded but not applied
    if (err):
        print("XE Error detected: " + err)
        print("Return code is: " + str(do_patch_upload.returncode))
        error_block = err.split('\n')
        if (do_patch_upload.returncode == 1 and error_block[0] == "The uploaded patch file already exists"):
            print("Patch previously uploaded, attempting to reapply " + str(uuid))
            uuid = error_block[1]
        else:        
            print("New error detected, aborting")
            sys.exit(123)
    else:
        # Second verification.
        out = None
        err = None
        patch_upload_uuid = None
        #Do not pass hostuuid here as the patch has not been applied yet and the patch-list for SRO will come back empty
        patch_upload_verify_cmd = str(xecli) + str(' patch-list params=uuid uuid=') + str(uuid) + str(" --minimal")
        do_patch_upload_verify = subprocess.Popen([patch_upload_verify_cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        (out, err) = do_patch_upload_verify.communicate()
    
        if (err):
            print("Failed to validate the uploaded patch: " + str(uncompfile) + "\nError: " + str(err))
            sys.exit(17)
        else:
            print("Completed: " + str(out))

        patch_upload_uuid_utf8 = out.decode("utf8")
        patch_upload_uuid = str(patch_upload_uuid_utf8.replace('\n', ''))
        patch_upload_uuid.rstrip('\r\n')
        if not ( patch_upload_uuid != None and patch_upload_uuid == uuid ):
            print("Patch internal upload failed for: " + str(uncompfile))
            print("patch_upload_uuid = " + str(patch_upload_uuid))
            print("uuid = " + str(uuid))
            print("out = " + str(out))
            sys.exit(16)
    
    print("Applying Patch " + str(uuid))
    patch_apply_cmd = str(xecli) + str(" patch-apply uuid=") + str(uuid) + str(" host-uuid=") + str(host_uuid)
    do_patch_apply = subprocess.Popen([patch_apply_cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    (out, err) = do_patch_apply.communicate()
    if (err):
        print("Patch failed, code: " + str(do_patch_apply.returncode))
        print("Command failed: " + patch_apply_cmd)
        print("Failed to apply patch: " + str(err))
        print("Secondary check...")

    out = None
    err = None
    patch_apply_verify_cmd = str(xecli) + str(' patch-list hosts="') + str(host_uuid) + str('" params=uuid uuid=') + str(uuid) + str(" --minimal")
    do_patch_apply_verify = subprocess.Popen([patch_apply_verify_cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    (out, err) = do_patch_apply_verify.communicate()
    if (err):
        print("Failed to validate installed patch: " + str(uncompfile))
        sys.exit(18)
    patch_apply_uuid_utf8 = out.decode("utf8")
    patch_apply_uuid = str(patch_apply_uuid_utf8.replace('\n', ''))
    if not ( patch_apply_uuid != None and patch_apply_uuid == uuid ):
        print("Patch apply failed for: " + str(uncompfile))
        sys.exit(19)
    os.remove(uncompfile)

### CODE START
# Validate that we're running XenServer
relver = '/etc/redhat-release'
xs = False
xsver = None

# Open Filehandle to relver to check version
try:
    f = open(relver, "r")
except IOError:
    print("Error Opening " + relver)
    try:
        f.close()
    except NameError:
        pass
    sys.exit(11)

try:
    filedata = str(f.read().replace('\n', ''))
    file_list = filedata.split()
    ### DEBUG
    #print(file_list)
    if "XenServer" or "Xenserver" in file_list:
        xs = True
        fullver = file_list[2]
        shortver = fullver.split("-")[0]
        if len(shortver.split('.')) > 2:
            if shortver.split('.')[2] == "0":
                majver = shortver.split('.')[0]
                minver = shortver.split('.')[1]
                xsver = str(majver) + str(minver)
            else:
                majver = shortver.split('.')[0]
                minver = shortver.split('.')[1]
                subver = shortver.split('.')[2]
                xsver = str(majver) + str(minver) + str(subver)
finally:
    f.close()

if xs == False:
    print("Failed to identify this host as a XenServer box.")
    sys.exit(4)

if xsver == None:
    print("Failed to identify XenServer Version.")
    sys.exit(5)

xecli = which("xe")
if xecli == None:
    print("Failed to locate the XE CLI Utility required for patching.")
    sys.exit(8)

try:
    # Get XML
    downloaded_data = urlopen(patchxmlurl)
except Exception, err:
    # Handle Errors
    print("\nFailed to read Citrix Patch List from: " + patchxmlurl)
    print("Check the URL is available, and connectivity is OK.")
    print("")
    print("Error: " + str(err))
    sys.exit(1)

# Set "data" to readable/printable page content.
data = downloaded_data.read()

# DEBUG - Show output
#print(data)

# Output to tmpfile
try:
    t = open(tmpfile, "wb")
except IOError:
    print("Error Opening " + relver)
    try:
        t.close()
    except NameError:
        pass
    sys.exit(11)
    
try:
    t.write(data)
finally:
    t.close()

# Parse XML to Vars
xmldoc = minidom.parse(tmpfile)
xmlpatches = xmldoc.getElementsByTagName('patch')

#Convert xsver to a string for use in regex
xsverstr = str(xsver)

### Parse Vars for each patch to a Dict, and add each Dict (PLUS) to the List
for s in xmlpatches:
    try:
        patchname = s.attributes['name-label'].value
    except KeyError:
        continue
    vermatch = "XS" + xsverstr
    if re.match(vermatch, patchname):
        # Set the name-label (Patch Filename)
        name_label = str(s.attributes['name-label'].value)
        # Set the patch-url (Where to download it from)
        patch_url = str(s.attributes['patch-url'].value)
        # Set the uuid (ID of the Patch)
        uuid = str(s.attributes['uuid'].value)
        # Set the name-description (What it fixes)
        name_description = str(s.attributes['name-description'].value)
        # Set the after-apply-guidance (What to do with the host once installed)
        try:
            after_apply_guidance = str(s.attributes['after-apply-guidance'].value)
        except KeyError:
            after_apply_guidance = None
        # Set the timestamp (when the patch was made available)
        try:
            timestamp = str(s.attributes['timestamp'].value)
        except KeyError:
            timestamp = None
        # Set the url (URL where Patch information can be found)
        try:
            url = str(s.attributes['url'].value)
        except KeyError:
            url = None
        
        # PUSH TO LIST
        listappend(name_label, patch_url, uuid, name_description, after_apply_guidance, timestamp, url)

## Validate that there is something defined... else quit.
if L == []:
    print("No Patches found on remote server for XS" + str(xsver))
    sys.exit(6)

# OK, so now we have a complete list of patches that Citrix have to offer. Lets see what we have installed already,
# and remove those from the list we made above.

out = None
err = None
get_host_uuid_cmd = str('for ip in `ip addr show | awk /"scope global"/\'{print$2}\' | awk -F/ \'{print$1}\'`; do uuid="`') + str(xecli) + str(' host-list address=$ip params=uuid --minimal | head -n1` $uuid"; done; echo $uuid | awk \'{print$1}\'')
get_host_uuid = subprocess.Popen([get_host_uuid_cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
print("Getting host list using: " + get_host_uuid_cmd)
(out, err) = get_host_uuid.communicate()
if not err and out != None:
    HOSTUUID_utf8 = out.decode("utf8")
    HOSTUUID = str(HOSTUUID_utf8.replace('\n', ''))
    print("Detected HOST UUID: " + HOSTUUID)
else:
    print("Failed to get HostUUID from XE")
    sys.exit(7)

if HOSTUUID == "" or HOSTUUID == ['']:
    print("Error: Failed to obtain HOSTUUID from XE CLI")
    sys.exit(10)

# Setup empty list:
inst_patch_list = []

out = None
err = None
get_inst_patch_cmd = str(xecli) + str(' patch-list hosts="') + str(HOSTUUID) + str('" --minimal')
get_inst_patch = subprocess.Popen([get_inst_patch_cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
print("Get patch list using: " + get_inst_patch_cmd)
(out, err) = get_inst_patch.communicate()
if not err and out != None:
    inst_patch_utf8 = out.decode("utf8")
    inst_patch_str = str(inst_patch_utf8.replace('\n', ''))
    inst_patch_list = inst_patch_str.split(",")
else:
    print("Failed to get Patch List from XE")
    sys.exit(9)

### DEBUG
#print("HOSTUUID: " + HOSTUUID)
#print("Installed Patches: " + str(inst_patch_list))

# Should probably clean this line to whatever actually works... :)
if inst_patch_list == [] or inst_patch_list == "" or inst_patch_list == ['']:
    print("No local Patches are installed.")
## Request that already installed patches are removed from the "to_be_installed" list:
for uuid in inst_patch_list:
    listremovedupe(uuid)
## Request, where necessary, that patches in the Exclusions file are removed.
if not exclusions == False:
    for namelabel in exclusions:
        listremoveexclude(namelabel)
## Lastly, sort the data by timestamp (to get oldest patches installed first).
sortedlist = sorted(L, key=itemgetter('timestamp'))
# Reassign the sorted list back to the old variable, 'cos i liked that one better.
L = sortedlist


var = str(L)
vara = var.replace(',','\n').replace('{','\n').replace('}','').replace('[','').replace(']','').replace("'", "")
if vara == "":
    print("No Patches Required. System is up to date.")
    sys.exit(0)

print("The following Patches are pending installation:")
print(vara)

# If the user just wanted a list, quit now.
if listonly == True:
    sys.exit(0)

reboot = 0
for a in L:
    if str(a['after_apply_guidance']) == "restartHost":
        reboot = reboot + 1

if reboot > 0:
    print("\nNOTE: Installation of these items will require a reboot!")
    if not autoreboot == True:
        print("      You will be prompted to reboot at the end.")
        print("")
    time.sleep(2)

if not auto == True:
    ans = raw_input("\nWould you like to install these items? [y/n]: ")
    if str(ans) == "y" or str(ans) == "yes" or str(ans) == "Yes" or str(ans) == "Y" or str(ans) == "YES":
        print("Starting patching...")
    else:
        print("You didn't want to patch...")
        sys.exit(0)

for a in L:
   uuid = str(a['uuid'])
   patch_url = str(a['patch_url'])
   name_label = str(a['name_label'])
   file_name = str(download_patch(patch_url))
   host_uuid = str(HOSTUUID)
   apply_patch(name_label, uuid, file_name, host_uuid)

if reboot > 0:
    if not autoreboot == True:
        ans = raw_input("\nA reboot is now required. Would you like to reboot now? [y/n]: ")
        if str(ans) == "y" or str(ans) == "yes" or str(ans) == "Yes" or str(ans) == "Y" or str(ans) == "YES":
            print("Rebooting...")
            os.system("reboot")

        else:
            print("OK, i'll let you reboot in your own time. Don't forget though!")
    else:
        print("Rebooting...")
        os.system("reboot")
else:
    print("Restarting XAPI Toolstack...")
    os.system("xe-toolstack-restart")
