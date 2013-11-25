citrix_xenserver_patcher
========================

Auto Patching tool for Citrix XenServer Boxes

Supports XenServer 6.0+ - designed primarily for 6.2+ where easy patch management via the GUI was removed
for non-supported customers. This should allow individuals and the likes to patch their systems with ease.

## To-do:
* Manual run default; auto run available with "-a|--auto"
* "-r|--report" option for feeding back pending updates via Cron or whatever
* "-q|--quiet" option for no on-screen output. Exit codes will be very important therefore! (And the Documentation of..)
* Manual run gives list of outstanding patches with options; can pick any number of patches to apply :: Need to aggregate require post-install steps. (Might be nice for people on strict patching policies, but not essential atm)
