#!/usr/bin/python
#
# Citrix XenServer Patcher
version = "1.5.2"
# -- Designed to automatically review available patches from Citrix's XML API,
#    compare with already installed patches, and apply as necessary- prompting the user
#    to reboot/restart the XE ToolStack if necessary.
#
# Written by: Darren Gibbard
# URL:        http://dgunix.com
# Github:     http://github.com/dalgibbard/citrix_xenserver_patcher
#
#
# Written for Python 2.4 which is present in current XenServer 6.1/6.2+ Builds, but also somewhat
# tested against Python2.7 and 3.2 where possible for future compatibility.
#
# LICENSE:
# This code is governed by The WTFPL (Do What the F**k You Want to Public License).
# Do whatever you like, but I would of course appreciate it if you fork this code and commit back
# with any good updates though :)
#
# DISCLAIMER:
# Both myself and this code are in no way affiliated with Citrix. This code is not supported by Citrix in any way.
# Use of the code within this project is without warranty, and neither myself, the company I work for, nor other contributors of this project are to blame for any issues which may arise, and therefore cannot be held accountable.
# Any use of this code is done so at your own risk.

############################
### IMPORT MODULES START ###
############################
import sys, re, subprocess, os, getopt, time, pprint, signal
from xml.dom import minidom
from operator import itemgetter
try:
    # Python v2
    from urllib2 import urlopen
except ImportError:
    # Python v3
    from urllib.request import urlopen
############################
### IMPORT MODULES END ###
############################

###############################
### INITIAL FUNCTIONS START ###
###############################
### Capture Ctrl+C Presses
def signal_handler(signal, frame):
    print("Quitting.\n")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

#############################
### INITIAL FUNCTIONS END ###
#############################

############################
### USER VARIABLES START ###
############################
# Where we can find the XML page of available updates from Citrix
patchxmlurl = 'http://updates.xensource.com/XenServer/updates.xml'
# Where we can find auto-exclude files on the internet - filename expected is either:
## "XS${majver}${minver}${subver}_exclusions.py"   - ie. "XS621_excludes.py" for XenServer 6.2.1
## "XS${majver}${minver}_exclusions.py"            - ie. "XS62_excludes.py" for XenServer 6.2.1 (if the above doesn't exist) OR XenServer 6.2
autourl = 'https://raw.githubusercontent.com/dalgibbard/citrix_xenserver_patcher/master/exclusions'
# Where we can store some temporary data
tmpfile = '/tmp/xml.tmp'
##########################
### USER VARIABLES END ###
##########################

##############################
### NAGIOS VARIABLES Start ###
##############################
OK = 0
WARNING = 1
CRITICAL = 2
UNKNOWN = 3
############################
### NAGIOS VARIABLES End ###
############################

########################################
### SYSTEM / INITIAL VARIABLES START ###
########################################
# Setup empty List for later
L = []
# Specify empty excludes file -- when specified, this is a list of patches to IGNORE [opt: -e FILENAME ]
exclude_file = False
exclusions = False
autoexclusions = False
# Define "listonly" as False by Default -- when true, list patches needed, but quit straight after. [opt: -l ]
listonly = False
# Define "nagios" as False by Default -- when true, return Nagios codes for system monitoring, but quit straight after. [opt: -n ]
nagios = False
# Define "pool" as False by Default -- when true, patches are applied to a pool
pool = False
# Enable loading of the Auto-Excludes list from github.
autoExclude = True
# Disable debug by default
debug = False
# Add XE credentials
xeuser = ""
xepasswd = ""
xecliusr = ""
######################################
### SYSTEM / INITIAL VARIABLES END ###
######################################

#######################################
### USAGE + ARGUMENT HANDLING START ###
#######################################
## Define usage text
def usage(exval=1):
    print("Usage: %s [-e /path/to/exclude_file] [-E] [-u <username>] [-p <password>] [-n] [-D] [-v]" % sys.argv[0])
    print("")
    print("-e /path/to/exclude_file    => Allows user to define a Python List of Patches NOT to install.")
    print("-E                          => *Disable* the loading of auto-exclusions list from Github")
    print("-n                          => Check for available patches and return Nagios OK or WARN for system monitoring")
    print("-u <username>               => xe username - for nagios monitoring")
    print("-p <passwd>                 => xe password - for nagios monitoring")
    print("-D                          => Enable DEBUG output")
    print("-v                          => Display Version and Exit.")
    print("-h                          => Display this message and Exit.")
    sys.exit(exval)


# Parse Args:
try:
    myopts, args = getopt.getopt(sys.argv[1:],"vhe:Eu:p:nrD")
except getopt.GetoptError:
    usage()

for o, a in myopts:
    if o == '-v':
        # Version print and Quit.
        print("Citrix_XenServer_Patch_Checker_Version: " + str(version))
        sys.exit(0)
    if o == '-h':
        # Version print and Quit.
        usage(0)
    elif o == '-e':
        # Set the exclusion file
        exclude_file = str(a)
        # Check the file exists
        if not os.path.exists(exclude_file):
            # If it doesn't exist, Error and quit.
            print("Failed to locate requested excludes file: " + exclude_file)
            sys.exit(1)
        # Our exclusions list is raw python, so try running it.
        try:
            execfile(exclude_file)
        # If running it fails, it's not valid python
        except Exception, err:
            print("An error occurred whilst loading the exclude file: " + exclude_file)
            if debug == True:
                print("Error: " + str(err))
            sys.exit(1)
        # Check that the Python we just ran actually contains some valid exclusions!
        if exclusions == False:
            print("No exclusions found in the loaded exceptions file...")
            sys.exit(1)
    elif o == '-E':
        # Disable Auto-Exclusions list
        autoExclude = False
    elif o == '-u':
        # Disable Auto-Exclusions list
        xeuser = str(a)
    elif o == '-p':
        # Disable Auto-Exclusions list
        xepasswd = str(a)
    elif o == '-n':
        nagios = True
    elif o == '-D':
        debug = True
    else:
        usage()


if nagios == True and (xeuser == "" or xepasswd == ""):
    print("WARNING: Cannot use 'nagios' without 'user' and 'password'.")
    sys.exit(WARNING)

#####################################
### USAGE + ARGUMENT HANDLING END ###
#####################################

if debug == True:
    print("Citrix_XenServer_Patcher_Version: " + str(version))

##############################
### SCRIPT FUNCTIONS START ###
##############################
def listappend(name_label, patch_url, uuid, name_description="None", after_apply_guidance="None", timestamp="0", url="None"):
    ''' Function for placing collected/parsed Patch File information into a dictionary, and then into a List '''
    dict = { "name_label": name_label, "name_description": name_description, "patch_url": patch_url, "uuid": uuid, "after_apply_guidance": after_apply_guidance, "timestamp": timestamp, "url": url }
    if debug == True:
        print("Adding patch to list: " + str(dict))
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

## Function to pull Auto-Excludes file    
def getAutoExcludeList(autourl):
    # Build the full file URL:
    autourlfull = autourl + "/XS" + xsver + "_excludes.py"
            
    ### Start XML Grab + Parse
    try:
        # Get XML
        autoexclude_data = urlopen(autourlfull)
    except Exception, err:
        if not subver == "":
            try:
                if nagios == False:
                    print("Failed to locate Auto Exclusions file: XS" + xsver + "_excludes.py" )
                    print("Checking for presence of Parent version file: XS" + majver + minver + "_excludes.py  ...")
                autourlfull = autourl + "/XS" + majver + minver + "_excludes.py"
                # Get XML
                autoexclude_data = urlopen(autourlfull)
            except Exception, err:
                # Handle Errors
                if nagios == True:
                    print("WARNING: Failed to read Auto-Exclusion List from: " + autourlfull)
                    sys.exit(WARNING)
                else:
                    print("\nFailed to read Auto-Exclusion List from: " + autourlfull)
                    print("Check the URL is available, and connectivity is OK.")
                    print("")
                    print("Error: " + str(err))
                    print("")
                    print('NOTE: To proceed without downloading the Auto-Excludes file (not recommended), pass the "-E" flag.')
                    sys.exit(1)
        else:
            if nagios == True:
                print("WARNING: Failed to read Auto-Exclusion List from: " + autourlfull)
                sys.exit(WARNING)
            else:
                # Handle Errors
                print("\nFailed to read Auto-Exclusion List from: " + autourlfull)
                print("Check the URL is available, and connectivity is OK.")
                print("")
                print("Error: " + str(err))
                print("")
                print('NOTE: To proceed without downloading the Auto-Excludes file (not recommended), pass the "-E" flag.')
                sys.exit(1)

    # Set "autoexclude" to readable/printable page content.
    autoexclude = autoexclude_data.read()
    
    # Our exclusions list is raw python, so try running it.
    try:
        exec autoexclude
    # If running it fails, it's not valid python
    except Exception:
        if nagios == True:
            print("WARNING: An error occurred whilst loading the auto-exclude file from " + autourlfull)
            sys.exit(WARNING)
        else:
            print("An error occurred whilst loading the auto-exclude file from " + autourlfull)
            ys.exit(1)
    # Check that the Python we just ran actually contains some valid exclusions!
    if autoexclusions == False:
        if nagios == True:
            print("WARNING: No auto-exclusions found in the loaded exceptions file...")
            sys.exit(WARNING)
        else:
            print("No auto-exclusions found in the loaded exceptions file...")
            sys.exit(1)
    else:
        return autoexclusions
            
# Function to test that the xe utility is operational (#21)
def xetest():
    out = None
    err = None
    test_xe_cmd = str(xecli) + str(xecliusr) + str(' host-list')
    test_xe = subprocess.Popen([test_xe_cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    if debug == True:
        print("Testing XE CLI function using: " + test_xe_cmd)
    (out, err) = test_xe.communicate()
    if not err and out != None:
        return True
    else:
        return False
    
############################
### SCRIPT FUNCTIONS END ###
############################

#######################    
### MAIN CODE START ###
#######################
# Validate that we're running XenServer
relver = '/etc/xensource-inventory'
xs = False
xsver = None

# Open Filehandle to relver to check version
try:
    f = open(relver, "r")
    # If this file is openable, we can safely assume that it's a XenServer box
    xs = True
except IOError:
    if nagios == True:
        print("WARNING: Error Opening " + relver)
        sys.exit(WARNING)
    else:
        print("Error Opening " + relver)
    try:
        f.close()
    except NameError:
        pass
    sys.exit(11)

# Read the relver contents, and split into variables for the XenServer version.
shortver = None
try:
    for line in f:
        if re.search("PRODUCT_VERSION=", line):
            shortver = line.split("=")[1].replace("'", "")
    if shortver == None:
        if nagios == True:
            print("WARNING: Failed to identify Major/Minor XenServer Version.")
            sys.exit(WARNING)
        else:
            print("Failed to identify Major/Minor XenServer Version.")
            sys.exit(23)
    else:
        if nagios == False:
            print("Detected XenServer Version: " + shortver)
    majver = shortver.split('.')[0]
    minver = shortver.split('.')[1]
    # Provide 'xsver' for versions consisting of two and three segments. (eg: 6.2 vs 6.2.1)
    if len(shortver.split('.')) > 2:
        subver = shortver.split('.')[2].strip()
        if subver == '0':
            subver = ""
            xsver = str(majver) + str(minver)
        else:
            xsver = str(majver) + str(minver) + str(subver)
    if debug == True:
        print("xsver: " + xsver)
finally:
    f.close()

# Check that relver listed 'XenServer' in it's contents.
if xs == False:
    if nagios == True:
        print("WARNING: Failed to identify this host as a XenServer box.")
        sys.exit(WARNING)
    else:
        print("Failed to identify this host as a XenServer box.")
        sys.exit(4)
elif debug == True:
    print("XenServer machine identified.")

# Ensure we found a valid XenServer Version.
if xsver == None:
    if nagios == True:
        print("WARNING: Failed to identify XenServer Version.")
        sys.exit(WARNING)
    else:
        print("Failed to identify XenServer Version.")
        sys.exit(5)
elif debug == True:
    print("XenServer Version " + xsver + " detected.")

# Locate the 'xe' binary.
xecli = which("xe")
if xecli == None:
    if nagios == True:
        print("WARNING: Failed to locate the XE CLI Utility required for patching.")
        sys.exit(WARNING)
    else:
        print("Failed to locate the XE CLI Utility required for patching.")
        sys.exit(8)
elif debug == True:
    print("XE utility located OK")
if xeuser != "" and xepasswd != "":
    xecliusr = " -u " + xeuser + " -pw " + xepasswd
    
###FIXME
# Now validate that XE is working:
if not xetest():
    if nagios == False:
        print("XE CLI not responding.")
        sys.exit(99)
    else:
        print("WARNING: XE not responding. Quitting.")
        sys.exit(WARNING)
elif debug == True:
    print("XE working OK")
    
### Start XML Grab + Parse
try:
    # Get XML
    if debug == True:
        print("Downloading patch list XML")
    downloaded_data = urlopen(patchxmlurl)
except Exception, err:
    # Handle Errors
    if nagios == True:
        print("WARNING: Failed to read Citrix Patch List from: " + patchxmlurl)
        sys.exit(WARNING)
    else:
        print("\nFailed to read Citrix Patch List from: " + patchxmlurl)
        print("Check the URL is available, and connectivity is OK.")
        print("")
        print("Error: " + str(err))
        sys.exit(1)

# Set "data" to readable/printable page content.
data = downloaded_data.read()

#######################
# DEBUG - Show output #
#######################
if debug == True:
    print("-----------------------------")
    print("RAW XML OUTPUT:")
    print(data)
    print("-----------------------------")
#######################

# Output to tmpfile - Open file handle
try:
    t = open(tmpfile, "wb")
except IOError:
    if nagios == False:
        print("Error Opening " + tmpfile)
    try:
        t.close()
    except NameError:
        pass
    if nagios == True:
        print("WARNING: Error Opening " + tmpfile)
        sys.exit(WARNING)
    else:
        sys.exit(11)

# Output to tmpfile - Write Data + Close.
try:
    t.write(data)
finally:
    t.close()

if debug == True:
    print("XML written to " + tmpfile)    
    
# Parse XML to Vars
xmldoc = minidom.parse(tmpfile)
xmlpatches = xmldoc.getElementsByTagName('patch')

# remove tmp file
if os.path.exists(tmpfile):
	try:
		os.remove(tmpfile)
	except OSError, e:
		print ("Error: %s - %s." % (e.tmpfile,e.strerror))

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

## Validate that there is something defined in the Patch list... else quit.
if L == []:
    if nagios == True:
        print("WARNING: No Patches found on remote server for XS" + str(xsver))
        sys.exit(WARNING)
    else:
        print("No Patches found on remote server for XS" + str(xsver))
        sys.exit(6)

# OK, so now we have a complete list of patches that Citrix have to offer. Lets see what we have installed already,
# and remove those from the list we made above.

# First, we use a subprocess shell to get the local host's XenServer UUID
out = None
err = None
get_host_uuid_cmd = str(xecli) + str(xecliusr) + str(' host-list hostname=`grep "^HOSTNAME=" /etc/sysconfig/network | awk -F= \'{print$2}\'` params=uuid --minimal')
get_host_uuid = subprocess.Popen([get_host_uuid_cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
if debug == True:
    print("Getting host list using: " + get_host_uuid_cmd)
(out, err) = get_host_uuid.communicate()
if not err and out != None:
    HOSTUUID_utf8 = out.decode("utf8")
    HOSTUUID = str(HOSTUUID_utf8.replace('\n', ''))
    if debug == True:
        print("Detected HOST UUID: " + HOSTUUID)
else:
    if nagios == True:
        print("WARNING: Failed to get HostUUID from XE")
        sys.exit(WARNING)
    else:
        print("Failed to get HostUUID from XE")
        sys.exit(7)

if HOSTUUID == "" or HOSTUUID == ['']:
    if nagios == True:
        print("WARNING: Failed to obtain HOSTUUID from XE CLI")
        sys.exit(WARNING)
    else:
        print("Error: Failed to obtain HOSTUUID from XE CLI")
        sys.exit(10)

# Setup empty list to use in a moment:
inst_patch_list = []

out = None
err = None
if pool == True:
    get_inst_patch_cmd = str(xecli) + str(xecliusr) + str(' patch-list ') + str(' --minimal')
else:
    get_inst_patch_cmd = str(xecli) + str(xecliusr) + str(' patch-list hosts:contains="') + str(HOSTUUID) + str('" --minimal')
get_inst_patch = subprocess.Popen([get_inst_patch_cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
if debug == True:
    print("Get patch list using: " + get_inst_patch_cmd)
(out, err) = get_inst_patch.communicate()
if not err and out != None:
    inst_patch_utf8 = out.decode("utf8")
    inst_patch_str = str(inst_patch_utf8.replace('\n', ''))
    inst_patch_list = inst_patch_str.split(",")
else:
    if nagios == True:
        print("WARNING: Failed to get Patch List from XE")
        sys.exit(WARNING)
    else:
        print("Failed to get Patch List from XE")
        sys.exit(9)

#############
### DEBUG ###
#############
if debug == True:
    print("HOSTUUID: " + HOSTUUID)
    print("Installed Patches: " + str(inst_patch_list))
#############


##### TEST DEBUG:
if debug == True:
    print("Trying to establish which 'null' is correct. If you see an 'X MATCHED' message, please notify me on Github via an Issue!")
    ## A
    if inst_patch_list == []:
        print(" *** A MATCHED *** ")
    ## B
    if inst_patch_list == "":
        print(" *** B MATCHED *** ")
    ## C
    if inst_patch_list == ['']:
        print(" *** C MATCHED *** ")
##### END TEST DEBUG
    
# If there's no patches installed on this machine yet, tell the user (in case they were curious)
if inst_patch_list == [] or inst_patch_list == "" or inst_patch_list == ['']:
    if nagios == False:
        print("No Patches are currently installed.")
# Else; request that already installed patches are removed from the "to_be_installed" list:
else:
    for uuid in inst_patch_list:
        listremovedupe(uuid)
    
## Request, where necessary, that patches in the Exclusions file are removed.
if not exclusions == False:
    for namelabel in exclusions:
        listremoveexclude(namelabel)

# Load the AutoExcludes:
autoexclusions = getAutoExcludeList(autourl)
## Patches loaded in from the auto-exclude file to be removed from the list next:    
if not autoexclusions == False:
    for namelabel in autoexclusions:
        listremoveexclude(namelabel)
        
## Lastly, sort the data by timestamp (to get oldest patches installed first).
sortedlist = sorted(L, key=itemgetter('timestamp'))

# Reassign the sorted list back to the old variable, 'cos I liked that one better.
L = sortedlist

# Dump the list to a temporary string for mangling into a readable output:
var = str(L)
# Do the mangling on the string to be human readable.
vara = var.replace(',','\n').replace('{','\n').replace('}','').replace('[','').replace(']','').replace("'", "")
# If we're done mangling, and the var is empty, then we have no patches to install.
if vara == "":
    if nagios == True:
        print("OK: No Patches Required. System is up to date.")
        sys.exit(OK)
    else:
        print("No Patches Required. System is up to date.")
        sys.exit(0)

# If vara isn't empty, show the user a list of patches we're going to install.
if nagios == True:
    print("WARNING: Patches are pending")
    sys.exit(WARNING)
else:
    print("The following Patches are pending installation:")
    print(vara)

sys.exit(0)


