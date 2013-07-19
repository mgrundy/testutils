#!/bin/bash

MONGOPATH=.
REPLICAS=4
REPLSETNAME=trending
REPLSETNUM=0
function setupReplication () {
	# Setting up replication
	${MONGOPATH}/mongo${MONGOVER} ${IPV6} admin --port 27${REPLSETNUM}11 --eval "cfg={\"_id\":\"${REPLSETNAME}${REPLSETNUM}\",\"members\":[{\"_id\": 0,\"host\":\"localhost:27${REPLSETNUM}11\",\"priority\":10},]}; printjson(rs.initiate(cfg));"
	sleep 60
	${MONGOPATH}/mongo${MONGOVER} ${IPV6} admin --port 27${REPLSETNUM}11 --eval "printjson(rs.status());"
	for repl in $(seq 2 ${REPLICAS}); do
		echo adding repl ${repl}
		${MONGOPATH}/mongo${MONGOVER} ${IPV6} admin --port 27${REPLSETNUM}11 --eval "printjson(rs.add(\"localhost:27${REPLSETNUM}1${repl}\"))"
	done
	echo Waiting for it all to come up
	sleep 60

}

function setupArbiter() {

	if [ "$ARB" == "true" ]; then
		if [ ! -d /data/${REPLSETNAME}${REPLSETNUM}-arb ]; then
			mkdir -p /data/${REPLSETNAME}${REPLSETNUM}-arb
		fi
		echo Launching arb mongods $la
		${MONGOPATH}/mongod${MONGOVER} ${IPV6} --dbpath /data/${REPLSETNAME}${REPLSETNUM}-arb --replSet ${REPLSETNAME}${REPLSETNUM} --port 27${REPLSETNUM}19 --logpath ./mongod-27${REPLSETNUM}19.log  --pidfilepath $(pwd)/mongod-${REPLSETNAME}${REPLSETNUM}-9.pid --fork
		${MONGOPATH}/mongo${MONGOVER} ${IPV6} admin --port 27${REPLSETNUM}11 --eval "printjson(rs.addArb(\"localhost:27${REPLSETNUM}19\"))"
	fi
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
function launchMongod() {
	echo Launch mongods
	checkPidRunning mongod-${REPLSETNAME}${REPLSETNUM}-*.pid ;
	for la in $(seq ${REPLICAS}); do 
		if [ ! -d /data/${REPLSETNAME}${REPLSETNUM}-${la} ]; then
			mkdir -p /data/${REPLSETNAME}${REPLSETNUM}-${la}
		fi
		echo Launching mongods $la
		${MONGOPATH}/mongod${MONGOVER} ${IPV6} --dbpath /data/${REPLSETNAME}${REPLSETNUM}-${la} --replSet ${REPLSETNAME}${REPLSETNUM} --port 27${REPLSETNUM}1${la} --logpath ./mongod-27${REPLSETNUM}1$la.log  --pidfilepath $(pwd)/mongod-${REPLSETNAME}${REPLSETNUM}-${la}.pid --fork
	done
	if [ "$ARB" == "true" ]; then
		echo Launching arb mongods $la
		${MONGOPATH}/mongod${MONGOVER} ${IPV6} --dbpath /data/${REPLSETNAME}${REPLSETNUM}-arb --replSet ${REPLSETNAME}${REPLSETNUM} --port 27${REPLSETNUM}19 --logpath ./mongod-27${REPLSETNUM}19.log  --pidfilepath $(pwd)/mongod-${REPLSETNAME}${REPLSETNUM}-9.pid --fork
	fi
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
	find /data/${REPLSETNAME}${REPLSETNUM}-* -type f -exec rm {} \;
}
function help () {
	echo "-d directory mongo programs / links are in"
	echo "--ver specific version to run, should match suffixes in directory"
	echo "--stop stop all mongod/mongos processes we started"
	echo "--start starts all mongod/mongos processes we want"
	echo "--first-start starts everything and configures repling"
	echo "--cleanup remove the databases from /data/repl* /data/config*"
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
	elif [ "$1" == "--ipv6" ]; then
		shift
		IPV6="--ipv6"
	elif [ "$1" == "--ver" ]; then
		shift
		MONGOVER="-${1}"
	elif [ "$1" == "--name" ]; then
		shift
		REPLSETNAME="${1}"
	elif [ "$1" == "--number" ]; then
		shift
		REPLSETNUM="${1}"
	elif [ "$1" == "--replicas" ]; then
		shift
		REPLICAS="${1}"
	elif [ "$1" == "--arb" ]; then
		ARB=true
	elif [ "$1" == "--cleanup" ]; then
		CLEANUP=1
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
	launchMongod

elif [ "$COMMAND" == "first-start" ]; then
	launchMongod
	setupReplication
	setupArbiter

elif [ "$COMMAND" == "stop" ]; then
	stopAll

else
	echo "you need to specify a command to run"
fi
if [ "$CLEANUP" == "1" ]; then
	cleanup
fi

