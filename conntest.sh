#!/bin/bash

while [ 2 ]; do
	for i in $(seq 200); do
		python reader.py &
	done
	echo Waiting....
	wait
	echo Collected!
	sleep 20
done
