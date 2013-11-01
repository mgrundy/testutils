import sys
import os
import time
import boto
import boto.ec2
import boto.manage.cmdshell
from boto import route53
from boto.route53 import connection
from boto.route53.record import ResourceRecordSets
import copy
import pymongo
from pprint import pprint

# We'll use these to determine what the highest spot price
# should be
ec2InstanceRates = {
    'm1.small': {'hourly': .06},
    'm1.medium': {'hourly': .12},
    'm1.large': {'hourly': .24},
    'm1.xlarge': {'hourly': .48},
    'm3.xlarge': {'hourly': .50},
    'm3.2xlarge': {'hourly': 1.00},
    't1.micro': {'hourly': .02},
    'm2.xlarge': {'hourly': .41},
    'm2.2xlarge': {'hourly': .82},
    'm2.4xlarge': {'hourly': 1.64},
    'c1.medium': {'hourly': .145},
    'c1.xlarge': {'hourly': .58},
    'cc1.4xlarge': {'hourly': 1.30},
    'cc2.8xlarge': {'hourly': 2.40},
    'cr1.8xlarge': {'hourly': 3.50},
    'hi1.4xlarge': {'hourly': 3.10},
    'hs1.8xlarge': {'hourly': 4.60}
    }

ec2InstanceTypes = [
	"t1.micro",
	"m1.small",
	"m1.medium",
	"m1.large",
	"m1.xlarge",
	"m2.xlarge",
	"m2.2xlarge",
	"m2.4xlarge",
	"c1.medium",
	"c1.xlarge",
	"cc1.4xlarge",
	"cc2.8xlarge",
	"cg1.4xlarge",
	"cr1.8xlarge",
	"m3.xlarge",
	"m3.2xlarge",
	"hi1.4xlarge",
	"hs1.8xlarge"
]

pvmAmiList = {
        "awz":'ami-35792c5c',
        "centos5":'ami-7739b21e',   #DynaCenter ami
        "centos6":'ami-07b73c6e',   #DynaCenter ami
        "rhel59": 'ami-cf5b32a6',
        "rhel64":'ami-a25415cb',
        "sles11":'ami-e8084981',
        "ubuntu1004":'ami-68c01201',
        "ubuntu1204":'ami-a73264ce',
        "ubuntu1310":'ami-ad184ac4',
        "fedora19":'ami-b22e5cdb'
        }
hvmAmiList = {
        "win2003":'ami-bc5f83d7',
        "win2008":'ami-7f236a16',
        "win2012":'ami-173d747e',
        "awz":'ami-69792c00',
        "rhel64":'ami-3218595b',
        "sles11":'ami-b6c146df',
        "ubuntu13":'ami-a1184ac8',
        "ubuntu12":'ami-b93264d0'
        }


#    Loop through all pending request ids waiting for them to be fulfilled.
#    If a request is fulfilled, remove it from pending_req_ids.
#    If there are still pending requests, sleep and check again in 10 seconds.
#    Only return when all spot requests have been fulfilled.
def wait_for_fulfillment(conn, request_ids, pending_req_ids):
    instance_ids = []
    results = conn.get_all_spot_instance_requests(request_ids=pending_req_ids)
    for result in results:
        if result.status.code == 'fulfilled':
            pending_req_ids.pop(pending_req_ids.index(result.id))
            print "spot request `{}` fulfilled!".format(result.id)
            instance_ids.append(result.instance_id)
        else:
            print "waiting on `{}`".format(result.id)

    if len(pending_req_ids) == 0:
        print "all spots fulfilled!"
    else:
        time.sleep(10)
        instance_ids += wait_for_fulfillment(conn, request_ids, pending_req_ids)

    return instance_ids


    
#    Launch an instance and wait for it to start running.
#    Returns a tuple consisting of the Instance object and the CmdShell
#    object, if request, or None.
def launch_instance(ami='ami-7341831a',
                    instance_type='t1.micro',
                    count=1,
                    spot=False,
                    key_name='paws',
                    key_extension='.pem',
                    key_dir='~/.ssh',
                    group_name='paws',
                    ssh_port=22,
                    cidr='0.0.0.0/0',
                    tags={"requestor":"Mike Grundy"},
                    user_data=None,
                    cmd_shell=True,
                    login_user='ec2-user',
                    ssh_passwd=None,
        		    bdm=None):


    cmd = None

    # Create a connection to EC2 service.
    ec2 = boto.connect_ec2()

    # Check to see if specified keypair already exists.
    # If we get an InvalidKeyPair.NotFound error back from EC2,
    # it means that it doesn't exist and we need to create it.
    try:
        key = ec2.get_all_key_pairs(keynames=[key_name])[0]
    except ec2.ResponseError, e:
        if e.code == 'InvalidKeyPair.NotFound':
            print 'Creating keypair: %s' % key_name
            # Create an SSH key to use when logging into instances.
            key = ec2.create_key_pair(key_name)

            # AWS will store the public key but the private key is
            # generated and returned and needs to be stored locally.
            # The save method will also chmod the file to protect
            # your private key.
            key.save(key_dir)
        else:
            raise

    # Check to see if specified security group already exists.
    # If we get an InvalidGroup.NotFound error back from EC2,
    # it means that it doesn't exist and we need to create it.
    try:
        group = ec2.get_all_security_groups(groupnames=[group_name])[0]
    except ec2.ResponseError, e:
        if e.code == 'InvalidGroup.NotFound':
            print 'Creating Security Group: %s' % group_name
            # Create a security group to control access to instance via SSH.
            group = ec2.create_security_group(group_name,
                                              'A group that allows SSH access')
        else:
            raise

    # Add a rule to the security group to authorize SSH traffic
    # on the specified port.
    try:
        group.authorize('tcp', ssh_port, ssh_port, cidr)
        # and httpd
        group.authorize('tcp',80 ,80 , cidr)
	# kerberos server ports
        #group.authorize('tcp',88 ,88 , cidr)
        #group.authorize('tcp',749 ,749 , cidr)
        #group.authorize('udp',88 ,88 , cidr)
        #group.authorize('udp', 749, 749, cidr)
	# Add a range of ports for MongoDB
        group.authorize('tcp', 27010, 27050, cidr)
    except ec2.ResponseError, e:
        if e.code == 'InvalidPermission.Duplicate':
            print 'Security Group: %s already authorized' % group_name
        else:
            raise

    # Now start up the instance.  The run_instances and spot_instances
    # methods have many, many parameters but these are all we need
    # for now.
    if spot:
        requests = ec2.request_spot_instances(ec2InstanceRates[instance_type]['hourly'] * .5,
    	 ami, # ami
    	 count=count,  # count
    	 type='one-time',
    	 key_name=key_name, # key_name
    	 security_groups= [group_name],
    	 user_data=user_data,
    	 instance_type=instance_type, #instance type
         # # Currently unused options
    	 # valid_from=None, valid_until=None, launch_group=None, 
         # availability_zone_group=None,
    	 # addressing_type=None, # only the shadow knows
    	 # placement=None, kernel_id=None, ramdisk_id=None, 
         # monitoring_enabled=False, subnet_id=None, placement_group=None,
    	 # instance_profile_arn=None, instance_profile_name=None, 
         # security_group_ids=None, ebs_optimized=False, network_interfaces=None,
    	 block_device_map=bdm)

        # get the request ids to wait on 
        request_ids = [req.id for req in requests]
        # wait for the requests to be fulfilled
        instance_ids = wait_for_fulfillment(ec2, request_ids, copy.deepcopy(request_ids))
        reservation = ec2.get_all_reservations(instance_ids=instance_ids)

    else:
        reservation = [ec2.run_instances(ami,
                        min_count=count, max_count=count,
                        key_name=key_name,
                        security_groups=[group_name],
                        instance_type=instance_type,
	    		        block_device_map=bdm,
                        user_data=user_data)]

    # The instance has been launched but it's not yet up and
    # running.  Let's wait for its state to change to 'running'.

    print 'waiting for instances'
    state = 'not'
    while state != 'running':
        sys.stdout.write('.')
        time.sleep(5)
        for r in reservation:
            for instance in r.instances:
                instance.update()
                state = 'running'
                if (instance.state != 'running'):
                    state = 'not'

    print '\nTagging instances'

    # Let's tag the instance with the specified label so we can
    # identify it later.
    for r in reservation:
        for instance in r.instances:
            for tagname in tags:
                instance.add_tag(tagname,tags[tagname])
            print instance.public_dns_name

    return (reservation)


def create_and_attach_volume(instance, volume_size, device_name):
    ec2 = instance.connection
    # Determine the Availability Zone of the instance
    azone = instance.placement
    
    volume = ec2.create_volume(volume_size, azone)

    # Wait for the volume to be created.
    while volume.status != 'available':
        time.sleep(5)
        volume.update()

    volume.attach(instance.id, device_name)
    return volume

def dnsUpdate( hostDict, dnsName):

    # Connect 
    route53 = connection.Route53Connection()

    # Get the Zone obj for our domain
    dnsZone=route53.get_zone(dnsName)

    # aname is our alias, hname is the real host name
    for aname, hname in hostDict.iteritems():
        record = dnsZone.get_cname(aname)
        if record is not None:
            # sure hope it's just one record
            if record.resource_records[0] != hname:
                dnsZone.update_cname(aname, hname)
        else:
            dnsZone.add_cname(aname, hname)


def main():
    import optparse

    parser = optparse.OptionParser(usage="""\
%prog [options]

10gen AWS instance builder for test""")

    parser.add_option("-l", "--log-file", dest="logfile",
        help="name of logfile all session traffic will be written to",
        default=None)

    parser.add_option("-i", "--instance", dest="instance",
        help="A specific instance to act on",
        default=None)

    parser.add_option("-c", "--count", dest="buildCount",
        help="Number of instances to build",
        type="int",
        default=None)

    parser.add_option("-s", "--spot", dest="spotRequest",
        help="Request spot instances",
        action="store_true",
        default=False)

    parser.add_option("-o", "--ondemand", dest="spotRequest",
        help="Request on-demand instances",
        action="store_false"
        )

    parser.add_option("--nodb", dest="useDB",
        help="Request spot instances",
        action="store_false",
        default=True)

    parser.add_option("--requestor", dest="requestor",
        help="The name to tag as requestor",
        default=None)

    parser.add_option("--name", dest="instName",
        help="The instance name, or name prefix (for multiples)",
        default=None)

    parser.add_option("--expires", dest="expires",
        help="Value for the expires-on tag",
        default=None)

    parser.add_option("--ami", dest="amiId",
        help="The ami nickname to use",
        default=None)

    parser.add_option("--list-types", dest="listType",
        help="display the machine types we can build",
        action="store_true",
        default=False)

    parser.add_option("--list-ami", dest="listAmi",
        help="list AMIs available in this utility",
        action="store_true",
        default=False)

    parser.add_option("--hvm", dest="hvmVirt",
        help="list AMIs available in this utility",
        action="store_true",
        default=False)

    parser.add_option("-m", "--instance-type", dest="instanceType",
        help="instance type to build",
        default=None)

    parser.add_option("-k", "--keyfile", dest="keyFile",
        help="name and path of ssh key file, created if doesn't exist",
        default=None)

    parser.add_option("-g", "--group", dest="groupName",
        help="name of security group to use, will create if doesn't exist (With ssh only)",
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

    (options, args) = parser.parse_args()

    if( options.listAmi ):
        print "ParaVirt AMIs:"
        for key in pvmAmiList: 
            print "\t", key
        print "HardwareVirt AMIs:"
        for key in hvmAmiList: 
            print "\t", key
        sys.exit()


    if( options.listType ):
        print "Instance type and on-demand hourly pricing"
        for instType, price in ec2InstanceRates.iteritems():
            print "\t", instType, "\t", price['hourly']
        sys.exit()

    if( (not options.instanceType) or (not options.buildCount) or (not options.groupName)):
        parser.error("options -i and -c, -g are mandatory")
    if( (options.domainName and not options.prefixName) or
            (options.prefixName and not options.domainName) ):
        parser.error("options --domain and --prefix must both be specified")

    # Get the database connection set up    
    if options.useDB:
        try:
            connection = MongoClient('localhost', 27017)
            # connection = pymongo.Connection("mongodb://localhost", safe=True)
        except ConnectionFailure, e:
            sys.stderr.write("Could not connect to MongoDB: %s" % e)
            sys.exit(1)
        # get a handle to the database
        db = connection['ec2data']
        # and the collection
        ec2_inst = db['instances']


    # Make sure we don't leave the root EBS volume hanging around
    dev_sda = boto.ec2.blockdevicemapping.EBSBlockDeviceType(delete_on_termination=True, size=20)
    block_dm = boto.ec2.blockdevicemapping.BlockDeviceMapping()
    block_dm['/dev/sda1'] = dev_sda

    # Map out the ephemeral disks. This doesn't seem to choke if there are less instance disks available
    block_dm['/dev/sdc'] = boto.ec2.blockdevicemapping.EBSBlockDeviceType(ephemeral_name='ephemeral0')
    block_dm['/dev/sdd'] = boto.ec2.blockdevicemapping.EBSBlockDeviceType(ephemeral_name='ephemeral1')
    block_dm['/dev/sde'] = boto.ec2.blockdevicemapping.EBSBlockDeviceType(ephemeral_name='ephemeral2')
    block_dm['/dev/sdf'] = boto.ec2.blockdevicemapping.EBSBlockDeviceType(ephemeral_name='ephemeral3')

    # so, this needs some logic to alow for the specification of iop devices
    # P U T   L O G I C   H E R E
    
    # put together the tags dict. The host aliases will be serialized
    inst_tags = {'Name':options.instName, 'requestor':options.requestor, 'expire-on': options.expires}
    pprint(inst_tags)

    
    try:
        if options.hvmVirt:
            launchAmi = hvmAmiList[options.amiId]
        else:
            launchAmi = pvmAmiList[options.amiId]
    except :
        parser.error("--ami is required and must be on the list (use --list-ami to see the list)\n" +
                     "Also, you may have to use --hvm for hardware virt images")

    # Decided not to do this inline for clarity
    kname = os.path.basename(options.keyFile)
    (kname, kext) = os.path.splitext(kname)
    kdir = os.path.dirname(options.keyFile)

    reservations = launch_instance(ami=launchAmi,
                    instance_type=options.instanceType,
                    count=options.buildCount,
                    spot=options.spotRequest,
                    key_name=kname,
                    key_extension=kext,
                    key_dir=kdir,
                    group_name=options.groupName,
                    tags=inst_tags,
                    cmd_shell=False,
#                    user_data=script,
#                    login_user='fedora',
        		    bdm=block_dm)

    # Initialize host count 
    count = options.startCount
    hostList = {}
    for r in reservations:
        for inst in r.instances:
            tmphname = options.prefixName + "-%02d." % count + options.domainName + "." 
            hostList[tmphname] = inst.public_dns_name
            count += 1
        try:
            instance = {}
            instance['_id'] = inst.id
            instance['public_dns_name'] = inst.public_dns_name
            instance['tags'] = inst.tags
            instance['image_id'] = inst.image_id
            instance['launch_time'] = inst.launch_time
            instance['instance_type'] = inst.instance_type
            instance['vpc_id'] = inst.vpc_id
            instance['architecture'] = inst.architecture
            instance['private_dns_name'] = inst.private_dns_name
            instance['private_ip_address'] = inst.private_ip_address
            instance['key_name'] = inst.key_name
            instance['dns_alias'] = tmphname[:-1]
            print "i made this:\n ", instance

            if options.useDB:
                print "inserting ", instance
                ec2_inst.insert(instance)
        except ValueError, e:
            # print sys.exc_info()
            print e
    if options.domainName:
        dnsUpdate(hostList, options.domainName + ".") 

if __name__ == "__main__":
    main()
