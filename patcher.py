#!/usr/bin/python
#
# Written for Python 2.4 which is present in current XenServer 6.1/6.2+ Builds
#
# No real license here... Do whatever. I'd appreciate it if you fork this code and commit back
# with any good updates though :)
#


#def somethingfunc(applyguide=restartHost, name, description="No Description", url, timestamp=None, infourl=None, uuid):
#        self.applyguide = applyguide
#        self.
#    ''' This Class allows us to store, call and manage our Patch Files information. '''
 
### IMPORT MODULES
import sys, re, subprocess, os
from xml.dom import minidom
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

### FUNCTIONS START
def listappend(name_label, patch_url, uuid, name_description="None", after_apply_guidance="None", timestamp="None", url="None"):
    ''' Function for placing collected/parsed Patch File information into a dictionary, and then into a List '''
    dict = { "name_label": name_label, "name_description": name_description, "patch_url": patch_url, "uuid": uuid, "after_apply_guidance": after_apply_guidance, "timestamp": timestamp, "url": url }
    #### DEBUG
    #print("Printing dict:")
    #print(dict)
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
except (urllib2.HTTPError, urllib2.URLError):
    # Handle Errors
    print("Failed to read Citrix Patch List from: " + patchxmlurl)
    print("Check the URL is available, and connectivity is OK.")
    print("")
    print("Error: " + err)
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
get_host_uuid_cmd = str(xecli) + str(" host-list params=uuid --minimal")
get_host_uuid = subprocess.Popen([get_host_uuid_cmd], stdout=subprocess.PIPE, shell=True)
(out, err) = get_host_uuid.communicate()
if err == None and out != None:
    HOSTUUID_utf8 = out.decode("utf8")
    HOSTUUID = str(HOSTUUID_utf8.replace('\n', ''))
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
get_inst_patch_cmd = str(xecli) + str(" patch-list hosts=") + str(HOSTUUID) + str(" --minimal")
get_inst_patch = subprocess.Popen([get_inst_patch_cmd], stdout=subprocess.PIPE, shell=True)
(out, err) = get_inst_patch.communicate()
if err == None and out != None:
    inst_patch_utf8 = out.decode("utf8")
    inst_patch_str = str(inst_patch_utf8.replace('\n', ''))
    inst_patch_list = inst_patch_str.split(",")
else:
    print("Failed to get Patch List from XE")
    sys.exit(9)

### DEBUG
print("HOSTUUID: " + HOSTUUID)
print("Installed Patches: " + str(inst_patch_list))

if inst_patch_list == [] or inst_patch_list == "" or inst_patch_list == ['']:
    print("No local Patches are installed.")
for uuid in inst_patch_list:
    listremovedupe(uuid)


var = str(L)
vara = var.replace(',','\n').replace('{','\n\n').replace('}','').replace('[','').replace(']','')
if vara == "":
    print("No Patches Required. System is up to date.")
else:
    print("The following Patches are pending installation:")
    print(vara)
