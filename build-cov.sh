#!/bin/bash
#Defaults
which lcov
if [ $(uname) == "Darwin" ]; then
    CPUS=$(sysctl machdep.cpu.core_count| cut -f2 -d" ")
else
    CPUS=$(cat /proc/cpuinfo | grep -c processor)
fi
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
DO_JSTEST=1
DO_UNIT=1
DO_COV=1
DB_PATH=/data
MV_PATH=/local/ml
ERRORLOG=covbuilderrors.log
failedtests[${#failedtests[@]}]="Failed Test List:"
# run every friendly test. quota is not a friendly test. jsPerf isn't anymore either
TEST_PLAN="js clone repl replSets ssl dur auth aggregation failPoint multiVersion disk sharding tool parallel" 

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
    scons --ssl -j${CPUS} --mute --opt=off --gcov all
    # This is the line for custom compiled 4.8.1 on my mac:
    # scons -j8 --opt=off --mute --gcov --cc=/usr/local/bin/gcc --cxx=/usr/local/bin/g++ --cpppath=/usr/local/include/c++/4.8.1/ --libpath=/usr/local/lib --extrapath=/usr/local/lib/gcc/x86_64-apple-darwin12.4.0/4.8.1/ all
    if [ $? != 0 ]; then
        error_disp BUILD
        exit 1
    fi  
}

function run_unittests() {
    cd $BUILD_DIR
    # Run tests individually so that failures are noted, but bypassed
    #for test in smoke smokeCppUnittests smokeDisk smokeTool smokeAuth  smokeClient test; do 
    # run the unit tests first
    for test in smoke smokeCppUnittests smokeClient test; do 
        scons --ssl -j${CPUS} --mute --smokedbprefix=$DB_PATH --opt=off --gcov $test; 
        if [ $? != 0 ]; then
            error_disp $test
            echo $test returned $?;
            failedtests[${#failedtests[@]}]=$test
            # put in option to fail here
            # exit
        fi  
        run_coverage $test 
    done

}

function run_jstests() {
    #append multiversion link path
    export PATH=$PATH:$MV_PATH

    # Run every test in the plan
    for test in $TEST_PLAN; do
        echo ===== Running $test =====
        python buildscripts/smoke.py $AUTH $SSL --continue-on-error --smoke-db-prefix=$DB_PATH $test; 
        if [ $? != 0 ]; then
            error_disp $test
            failedtests[${#failedtests[@]}]=$test
            echo $test returned $?;
        fi  
        # Takes longer, but gives us incremental coverage results
        run_coverage $test
    done
}

function run_coverage () {
    # Make sure we're supposed to be here
    if [ $DO_COV -eq 0 ]; then
        return
    fi
    # figure out where the binaries are
    cd $BUILD_DIR
    buildout=$(dirname $(find build -type f -perm +111 -name mongod))
    REV=$(git rev-parse --short HEAD)
    mkdir -p $LCOV_OUT/$REV

    # $1 is the test
    lcov -t $1 -o $LCOV_TMP/raw-${REV}.info -c -d ./${buildout}  -b src/mongo/ --derive-func-data --rc lcov_branch_coverage=1
    if [ $? != 0 ]; then
        error_disp $test
        echo lcov pass 1 failed
        echo coverage data loss risk, please re-run:
        echo lcov -t $1 -o $LCOV_TMP/raw-${REV}.info -c -d ./${buildout}  -b src/mongo/ --derive-func-data --rc lcov_branch_coverage=1
        exit
    fi  

    # Clean up the coverage data files, that's why we die if phase one fails
    find $buildout -name \*.gcda -exec rm -f {} \;
    cd $LCOV_TMP
    
    # Clean out the third_party and system libs data
    lcov --extract raw-${REV}.info \*mongo/src/mongo\* -o  lcov-${REV}-${1}.info --rc lcov_branch_coverage=1
    if [ $? != 0 ]; then
        error_disp $test
        echo lcov pass 2 failed
        echo coverage data loss risk, please re-run:
        echo lcov --extract raw-${REV}.info \*mongo/src/mongo\* -o  lcov-${REV}-${1}.info --rc lcov_branch_coverage=1
        exit
    fi  

    rm raw-${REV}.info

    # Append all the test files to a single for reporting,
    # first create an arg list of files to merge
    for la in lcov-${REV}-*.info; do
        covlist[${#covlist[@]}]="-a" 
        covlist[${#covlist[@]}]=$la 
    done
    # Then run command with proper args. Supposedly we can just cat the files together
    # We'll try that out later and see which is faster
    lcov ${covlist[@]} -o lcov-${REV}.info --rc lcov_branch_coverage=1
    if [ $? != 0 ]; then
        error_disp $test
        echo lcov pass 3 failed
    fi  

    # Run genhtml with 
    genhtml -s -o $LCOV_OUT/$REV -t "Branch: $BRANCH Commit:$REV $@" --highlight lcov-${REV}.info --rc lcov_branch_coverage=1
    if [ $? != 0 ]; then
        error_disp $test
        echo genhtml failed
    fi
    # XXX This needs to be not so suck
    # Let's change this to calling another script
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
    echo '--auth run jstests with --auth parameter to smoke'
    echo '--patch "patch path/name" patch to apply before build (not implemented yet)'
    echo '--build-dir "path" place where MongoDB source lives'
    echo '--mv-dir "path" multiversion link directory'
    echo '--skip-git skip over all the git phases'
    echo '--skip-build skip the build phase'
    echo '--skip-coverage coverage reports will not be run'
    echo "--skip-jstest don\'t run jstests"
    echo "--skip-test don\'t run tests, but run coverage if not skipped"
    echo "--skip-unit don\'t run unit tests"
    echo "--ssl run jstests with ssl support"
    echo "--test-plan \"list of js test suites\" to run"
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
            MV_PATH=$1
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
    elif [ "$1" == "--skip-jstest" ]; then
        DO_JSTEST=0
    elif [ "$1" == "--skip-test" ]; then
        DO_TESTS=0
        DO_COV=1
    elif [ "$1" == "--skip-coverage" ]; then
        DO_COV=0
    elif [ "$1" == "--test-plan" ]; then
        shift
        TEST_PLAN=$1
    elif [ "$1" == "--ssl" ]; then
        SSL="--use-ssl"
    elif [ "$1" == "--auth" ]; then
        AUTH=--auth  
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

# quick check for lcov
if [ $? -ne 0 ]; then
    error_disp "LCOV check"
    exit 1
fi

if [ $DO_GIT != 0 ]; then
    do_git_tasks
fi
if [ $DO_BUILD != 0 ]; then
    run_build
fi
if [ $DO_TESTS != 0 ]; then
    if [ $DO_UNIT != 0 ]; then
        run_unittests
    elif [ $DO_JSTEST != 0 ]; then
        run_jstests
    fi
fi
# only run if tests aren't
if [ $DO_COV != 0 ]; then
    run_coverage report_only
fi
echo Have a nice day

if [ $DO_TESTS != 0 ]; then
    echo ${failedtests[@]}
fi

