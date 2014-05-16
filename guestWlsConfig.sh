#!/bin/bash
    sudo yum --assumeyes install gcc-c++ cyrus-sasl cyrus-sasl-lib cyrus-sasl-devel cyrus-sasl-gssapi cyrus-sasl-md5 net-snmp net-snmp-libs net-snmp-utils net-snmp-devel libgsasl git pymongo python-pip python-devel openssl-devel boost.x86_64 boost-devel.x86_64 xfsprogs lcov wget openldap-servers openldap-clients screen
    sudo pip-python install pymongo simples3 cpplint
    wget "http://softlayer-dal.dl.sourceforge.net/project/scons/scons/2.3.0/scons-2.3.0.tar.gz"
    tar zxvf scons-2.3.0.tar.gz 
    sudo python scons-2.3.0/setup.py install
    chmod 600 mg-covweb.pem
    scp -i ~/mg-covweb.pem ec2-user@lcov.knuckleboys.com:lcov.rpm .
    sudo rpm -i lcov.rpm --force
    scp -i ~/mg-covweb.pem ec2-user@lcov.knuckleboys.com:geninfo .
    sudo cp geninfo /usr/bin
    wget lcov.knuckleboys.com/gcc-aws-hvm.tar.bz2
    sudo su -c "cd / && tar xjf ~ec2-user/gcc-aws-hvm.tar.bz2"

    # disk fixups
    sudo umount /mnt/* /dev/xvdc /dev/xvdd /dev/xvde /dev/xvdf
    sudo sed -i '/ephemeral/d' /etc/fstab
    echo -e "n\np\n1\n\n+100G\nn\np\n2\n\n+100G\nw\n" | sudo fdisk /dev/xvdc
    sudo /sbin/mkfs.xfs /dev/xvdc1 -f
    sudo /sbin/mkfs.xfs /dev/xvdc2 -f
    sudo /sbin/mkfs.xfs /dev/xvdd -f
    sudo /sbin/mkfs.xfs /dev/xvde -f
    sudo /sbin/mkfs.xfs /dev/xvdf -f
    sudo mkdir -p /data
    sudo mkdir -p /local
    sudo blockdev --setra 32 /dev/xvdc1
    echo "/dev/xvdc1 /data auto noatime 0 0" | sudo tee -a /etc/fstab
    echo "/dev/xvdd /local auto noatime 0 0" | sudo tee -a /etc/fstab
    sudo mount -a
    sudo mkdir -p /local/build
    sudo mkdir -p /data/db
    echo "/dev/xvde /local/build auto noatime 0 0" | sudo tee -a /etc/fstab
    echo "/dev/xvdc2 /tmp auto noatime 0 0" | sudo tee -a /etc/fstab
    sudo mount -a
    sudo chmod 1777 /tmp
    sudo chown -R ec2-user:ec2-user /data
    sudo chown -R ec2-user:ec2-user /local


cd /local/build
git clone https://github.com/mongodb/mongo.git
cd mongo
sudo mkdir -p /static/html
sudo chown -R ec2-user:ec2-user /static
python buildscripts/setup_multiversion_mongodb.py /local/multi-install /static/multi-link Linux/x86_64 1.8 2.0 2.2 2.4
cd -
git clone https://github.com/mgrundy/testutils.git

cd testutils
    wget lcov.knuckleboys.com/cleanbb.py
    cp cleanbb.py /local/build/mongo/buildscripts
 echo '*	hard    nproc           50000' | sudo tee -a /etc/security/limits.conf
 echo '*	soft 	nproc           45000' | sudo tee -a /etc/security/limits.conf
 echo '*	hard    nofile           50000' | sudo tee -a /etc/security/limits.conf
 echo '*	soft 	nofile           45000' | sudo tee -a /etc/security/limits.conf
echo "ulimit -u 50000" >> .bashrc
#bash build-cov.sh -d /static/html/ -t /local -b master -x -p --build-dir /local/build/mongo/ --mv-dir /static/multi-link/
