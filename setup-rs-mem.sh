#!/bin/bash
DLURL=https://fastdl.mongodb.org/linux/mongodb-linux-x86_64-amazon-3.0.1-rc0.tgz
TGZ=${DLURL##h*/}
MONGOROOT=${TGZ%.tgz}
oplogOpt[1]=""
oplogOpt[2]=""
oplogOpt[3]=""

compOpts[1]=""
compOpts[2]="--wiredTigerJournalCompressor=none"
compOpts[3]="--nojournal"
shardList="1 5"
nodeList=(1 2 3)
function run_all () {
	for shard in $shardList ; do 
		for id in ${nodeList[*]} ; do 
			ssh -t -i ~/keys/mg-newlst.pem ec2-user@shard${shard}-0${id}.knuckleboys.com "$@"
		done
	done
}

function cleanup () {
	run_all "sudo killall -9 mongod mongo iostat java screen"
	run_all "screen -wipe"
	run_all "rm -f *.log screenlog.*"
	run_all "find /data -type f -exec rm -f {} \;"
	run_all "rm -f $TGZ*"
	run_all "wget $DLURL"
	run_all "tar xvzf $TGZ"
}

# WT 
function run_mongo() {
	seOpt=""
	rsOpt=""
	if [ $2. == "wt". ]; then
		seOpt="--storageEngine=wiredTiger" 
	fi
	for shard in $shardList; do 
		if [ $1. == "repl". ]; then
			rsOpt="--replSet shard${shard}"
		fi
		for id in ${nodeList[*]} ; do 
			ssh -t -i ~/keys/mg-newlst.pem ec2-user@shard${shard}-0${id}.knuckleboys.com \ "numactl --interleave=all ${MONGOROOT}/bin/mongod $seOpt  --dbpath /data/1 $rsOpt --logpath ./${id}.log --pidfilepath /home/ec2-user/mongod${id}.pid --fork ${oplogOpt[$3]} ${compOpts[$3]}  "; 
		done 
	done
	if [ $1. == "repl". ]; then
		for shard in $shardList; do 
		SETUPCMD="cfg={_id:\"shard${shard}\",version:1,members:[{_id:1,host:\"shard${shard}-01.knuckleboys.com:27017\"},{_id:2,host:\"shard${shard}-02.knuckleboys.com:27017\"},{_id:3,host:\"shard${shard}-03.knuckleboys.com:27017\"}]};printjson(rs.initiate(cfg));"
			for id in ${nodeList[0]} ; do 
				echo $SETUPCMD |  ssh -t -i ~/keys/mg-newlst.pem ec2-user@shard${shard}-0${id}.knuckleboys.com "cat > rsetup.js"
				ssh -t -i ~/keys/mg-newlst.pem ec2-user@shard${shard}-0${id}.knuckleboys.com "${MONGOROOT}/bin/mongo rsetup.js" 
				sleep 10 # give it a rest
			done
		done
	fi
}

function run_test () {
	echo $@
	cleanup
	run_mongo $@
	# Run the simple workload
#	ssh -t -i ~/keys/mg-newlst.pem ec2-user@shard5-01.knuckleboys.com "${MONGOROOT}/bin/mongo insert_test.js > s${1}-${2}-${3}.out"

}


#run_test "sa" "mmap" 1
#run_test "repl" "mmap" 1

#run_test "sa" "wt" 1
run_test "repl" "wt" 1

#run_test "sa" "wt" 2
#run_test "repl" "wt" 2

#run_test "sa" "mmap" 3
#run_test "repl" "mmap" 3

#run_test "sa" "wt" 3
#run_test "repl" "wt" 3
