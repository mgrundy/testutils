#!/bin/bash

## example of a 2.2->2.4 upgrade:
## start everything in 2.2
#./startshards.sh --ver 2.2 -d ./ltest
## stop everything
#./startshards.sh --ver 2.2 -d ./ltest --stop
## start everything in 2.4 mode (mongos will fail)
#./startshards.sh --ver 2.4.0-rc2 -d ./ltest
## Look at failure
#cat mongos.log
## start up mongos in prev version
#./startshards.sh --ver 2.2 -d ./ltest --starts
## Turn off balancer
#ltest/mongo-2.2 < baloff.js
## stop mongos
#./startshards.sh --ver 2.2 -d ./ltest --stops
## start mongos in upgrade mode
#./startshards.sh --ver 2.4.0-rc2 -d ./ltest --upgrades
## ctrl+c out then start for realz
#./startshards.sh --ver 2.4.0-rc2 -d ./ltest --starts 
## turn on balancer
#ltest/mongo-2.2 < balon.js

MONGOPATH=.
LOGPATH="--logpath ./mongos.log"
SHARDS=3
REPLICAS=0
function setupShards () {
	# Setting up sharding
	sleep 5
	for shard in $(seq ${SHARDS}); do
		echo adding shard ${shard}
		if [ $REPLICAS -eq 0 ]; then
			${MONGOPATH}/mongo${MONGOVER} ${IPV6} admin --eval "printjson(db.runCommand({\"addShard\" : \"localhost:2794${shard}\"}))"
		else
			${MONGOPATH}/mongo${MONGOVER} ${IPV6} admin --eval "printjson(db.runCommand({\"addShard\" : \"shardset${shard}/localhost:27${shard}11,localhost:27${shard}12,localhost:27${shard}13\"}))"
		fi
	done
	sleep 5
	# Enable sharding on the machstats db and its collections
	echo inserting test data 
	${MONGOPATH}/mongo${MONGOVER} ${IPV6} machstats --eval "db.ps.insert({test:1}); db.top.insert({test:1})"
	echo  sharding collections
	${MONGOPATH}/mongo${MONGOVER} ${IPV6} admin --eval "printjson(sh.enableSharding('machstats'));"
	${MONGOPATH}/mongo${MONGOVER} ${IPV6} admin --eval "printjson(sh.shardCollection('machstats.top', {_id: 1}));"
	${MONGOPATH}/mongo${MONGOVER} ${IPV6} admin --eval "printjson(sh.shardCollection('machstats.ps', {_id: 1}));"
	${MONGOPATH}/mongo${MONGOVER} ${IPV6} admin --eval "printjson(sh.status());"
}
function mongosUpgrade () {
	echo starting mongos upgrade version $MONGOVER
	echo Turning off balancer
	${MONGOPATH}/mongo${MONGOVER} ${IPV6} config --eval "sh.setBalancerState(false)"
	echo running upgrade, control+C when complete
	${MONGOPATH}/mongos${MONGOVER} ${IPV6} --configdb localhost:27931,localhost:27932,localhost:27933 --upgrade
	echo Turning on balancer
	${MONGOPATH}/mongo${MONGOVER} ${IPV6} config --eval "sh.setBalancerState(true)"
	launchMongos

}
function checkPidRunning() {
	# Check and see if the config servers are already running
	for pidfile in $@; do
		if [ -e $pidfile ]; then
			if ps -p $(cat $pidfile) > /dev/null; then
				echo config server $(cat $pidfile) is still running
				echo you need to use the appropriate --stop options before restarting
				exit
			else
				echo removing stale pid file $pidfile
				rm -f $pidfile
			fi
		fi
	done
}
function startReplicas() {
if [ $REPLICAS -gt 0 ]; then
	echo Starting Replicas
	if [ "$1" == "first" ]; then
		START="--first-start"
	else
		START="--start"
	fi
	for REPNUM in $(seq $REPLICAS); do
		echo Trying to start set $REPNUM

		./startrepl.sh ${IPV6} -d ${MONGOPATH} --ver ${MONGOVER/-/} --number $REPNUM --name shardset --replicas 3 ${START} &
		
	done
	echo taking a snooze while we wait
	wait
	sleep 60
fi
}
function launchConfigServers() {
	echo Launch config servers

	checkPidRunning mongod-config-?.pid

	for la in 1 2 3; do 
		if [ ! -d /data/config-${la} ]; then
			mkdir -p /data/config-${la}
		fi
		echo Launching config server $la
		${MONGOPATH}/mongod${MONGOVER} ${IPV6} --configsvr --dbpath /data/config-${la} --port 2793${la} --logpath ./mongod-2793$la.log  --pidfilepath $(pwd)/mongod-config-${la}.pid --fork
	done
	sleep 5
}
function launchMongod() {
if [ $REPLICAS -eq 0 ]; then

	echo Launch mongods
	checkPidRunning mongod?.pid;
	for la in $(seq ${SHARDS}); do 
		if [ ! -d /data/shard-${la} ]; then
			mkdir -p /data/shard-${la}
		fi
		echo Launching mongods $la
		${MONGOPATH}/mongod${MONGOVER} ${IPV6} --shardsvr --dbpath /data/shard-${la} --port 2794${la} --logpath ./mongod-2794$la.log  --pidfilepath $(pwd)/mongod${la}.pid --fork
	done
fi
}
function launchMongos () {
	echo starting mongos version $MONGOVER
	checkPidRunning mongods.pid;
	# launch mongos on standard port
	${MONGOPATH}/mongos${MONGOVER} ${IPV6} --configdb localhost:27931,localhost:27932,localhost:27933 $LOGPATH --pidfilepath $(pwd)/mongos.pid --fork
}
function stopMongos() {
	echo killing mongos processes
	for pidfile in mongos*.pid; do
		kill $(cat $pidfile)
		rm $pidfile
	done
}
function stopAll() {
	echo killing all mongod and mongos processes
	for pidfile in mongo*.pid; do
		kill $(cat $pidfile)
		rm $pidfile
	done
}
function cleanup() {
	echo cleaning up database files
	find /data/shard* -type f -exec rm {} \;
	find /data/config* -type f -exec rm {} \;
}
function help () {
	echo "-d directory mongo programs / links are in"
	echo "--ver specific version to run, should match suffixes in directory"
	echo "--stop stop all mongod/mongos processes we started"
	echo "--start starts all mongod/mongos processes we want"
	echo "--first-start starts everything and configures sharding"
	echo "--cleanup remove the databases from /data/shard* /data/config*"
	echo "--starts just starts the mongos process"
	echo "--stops just stops the mongos process"
	echo "--upgrades runs mongos in foreground with --upgrade option"
}

# Args processing
while [ $# -gt 0 ]; do
	# -d directory mongo programs are in
	if [ "$1" == "-d" ]; then
		shift
		if [ -d $1 ]; then
			MONGOPATH=$1
		else
			echo $1 is not a valid path
			exit -1
		fi
		# --ver specific version to run
	elif [ "$1" == "--auth" ]; then
		IPV6=" --keyFile $(pwd)/db.key"
	elif [ "$1" == "" ]; then
		IPV6="--ipv6"
	elif [ "$1" == "--syslog" ]; then
		LOGPATH="--syslog"
	elif [ "$1" == "--ver" ]; then
		shift
		MONGOVER="-${1}"
	elif [ "$1" == "--shards" ]; then
		shift
		SHARDS="${1}"
	elif [ "$1" == "--replicas" ]; then
		shift
		REPLICAS="${1}"
	elif [ "$1" == "--cleanup" ]; then
		CLEANUP=1
	elif [ "$1" == "--setupshard" ]; then
		COMMAND=setupshards
	elif [ "$1" == "--start" ]; then
		COMMAND=start
	elif [ "$1" == "--first-start" ]; then
		COMMAND=first-start
	elif [ "$1" == "--stop" ]; then
		COMMAND=stop
	elif [ "$1" == "--starts" ]; then
		COMMAND=starts
	elif [ "$1" == "--stops" ]; then
		COMMAND=stops
	elif [ "$1" == "--upgrades" ]; then
		COMMAND=upgrades
	else
		echo
		echo $1 is not a valid option. Try one of these instead:
		echo
		help
		exit
	fi
	shift
done


if [ "$COMMAND" == "start" ]; then
	launchConfigServers
	startReplicas
	launchMongod
	launchMongos

elif [ "$COMMAND" == "first-start" ]; then
	launchConfigServers
	startReplicas first
	launchMongod
	launchMongos
	setupShards

elif [ "$COMMAND" == "starts" ]; then
	launchMongos

elif [ "$COMMAND" == "upgrades" ]; then
	mongosUpgrade

elif [ "$COMMAND" == "setupshards" ]; then
	setupShards	

elif [ "$COMMAND" == "stop" ]; then
	stopAll

elif [ "$COMMAND" == "stops" ]; then
	stopMongos

else
	echo "you need to specify a command to run"
fi
if [ "$CLEANUP" == "1" ]; then
	cleanup
fi

