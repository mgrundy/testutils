#!/bin/bash
#Defaults
LCOV_OUT=./lcov-output
LCOV_TMP=.
BRANCH=master
BUILD_DIR=$(pwd)
DO_CLEAN=0
DO_PULL=0
DO_PATCH=0
DO_CO=0
DO_GIT=1
DO_BUILD=1
DO_TESTS=1
DO_UNIT=1
DO_COV=1
DB_PATH=/data
MV_PATH=/local/ml
ERRORLOG=covbuilderrors.log
failedtests[${#failedtests[@]}]="Failed Test List:"

function error_disp() {
echo '===================================================='
echo -e "\t Step $1 failed, check above for deets"
echo  Step $1 failed >> $ERRORLOG
echo '===================================================='
}

function do_git_tasks() {
    cd $BUILD_DIR
    if [ $DO_CO != 1 ]; then
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
        patch -N -p1 < $PATCH
        if [ $? != 0 ]; then
            echo PATCH $PATCH has issues. Deal with it plz.
            exit
        fi
    fi
}

function run_build() {
    cd $BUILD_DIR
    scons  -j8 --mute --opt=off --gcov all
    # This is the line for custom compiled 4.8.1 on my mac:
    # scons -j8 --opt=off --mute --gcov --cc=/usr/local/bin/gcc --cxx=/usr/local/bin/g++ --cpppath=/usr/local/include/c++/4.8.1/ --libpath=/usr/local/lib --extrapath=/usr/local/lib/gcc/x86_64-apple-darwin12.4.0/4.8.1/ all
    if [ $? != 0 ]; then
        error_disp BUILD
        exit 1
    fi  
}

function run_tests() {
    cd $BUILD_DIR
    # Run tests individually so that failures are noted, but bypassed
    #for test in smoke smokeCppUnittests smokeDisk smokeTool smokeAuth  smokeClient test; do 
    # run the unit tests first
    for test in smoke smokeCppUnittests test; do 
        scons -j8 --mute --smokedbprefix=$DB_PATH --opt=off --gcov $test; 
        if [ $? != 0 ]; then
            error_disp $test
            echo $test returned $?;
            failedtests[${#failedtests[@]}]=$test
            # put in option to fail here
            # exit
        fi  
    done

    if [ $DO_COV != 0 ]; then
        run_coverage "Unit Tests"
    fi
    # run every friendly test. quota is not a friendly test. jsPerf isn't anymore either
    #for test in js jsPerf disk parallel clone repl replSets dur auth sharding tool aggregation multiVersion failPoint ssl jsSlowNightly jsSlowWeekly ; do

    #append multiversion link path
    export PATH=$PATH:$MV_PATH

    # taking out the slows for a couple days
    for test in js clone repl replSets dur auth aggregation failPoint multiVersion disk parallel sharding tool "--auth aggregation" ; do
#    for test in multiVersion js jsPerf disk parallel clone repl replSets dur auth sharding tool aggregation failPoint ssl; do
        echo ===== Running $test =====
        python buildscripts/smoke.py --smoke-db-prefix=$DB_PATH $test; 
        if [ $? != 0 ]; then
            error_disp $test
            failedtests[${#failedtests[@]}]=$test
            echo $test returned $?;
        fi  
        # Takes longer, but gives us incremental coverage results
        if [ $DO_COV != 0 ]; then
            run_coverage $test
        fi
    done
}

function run_coverage () {
    cd $BUILD_DIR
    buildout=$(dirname $(find build -type f -perm +111 -name mongod))
    REV=$(git rev-parse --short HEAD)
    mkdir -p $LCOV_OUT/$REV
    lcov -t "$REV" -o $LCOV_TMP/complete-${REV}.info -c -d ./${buildout}  -b src/mongo/ --derive-func-data --rc lcov_branch_coverage=1
    if [ $? != 0 ]; then
        error_disp $test
        echo lcov pass 1 failed
    fi  
    cd $LCOV_TMP
    lcov --extract complete-${REV}.info \*mongo/src/mongo\* -o  lcov-${REV}.info --rc lcov_branch_coverage=1
    if [ $? != 0 ]; then
        error_disp $test
        echo lcov pass 2 failed
    fi  
# We had been filtering out the tests, but that doesn't help us understand
# which tests ran.
#    lcov --remove stage2.info \*test\* -o  stage3.info --rc lcov_branch_coverage=1
#    if [ $? != 0 ]; then
#        error_disp $test
#        echo lcov pass 3 failed
#    fi  
    genhtml -o $LCOV_OUT/$REV -t "Branch: $BRANCH Commit:$REV $@" --highlight lcov-${REV}.info --rc lcov_branch_coverage=1
    if [ $? != 0 ]; then
        error_disp $test
        echo genhtml failed
    fi
    # XXX This needs to be not so suck
    cd $LCOV_OUT 
    echo '<html><body>' > index.html
    ls -thor | grep -v index | awk '{print "<a href=\""$8"\" >"$8" " $5" "$6" "$7"</a><br>"}' >> index.html
    echo '</body></html>'>> index.html

    cd $BUILD_DIR
}

function help () {
    echo code coverage helper, usage: $0 
    echo '-d "path" html output path'
    echo '-t "path" temp directory for coverage .info files'
    echo '-b branch to work on'
    echo '-c check out branch'
    echo '-x run git clean -fqdx before build'
    echo '-p run git pull before build'
    echo '--patch "patch path/name" patch to apply before build (not implemented yet)'
    echo '--build-dir "path" place where MongoDB source lives'
    echo '--mv-dir "path" multiversion link directory'
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
    elif [ "$1" == "--mv-dir" ]; then
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
    # TODO
    elif [ "$1" == "--skip-unit" ]; then
        DO_UNIT=0
    elif [ "$1" == "--skip-test" ]; then
        DO_TESTS=0
    elif [ "$1" == "--skip-coverage" ]; then
        DO_COV=0
    elif [ "$1" == "--help" ]; then
        help
        exit
    else
        echo $1 : unrecognized option
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

if [ $DO_TESTS != 0 ]; then
    echo ${failedtests[@]}
fi

