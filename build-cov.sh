#!/bin/bash
#Defaults
LCOV_OUT=./lcov-output
LCOV_TMP=.
BRANCH=master
BUILD_DIR=./mongo
DO_CLEAN=0
DO_PULL=0
DO_PATCH=0
DO_CO=0
DO_GIT=1
DO_BUILD=1
DO_TESTS=1
DO_COV=1

function error_disp() {
echo '===================================================='
echo -n \t Step $1 failed, check above for deets
echo '===================================================='
}

function do_git_tasks() {
    cd $BUILD_DIR
    if [ $DO_CO != 0 ]; then
        git checkout $BRANCH
    fi
    if [ $DO_CLEAN != 0 ]; then
        git clean -fqdx
    fi
    if [ $DO_PULL != 0 ]; then
        git pull
        if [ $? != 0 ] && [ $DO_ANYWAY != 1 ]; then
            echo "Git seems to be up to date, use -f to do it anyway"
            exit 1
        fi
    fi  
    if [ $DO_PATCH != 0 ]; then
    	patch -p1 $PATCH
    fi
}

function run_build() {
    scons  -j8 --dd --gcov all
    if [ $? != 0 ]; then
        error_disp $test
        exit 1
    fi  
}

function run_tests() {
    # figure out what to do with this gcc 4.8.1 specific mess
    for test in smoke smokeCppUnittests smokeDisk smokeTool smokeAuth  smokeClient test; do 
        scons --dd --gcov $test; 
        if [ $? != 0 ]; then
            error_disp $test
            echo $test returned $?;
        fi  
    done

    for test in smokeJs smokeTool smokeReplSets smokeDur mongosTest smokeSharding smokeRepl smokeClone; do 
        scons --dd --gcov $test; 
        #LD_LIBRARY_PATH=/usr/local/lib:/usr/lib:/usr/local/lib64:/usr/lib64 scons --dd --gcov $test; 
        if [ $? != 0 ]; then
            error_disp $test
            echo $test returned $?;
        fi  
    done

    python buildscripts/smoke.py aggregation
    python buildscripts/smoke.py js
}

function run_coverage () {
    REV=$(git rev-parse --short HEAD)
    mkdir -p $LCOV_OUT/$REV
    lcov -t "$REV" -o $LCOV_TMP/stage1.info -c -d ./build/linux2/dd/gcov/mongo/ -b src/mongo/ --derive-func-data --rc lcov_branch_coverage=1
    if [ $? != 0 ]; then
        error_disp $test
        echo lcov pass 1 failed
    fi  
    cd $LCOV_TMP
    lcov --extract stage1.info \*mongo/src/mongo\* -o  stage2.info --rc lcov_branch_coverage=1
    if [ $? != 0 ]; then
        error_disp $test
        echo lcov pass 2 failed
    fi  
    lcov --remove stage2.info \*test\* -o  stage3.info --rc lcov_branch_coverage=1
    if [ $? != 0 ]; then
        error_disp $test
        echo lcov pass 3 failed
    fi  
    genhtml -o $LCOV_OUT/$REV -t "Branch: $BRANCH Commit:$REV" --highlight stage3.info --rc lcov_branch_coverage=1
    if [ $? != 0 ]; then
        error_disp $test
        echo genhtml failed
    fi  
}

function help () {
    echo code coverage helper, usage: $0 
    echo '-p "path" html output path'
    echo '-t "path" temp directory for coverage .info files'
    echo '-b branch to work on'
    echo '-c check out branch'
    echo '-x run git clean -fqdx before build'
    echo '-p run git pull before build'
    echo '--patch "patch path/name" patch to apply before build (not implemented yet)'
    echo '--build-dir "path" place where MongoDB source lives'
    echo '--skip-git skip over all the git phases'
    echo '--skip-build skip the build phase'
    echo "--skip-test don\'t run tests"
    echo '--skip-coverage coverage reports will not be run'
}


if [ $# -eq 0 ]; then
    help
    exit 1
fi

while [ $# -gt 0 ]; do
    # -d directory to drop lcov results
    if [ "$1" == "-d" ]; then
        shift
        if [ -d $1 ]; then
            LCOV_OUT=$1
        else
            echo $1 is not a valid path
            exit -1
        fi
    elif [ "$1" == "-t" ]; then
        shift
        if [ -d $1 ]; then
            LCOV_TMP=$1
        else
            echo $1 is not a valid path
            exit -1
        fi
    elif [ "$1" == "--build-dir" ]; then
        shift
        if [ -d $1 ]; then
            BUILD_DIR=$1
        else
            echo $1 is not a valid path
            exit -1
        fi
    elif [ "$1" == "--patch" ]; then
        shift
	DO_PATCH=1
        if [ -e $1 ]; then
            PATCH=$1
        else
            echo $1 patch file does not exist
            exit -1
        fi
    elif [ "$1" == "-b" ]; then
        shift
        BRANCH=$1
    elif [ "$1" == "--patch" ]; then
        shift
        PATCH=$1
    elif [ "$1" == "-x" ]; then
        DO_CLEAN=1
    elif [ "$1" == "-p" ]; then
        DO_PULL=1
    elif [ "$1" == "-c" ]; then
        DO_CO=1
    elif [ "$1" == "-f" ]; then
        DO_ANYWAY=1
    elif [ "$1" == "--skip-git" ]; then
        DO_GIT=0
    elif [ "$1" == "--skip-build" ]; then
        DO_BUILD=0
    elif [ "$1" == "--skip-test" ]; then
        DO_TESTS=0
    elif [ "$1" == "--skip-coverage" ]; then
        DO_COV=0
    elif [ "$1" == "--help" ]; then
        help
        exit
    else
        echo unrecognized option
        help
        exit
    fi
    shift
done

if [ $DO_GIT != 0 ]; then
    do_git_tasks
fi
if [ $DO_BUILD != 0 ]; then
    run_build
fi
if [ $DO_TESTS != 0 ]; then
    run_tests
fi
if [ $DO_COV != 0 ]; then
    run_coverage
fi
echo Have a nice day
