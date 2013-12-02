citrix_xenserver_patcher
========================

Auto Patching tool for Citrix XenServer Boxes

Supports XenServer 6.0+ - designed primarily for 6.2+ where easy patch management via the GUI was removed
for non-supported customers. This should allow individuals and the likes to patch their systems with ease.

Currently, this script is used directly on the Hypervisor itself (as root), and hasn't been designed with pools in mind...
If there is a particular feature (or bug!) you want sorted, please feel free to raise an Issue here, and i'll look into it (or feel free to fork and commit fixes back!): https://github.com/dalgibbard/citrix_xenserver_patcher/issues

## How To Use
* SSH to your XenServer Host (Use PuTTY if using a Windows PC).
* Ensure you're logged on as the "root" user.
* Get the XenServer Patcher Script:
```
wget -O patcher.py https://raw.github.com/dalgibbard/citrix_xenserver_patcher/master/patcher.py
chmod +x patcher.py
```
* Run the patcher, and follow the prompts :)
```
./patcher.py
```

Alternatively, distribute using Puppet, or some other form of shininess. But the above works fine :)


## To-do:
* Manual run default; auto run available with "-a|--auto"
* "-r|--report" option for feeding back pending updates via Cron or whatever
* "-q|--quiet" option for no on-screen output. Exit codes will be very important therefore! (And the Documentation of..)
* Manual run gives list of outstanding patches with options; can pick any number of patches to apply (Might be nice for people on strict patching policies, but not essential atm)
* Ability to run script from local machine to patch a remote host...
* Test XenServer Pool patching functionality. [Currently UNTESTED]



Tags: XenServer Citrix Patch Patching Patcher Auto-Patcher Autopatcher
