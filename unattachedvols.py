#!/bin/python

import boto
from pprint import pprint
ec2 = boto.connect_ec2()
vol = ec2.get_all_volumes()
for unattachedvol in vol:
    state = unattachedvol.attachment_state()
    if state == None:
        if unattachedvol.snapshot_id == "":
#            pprint(vars(unattachedvol))
            print unattachedvol.create_time,  unattachedvol.status, unattachedvol.id, "iops:", unattachedvol.iops, "size:",unattachedvol.size, "\n", unattachedvol.tags
