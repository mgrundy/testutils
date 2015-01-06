#!/bin/bash

import sys
import os
import pwd
import time
import boto
import boto.ec2
import boto.vpc
import boto.manage.cmdshell
import ConfigParser
from boto import route53
from boto.route53 import connection
from boto.route53.record import ResourceRecordSets
from os.path import expanduser


def dnsUpdate( hostDict, dnsName, access=None, key=None):

    # Connect 
    route53 = connection.Route53Connection(access, key)

    # Get the Zone obj for our domain
    dnsZone=route53.get_zone(dnsName)

    if not dnsZone:
        print "unable to get zone for " + dnsName
        print "DNS not updated"
        return

    # aname is our alias, hname is the real host name
    for aname, hname in hostDict.iteritems():
        print(aname, hname)
        record = dnsZone.get_cname(aname)
        if record is not None:
            # sure hope it's just one record
            if record.resource_records[0] != hname:
                dnsZone.update_cname(aname, hname)
        else:
            dnsZone.add_cname(aname, hname)


def dnsClean( hostList, dnsName, access=None, key=None):

    # Connect 
    route53 = connection.Route53Connection(access, key)

    # Get the Zone obj for our domain
    dnsZone=route53.get_zone(dnsName)

    if not dnsZone:
        print "unable to get zone for " + dnsName
        print "DNS not updated"
        return

    # aname is our alias to delete
    for aname in hostList:
        status = dnsZone.delete_cname(aname)
        print(aname, status)

def main():
    import optparse
    user_info = pwd.getpwuid( os.getuid() )
    parser = optparse.OptionParser(usage="""\
%prog [options]

Domain name update for Route 53""")

    parser.add_option("-f", "--file", dest="hostsFile",
        help="name of the file with the hosts list",
        default=None)

    parser.add_option("-d", "--domain", dest="domainName",
        help="name of the domain to update with the new hosts",
        default=None)

    parser.add_option("-p", "--prefix", dest="prefixName",
        help="prefix of hostname to update domain with, will be appended with number",
        default=None)

    parser.add_option("--startcount", dest="startCount",
        help="number to start appending to prefix with",
        type="int",
        default=1)
    parser.add_option("--endcount", dest="endCount",
        help="last host to clean",
        type="int",
        default=1)

    parser.add_option("--DEATHNOTE", dest="cleanup",
        help="remove cname records for hosts between start and end counts",
        action="store_true",
        default=False)

    (options, args) = parser.parse_args()

    # get the path to the user's homedir
    user_home = expanduser("~")

    #load their .boto config file
    config = ConfigParser.ConfigParser()
    config.read([str(user_home + "/.boto")])

    #get the keypair for optional Route53Credentials
    R53access = None
    R53key = None
    try:
        R53access = config.get('Route53Credentials', 'aws_access_key_id')
        R53key = config.get('Route53Credentials', 'aws_secret_access_key')
    except:
        print "No Route53 specific credentials found"
        return

    count = options.startCount
    if (options.cleanup):
        hosts = []
        while count <= options.endCount:
            hosts.append(options.prefixName + "-%02d." % count + options.domainName + ".")
            count += 1
        dnsClean(hosts, options.domainName + ".", access=R53access, key=R53key) 

    else:
        # Read in the list of hosts to alias
        with open(options.hostsFile) as f:
            hosts = f.readlines()

        hostList = {}
        for host in hosts:
            tmphname = options.prefixName + "-%02d." % count + options.domainName + "." 
            hostList[tmphname] = host
            count += 1

        dnsUpdate(hostList, options.domainName + ".", access=R53access, key=R53key) 

if __name__ == "__main__":
    main()
