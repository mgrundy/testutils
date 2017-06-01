import sys
import os
import pwd
import time
import boto
import boto.ec2
import boto.vpc
import boto.manage.cmdshell
from boto import route53
from boto.route53 import connection
from boto.route53.record import ResourceRecordSets
from datetime import date, timedelta
import copy
import pymongo
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from pprint import pprint
import ConfigParser
from os.path import expanduser
from Crypto.Cipher import PKCS1_v1_5
from Crypto.PublicKey import RSA

# We'll use these to determine what the highest spot price
# should be
ec2InstanceRates = {
    # General Purpose Current Gen    
    # These don't look like they can be spot
    't2.micro': {'hourly': .013},
    't2.small': {'hourly': .026},
    't2.medium': {'hourly': .052},
    # These can be spot
    'm3.medium': {'hourly': .07},
    'm3.large': {'hourly': .14},
    'm3.xlarge': {'hourly': .28},
    'm3.2xlarge': {'hourly': .56},
    # General Purpose Prev Gen    
    'm1.small': {'hourly': .044},
    'm1.medium': {'hourly': .087},
    'm1.large': {'hourly': .175},
    'm1.xlarge': {'hourly': .35},
    # Compute Optimized Current Gen
    'c3.large': {'hourly':   0.105},
    'c3.xlarge': {'hourly':  0.210},
    'c3.2xlarge': {'hourly': 0.420},
    'c3.4xlarge': {'hourly': 0.840},
    'c3.8xlarge': {'hourly': 1.680},
    # Compute Optimized Prev Gen
    'c1.medium': {'hourly': .24},
    'c1.xlarge': {'hourly': .53},
    'cc2.8xlarge': {'hourly': 2.00},
    # GPU Instances Current Gen
    'g2.2xlarge': {'hourly': .65},
    # GPU Instances Prev Gen
    'cg1.4xlarge': {'hourly': 2.10},
    # Memory Optimized Current Gen
    'r3.large': {'hourly': .175},
    'r3.xlarge': {'hourly': .350},
    'r3.2xlarge': {'hourly': .70},
    'r3.4xlarge': {'hourly': 1.40},
    'r3.8xlarge': {'hourly': 2.80},
    # Memory Optimized Prev Gen
    'm2.xlarge': {'hourly': .245},
    'm2.2xlarge': {'hourly': .49},
    'm2.4xlarge': {'hourly': .98},
    'cr1.8xlarge': {'hourly': 3.50},
    # Storage Optimized Prev Gen
    'hi1.4xlarge': {'hourly': 3.10},
    # Micro
    't1.micro': {'hourly': .02}
    }

ec2InstanceTypes = [
    # General Purpose Current Gen    
    # These don't look like they can be spot
    't2.micro',
    't2.small',
    't2.medium',
    # These can be spot
    'm3.medium',
    'm3.large',
    'm3.xlarge',
    'm3.2xlarge',
    # General Purpose Prev Gen    
    'm1.small',
    'm1.medium',
    'm1.large',
    'm1.xlarge',
    # Compute Optimized Current Gen
    'c3.large',
    'c3.xlarge',
    'c3.2xlarge',
    'c3.4xlarge',
    'c3.8xlarge',
    # Compute Optimized Prev Gen
    'c1.medium',
    'c1.xlarge',
    'cc2.8xlarge',
    # GPU Instances Current Gen
    'g2.2xlarge',
    # GPU Instances Prev Gen
    'cg1.4xlarge',
    # Memory Optimized Current Gen
    'r3.large',
    'r3.xlarge',
    'r3.2xlarge',
    'r3.4xlarge',
    'r3.8xlarge',
    # Memory Optimized Prev Gen
    'm2.xlarge',
    'm2.2xlarge',
    'm2.4xlarge',
    'cr1.8xlarge',
    # Storage Optimized Prev Gen
    'hi1.4xlarge',
    # Micro
    't1.micro'
]

pvmAmiList = {
        "awz":'ami-1b3b462b',
        "centos5":'ami-7739b21e',   #DynaCenter ami
        "centos6":'ami-07b73c6e',   #DynaCenter ami
        "rhel59": 'ami-cf5b32a6',
        "rhel64":'ami-a25415cb',
        "rhel65":'ami-7bdaa84b',
        "sles11":'ami-a997ea99',
        "ubuntu1004":'ami-68c01201',
        "ubuntu1204":'ami-a73264ce',
        "ubuntu1310":'ami-ad184ac4',
        "ubuntu1404":'ami-8bb8c0bb',
        "fedora19":'ami-b22e5cdb',
        "arch":'ami-cd7b67a4'
        }
hvmAmiList = {
        "win2003":'ami-f16025c1',
        "win2008":'ami-056d2835',
        "win2012":'ami-3bcd880b',
        "awz":'ami-d13845e1',
        "rhel64":'ami-3218595b',
        "rhel65":'ami-5b697332',
        "rhel7":'ami-77d7a747',
        "sles11":'ami-7fd3ae4f',
        "ubuntu14":'ami-e7b8c0d7',
        "ubuntu13":'ami-a1184ac8',
        "ubuntu12":'ami-b93264d0'
        }

def changeState(group, instid, action, ec2_inst):
# Deprecated
    # ec2 = boto.connect_ec2()
# XXX TODO take region as an option
    ec2 = boto.vpc.connect_to_region("us-east-1")
    instancelist = list()
    # try block this stuff please
    if group:
        instances = ec2_inst.find({"group":group},{"_id":1})
        for instance in instances:
        	instancelist.append(instance["_id"])
    elif instid:
       	instancelist.append(instid)
    else:
        print "Internal Error, no instance or group specified"
        return

    if action == "stop":
        reslist = ec2.stop_instances(instance_ids=instancelist)

    elif action == "start":
        reslist = ec2.start_instances(instance_ids=instancelist)

    elif action == "terminate":
        reslist = ec2.terminate_instances(instance_ids=instancelist)

    else:
        print "Internal Error, no action specified"

    print reslist

def getWindowsPassword(ec2, instance, keyfile):
    plaintext = None
    password_data = None
    try:
        input = open(keyfile)
        key = RSA.importKey(input.read())
        input.close()
        # is this really the best way?
        while not password_data:
            print "getting password for instance: ", instance
            password_data = ec2.get_password_data(instance)
            print "intermed data", password_data
            time.sleep(10)
        cipher = PKCS1_v1_5.new(key)
        plaintext = cipher.decrypt(password_data.decode('base64'), None)
    except IOError, e:
        print "IOError: ", e[0], e[1], keyfile
    except (ValueError, IndexError, TypeError) as detail:
        print type(detail), detail
    except e: 
        print type(e), e
    finally:
        return plaintext


#    Loop through all pending request ids waiting for them to be fulfilled.
#    If a request is fulfilled, remove it from pending_req_ids.
#    If there are still pending requests, sleep and check again in 10 seconds.
#    Only return when all spot requests have been fulfilled.
def wait_for_fulfillment(conn, request_ids, pending_req_ids):
    instance_ids = []
    retry_count = 0
    while retry_count < 5:
        try:    
            results = conn.get_all_spot_instance_requests(request_ids=pending_req_ids)
            break
        except conn.ResponseError, e:
            print e.code, "error getting requests, probs not ready"
            time.sleep(10)
            retry_count += 1

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
                    tags={"owner":"Mike Grundy"},
                    user_data=None,
                    cmd_shell=True,
                    login_user='ec2-user',
                    ssh_passwd=None,
                    getPass=False,
        		    bdm=None):


    cmd = None
    create_group = False

    # Create a connection to EC2 service.
    #ec2 = boto.connect_ec2()
    ec2 = boto.vpc.connect_to_region("us-east-1")

    # Check to see if specified keypair already exists.
    # If we get an InvalidKeyPair.NotFound error back from EC2,
    # it means that it doesn't exist and we need to create it.
    try:
        key = ec2.get_all_key_pairs(keynames=[key_name])[0]
        print key
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
        print ec2.get_all_security_groups()
        group = ec2.get_all_security_groups(filters={'group-name': group_name})[0]
    except IndexError:
        create_group = True
    except ec2.ResponseError, e:
        if e.code == 'InvalidGroup.NotFound':
            create_group = True
        else:
            raise
    if create_group:
        print 'Creating Security Group: %s' % group_name
        # Create a security group to control access to instance via SSH.
        group = ec2.create_security_group(group_name,
                                              'A group that allows SSH access',
                                              vpc_id="vpc-9b04b5fe")
    # Add a rule to the security group to authorize SSH traffic
    # on the specified port.
    try:
        group.authorize('tcp', ssh_port, ssh_port, cidr)
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
         security_group_ids=[group.id],
         subnet_id='subnet-a3cb3bfa',
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
                        security_group_ids=[group.id],
                        instance_type=instance_type,
	    		        block_device_map=bdm,
                        subnet_id='subnet-a3cb3bfa',
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

    if getPass:
        for r in reservation:
            for instance in r.instances:
                getWindowsPassword(ec2, instance, key_dir + "/" + key_name + key_extension)

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
        record = dnsZone.get_cname(aname)
        if record is not None:
            # sure hope it's just one record
            if record.resource_records[0] != hname:
                dnsZone.update_cname(aname, hname)
        else:
            dnsZone.add_cname(aname, hname)


def main():
    import optparse
    user_info = pwd.getpwuid( os.getuid() )
    parser = optparse.OptionParser(usage="""\
%prog [options]

MongoDB CAP AWS instance builder for test""")

    parser.add_option("-l", "--log-file", dest="logfile",
        help="name of logfile all session traffic will be written to",
        default=None)

    parser.add_option("-i", "--instance", dest="instance",
        help="A specific instance to act on",
        default=None)

    parser.add_option("-c", "--count", dest="buildCount",
        help="Number of instances to build",
        type="int",
        default=1)

    parser.add_option("-s", "--spot", dest="spotRequest",
        help="Request spot instances",
        action="store_true",
        default=False)

    parser.add_option("-o", "--ondemand", dest="spotRequest",
        help="Request on-demand instances",
        action="store_false"
        )

    parser.add_option("--nodb", dest="useDB",
        help="Don't use database to store created instance data",
        action="store_false",
        default=True)

    parser.add_option("--owner", dest="Owner",
        help="The name to tag as owner",
        default=user_info[4])

    parser.add_option("--name", dest="instName",
        help="The instance name, or name prefix (for multiples)",
        default=user_info[0])

    parser.add_option("--expires", dest="expires",
        help="Value for the expires-on tag",
        default=(date.today() + timedelta(days=3)).isoformat())

    parser.add_option("--ami", dest="amiId",
        help="The ami nickname to use",
        default="awz")

    parser.add_option("--list-types", dest="listType",
        help="display the machine types we can build",
        action="store_true",
        default=False)

    parser.add_option("--list-ami", dest="listAmi",
        help="list AMIs available in this utility",
        action="store_true",
        default=False)

    parser.add_option("--hvm", dest="hvmVirt",
        help="use hardware virtualization for Windows instances and m3 or cluster compute machine types",
        action="store_true",
        default=False)

    parser.add_option("-m", "--instance-type", dest="instanceType",
        help="instance type to build",
        default="m1.small")

    parser.add_option("-k", "--keyfile", dest="keyFile",
        help="name and path of ssh key file, created if doesn't exist",
        default=user_info[5] + "/" + user_info[4] + ".pem")

    parser.add_option("--windows-password", dest="winPass",
        help="Get the Windows administrator password for the instances selected by --group or -i",
        action="store_true",
        default=False)
    parser.add_option("--root-size", dest="rootSize",
        help="Set the root volume size in gb. 40gb required for Windows instances, 20gb is default",
        action="store_const", 
        default=20)
    parser.add_option("--start", dest="controlAction",
        help="Start the instances selected by --group or -i",
        action="store_const", 
        const='start',
        default=None)
    parser.add_option("--stop", dest="controlAction",
        help="Stop the instances selected by --group or -i",
        action="store_const", 
        const='stop',
        default=None)
    parser.add_option("--terminate", dest="controlAction",
        help="Terminate the instances selected by --group or -i",
        action="store_const", 
        const='terminate',
        default=None)

    parser.add_option("-g", "--sec-group", dest="secGroup",
        help="name of security group to use, will create if doesn't exist (With ssh only)",
        default=user_info[0])

    parser.add_option("--group", dest="groupName",
        help="name of management group. only used internally for managing instances (do this if you are attached to a db)",
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

    if options.amiId:
        if( (not options.instanceType) or (not options.buildCount) or (not options.secGroup)):
            parser.error("options -m, -c, --sec-group are mandatory for instance creation")
        if( (options.domainName and not options.prefixName) or
                (options.prefixName and not options.domainName) ):
            parser.error("options --domain and --prefix must both be specified")

    if options.controlAction and ( not (bool(options.instance) ^ bool(options.groupName))):
        parser.error("You have to specify an instance id or group for control (start/stop/term) functions")

    if options.winPass and options.instance:
#        parser.error("You have to specify an instance id or group for control (windows password) functions")
        print getWindowsPassword(boto.connect_ec2(), options.instance, options.keyFile)
        sys.exit()


    # Get the database connection set up. Place no connect actions above, post connects below
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
    elif options.groupName:
        parser.error("You can't use group name without a database connection")

    # Here's where I smh and realize I have to move all of the instance creation junk
    # to a separate method and out of main.
    if( options.groupName or options.instance ):
        if options.controlAction:
            changeState(options.groupName, options.instance, options.controlAction, ec2_inst)
            sys.exit()


    # Make sure we don't leave the root EBS volume hanging around
    dev_sda = boto.ec2.blockdevicemapping.EBSBlockDeviceType(delete_on_termination=True, size=options.rootSize)
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
    inst_tags = {'Name':options.instName, 'owner':options.Owner, 'expire-on': options.expires}
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
                    group_name=options.secGroup,
                    tags=inst_tags,
                    getPass=options.winPass,
                    cmd_shell=False,
#                    user_data=script,
#                    login_user='fedora',
        		    bdm=block_dm)

    # Initialize host count 
    count = options.startCount
    hostList = {}
    for r in reservations:
        for inst in r.instances:
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
                if options.prefixName:
                    tmphname = options.prefixName + "-%02d." % count + options.domainName + "." 
                    hostList[tmphname] = inst.public_dns_name
                    count += 1
                    instance['dns_alias'] = tmphname[:-1]
                instance['key_name'] = inst.key_name
                if options.groupName:
                    instance['group'] = options.groupName
                print "Instance created:\n ", instance

                if options.useDB:
                    ec2_inst.insert(instance)
            except ValueError, e:
                # print sys.exc_info()
                print e
    if options.domainName:
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

        dnsUpdate(hostList, options.domainName + ".", access=R53access, key=R53key) 

if __name__ == "__main__":
    main()
