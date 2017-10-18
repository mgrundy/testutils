# testutils

_github suggested I call this drunken-dangerzone. It's like they saw my code first..._

*This was built for AWS classic. It doesn't really do VPC correctly.*

There is a bunch of messy this and that in here. But the big one is awsbuilder. When I'm testing I frequently need to build up AWS instances. I've had a rag-tag fleet of scripts to do this for some time; but laziness and haste led to constant tweaking for a particular job instead of general purpose power.

## awsbuilder.py

* The ability to build Linux or Windows instances
* The ability to build Paravirtual or Hardware virtual instances
* A set of working AMIs to choose from
* Store your instance data in MongoDB, or work without a db
* Support for Spot as well as on-demand instances (Spot is a significant cost saver over equivalent on-demand instances).
* Ability to update Route53 DNS with sequential host CNAMEs (based on prefix, count, and domain name options)

### Prereqs:

* Boto and PyMongo modules installed
* AWS credentials in a .boto file. Example:
```
[Credentials]
aws_access_key_id = AKIAIOMDXAAAAAAAAAAAA
aws_secret_access_key = d+pzsYrrrrrrrrrrrrrrYYYYYYYYYYYYYYYYYYY5
```

### Usage:

Here is a basic example that creates an on-demand m1.small instance running Ubuntu Server 10.04 LTS:

```
python awsbuilder.py --expires=2013-11-03 --owner=<your jira username> --name=QA-399 -m m1.small --nodb --sec-group=mg-fsr -k /Users/mg/mg-repro.pem -c 1 --ami=ubuntu1004
```

* Standard tags from a previous gig are filled out (the expires-on, owner, and Name tags).
`--sec-group` specifies the name of the AWS security group for this instance. If you give a name that doesn't exist, a new group with ssh and tcp ports 27010-27050 open.
* The `-k` specifies a ssh private key to use. If it doesn't exist, it will be created.
* `-c` is the number of instances to create, and `--ami` is the nickname of the AMI to use. Not all AMIs work with spot instances, and some machine classes are restricted from certain AMIs. It's a bit willy-nilly, but it will error fatally and tell you what was wrong.

* You can list out the available AMIs with the `--list-ami` option:

``` 
python awsbuilder.py --list-ami
ParaVirt AMIs:
	ubuntu1310
	centos6
	centos5
	awz
	sles11
	ubuntu1004
	fedora19
	ubuntu1204
	rhel59
	rhel64
HardwareVirt AMIs:
	win2003
	win2012
	ubuntu13
	awz
	win2008
	ubuntu12
	rhel64
	sles11
```
#### Who knows if this is still even correct?
A word about paravirtualization vs hardware virtualization: Windows instances are all Hardware Virtualization, some machine types (certain cluster compute nodes and m3 nodes for example) are as well. If you're creating a Windows instance or want to use a m3 or cluster compute machine type, specify the --hvm flag. You'll get an error if you get them wrong, no big deal.

Spot instances are significantly less expensive than on-demand instances. Use them! But keep in mind some images won't work with spot pricing (RHEL for example). Spot works on a high bid basis. Costs are typically 1/10th of the on-demand price. I set the high bid price to be half of the on-demand price. That is the most that we can be charged for a spot instance. Keep in mind though, that spot instances will be cancelled if the market price goes above our high bid. They are not perfect for long running projects. That said, I've had spot instances run for quite some time without issue. The biggest thing to remember with spot instances is "don't store anything unique!". If you can't reproduce it with a shell script or git clone, don't keep it hanging on a spot instance. (Or use EBS storage and attach it to your spot, but think about what you're doing there before you start)

Finally check the spot pricing here: http://aws.amazon.com/ec2/pricing/#spot
And here is a great comparison of instance types: http://copperegg.wpengine.netdna-cdn.com/wp-content/uploads/2013/08/AWS-Pricing-Cheat-Sheet8-6-13.pdf



```
Usage: awsbuilder.py [options]

AWS instance builder for 

Options:
  -h, --help            show this help message and exit
  -l LOGFILE, --log-file=LOGFILE
                        name of logfile all session traffic will be written to
  -i INSTANCE, --instance=INSTANCE
                        A specific instance to act on
  -c BUILDCOUNT, --count=BUILDCOUNT
                        Number of instances to build
  -s, --spot            Request spot instances
  -o, --ondemand        Request on-demand instances
  --nodb                Do not connect to database
  --owner=OWNER         The name to tag as owner
  --name=INSTNAME       The instance name, or name prefix (for multiples)
  --expires=EXPIRES     Value for the expires-on tag
  --ami=AMIID           The ami nickname to use
  --list-types          display the machine types we can build
  --list-ami            list AMIs available in this utility
  --hvm                 list AMIs available in this utility
  -m INSTANCETYPE, --instance-type=INSTANCETYPE
                        instance type to build
  -k KEYFILE, --keyfile=KEYFILE
                        name and path of ssh key file, created if doesn't
                        exist
  --start               Start the instances selected by --group or -i
  --stop                Stop the instances selected by --group or -i
  --terminate           Terminate the instances selected by --group or -i
  --sec-group=SECGROUP  name of security group to use, will create if doesn't
                        exist (With ssh only)
  --group=GROUPNAME     name of management group. only used internally for
                        managing instances (do this if you are attached to a
                        db)
  -d DOMAINNAME, --domain=DOMAINNAME
                        name of the domain to update with the new hosts
  -p PREFIXNAME, --prefix=PREFIXNAME
                        prefix of hostname to update domain with, will be
                        appended with number
  --startcount=STARTCOUNT
                        number to start appending to prefix with
			
```
