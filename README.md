citrix_xenserver_patcher
========================

Auto Patching tool for Citrix XenServer Boxes

Supports XenServer 6.0+ - designed primarily for 6.2+ where easy patch management via the GUI was removed
for non-supported customers. This should allow individuals and the likes to patch their systems with ease.

Currently, this script is used directly on the Hypervisor itself (as root), and is tested working with both standalone nodes, and pools (must be run on the pool master!).

If there is a particular feature (or bug!) you want sorted, please feel free to raise an Issue here, and i'll look into it (or feel free to fork and commit fixes back!): https://github.com/dalgibbard/citrix_xenserver_patcher/issues

## DISCLAIMER
Both myself and this code are in no way affiliated with Citrix. This code is not supported by Citrix in any way.
Use of the code within this project is without warranty, and neither myself, the company I work for, nor other contributors of this project are to blame for any issues which may arise, and therefore cannot be held accountable.
Any use of this code is done so at your own risk.

Anyway; enough of the nasty stuff.

## How To Use
* SSH to your XenServer Host (Use PuTTY if using a Windows PC).
* Ensure you're logged on as the "root" user.
* Get the XenServer Patcher Script
* Set the permissions as executable
* OPTIONAL: Create your own exclusions file. (Exclusions will be loaded from Github, but feel free to produce your own list too.)
* Run it!

```
wget --no-check-certificate -O patcher.py https://raw.github.com/dalgibbard/citrix_xenserver_patcher/master/patcher.py
chmod a+x patcher.py

# Standalone node:
./patcher.py

# Pool Master node:
./patcher.py -p
```

* Run the patcher, and follow the prompts :)

## A Note On Exclusions
Exclusions are necessary, particularly when Citrix release a Service Pack update which combines previously released patches (be sure to check the "to-be-installed" list for any "SP" patches, and report them if they're new!)

Exclusions are defined in two different ways, which can be utilised together, or individually.
### Auto Exclusions
Automatic Exclusions are provided within the 'exclusions' directory of this project by default. Please raise an issue, or raise a pull request with appropriate changes if you find anything to be wrong/missing.
Auto-Exclusions can be _DISABLED_ by using the ```-E``` flag, like so:
```
## NOTE: ** NOT RECOMMENDED! **
./patcher.py -E
```
### Local / Manual Exclusions
If you want to define your own list of patches to exclude, you can do so by providing the ```-e``` argument, and an appropriately formatted file.
For an example of how this file should be formatted; see: *local_exclusions_example.py*

Example on using this flag:
```
## Use a manual exclusions file, in _addition_ to the Auto-Exclusions file on Github:
./patcher.py -e /path/to/exclusions_file.py

## Use ONLY the manual exclusions file:
./patcher.py -E -e /path/to/exclusions_file.py
```

## Usage:
* The code supports a few other arguments too:

```bash
Usage: ./patcher.py [-p] [-e /path/to/exclude_file] [-E] [-a] [-r] [-l] [-D] [-C] [-v]

-p                          => POOL MODE: Apply Patches to the whole Pool. It must be done on the Pool Master.
-e /path/to/exclude_file    => Allows user to define a Python List of Patches NOT to install.
-E                          => *Disable* the loading of auto-exclusions list from Github
-a                          => Enables auto-apply of patches - will NOT reboot host without below option.
-r                          => Enables automatic reboot of Host on completion of patching without prompts.
-l                          => Just list available patches, and Exit. Cannot be used with '-a' or '-r'.
-D                          => Enable DEBUG output
-C                          => *Disable* the automatic cleaning of patches on success.
-v                          => Display Version and Exit.
```

Tags: XenServer Citrix Patch Patching Patcher Auto-Patcher Autopatcher Xen Server Python
