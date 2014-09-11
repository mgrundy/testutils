#!/bin/bash

#Defaults
BRANCH=master
BUILD_DIR=$(pwd)
DB_PATH=/data
DO_BUILD=1
DO_CLEAN=0
DO_CO=0
DO_COV=1
DO_GIT=1
DO_JSTEST=1
DO_LOOP=0
DO_PATCH=0
DO_PULL=0
DO_TESTS=1
DO_UNIT=1
ERRORLOG=covbuilderrors.log
LCOV_OUT=./lcov-output
LCOV_TMP=.
MV_PATH=/local/ml
failedtests[${#failedtests[@]}]="Failed Test List:"
# run every friendly test. quota is not a friendly test. jsPerf isn't anymore either
TEST_PLAN="js jsCore repl replSets ssl dur auth aggregation failPoint multiVersion disk sharding tool parallel noPassthrough noPassthroughWithMongod slow1 slow2 sslSpecial" 
REV=0

function error_disp() {
echo '===================================================='
echo -e "\t Step $1 failed, check above for deets"
echo  Step $1 failed >> $ERRORLOG
echo '===================================================='
}

function do_git_tasks() {
    cd $BUILD_DIR
    if [ $DO_GIT != 0 ]; then
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
    fi
    REV=$(git rev-parse --short HEAD)
}

function run_build() {
    cd $BUILD_DIR
    scons --ssl -j${CPUS} --mute --opt=off --gcov all
    # This is the line for custom compiled 4.8.1 on my mac:
    # scons -j8 --opt=off --mute --gcov --cc=/usr/local/bin/gcc --cxx=/usr/local/bin/g++ --cpppath=/usr/local/include/c++/4.8.1/ --libpath=/usr/local/lib --extrapath=/usr/local/lib/gcc/x86_64-apple-darwin12.4.0/4.8.1/ all
    if [ $? != 0 ]; then
        error_disp BUILD
        [ $DO_LOOP == 1 ] && return 1 || exit 1
    fi  
}

function run_unittests() {
    cd $BUILD_DIR
    # Run tests individually so that failures are noted, but bypassed
    #for test in smoke smokeCppUnittests smokeDisk smokeTool smokeAuth  smokeClient test; do 
    # run the unit tests first
    for test in smoke smokeCppUnittests ; do 
        GCOV_PREFIX=/local/gcda/${test} scons --ssl -j${CPUS} --mute --smokedbprefix=$DB_PATH --opt=off --gcov $test; 
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
    cd $BUILD_DIR
    #append multiversion link path
    export PATH=$PATH:$MV_PATH

    # Run every test in the plan
    for test in $TEST_PLAN; do
        echo ===== Running $test =====
        GCOV_PREFIX=/local/gcda/${test} python buildscripts/smoke.py $AUTH $SSL --continue-on-failure --smoke-db-prefix=$DB_PATH $test; 
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
    mkdir -p $LCOV_OUT/$REV

    # $1 is the test
    lcov -t $1 -o $LCOV_TMP/raw-${REV}.info -c -d ./${buildout}  -b src/mongo/ --derive-func-data --rc lcov_branch_coverage=1
    if [ $? != 0 ]; then
        error_disp $test
        echo lcov pass 1 failed
        echo coverage data loss risk, please re-run:
        echo lcov -t $1 -o $LCOV_TMP/raw-${REV}.info -c -d ./${buildout}  -b src/mongo/ --derive-func-data --rc lcov_branch_coverage=1
        [ $DO_LOOP == 1 ] && return 1 || exit 1
    fi  

    # Clean up the coverage data files, that's why we die if phase one fails
    find $buildout -name \*.gcda -exec rm -f {} \;

    cd $LCOV_TMP
    # Clean out the third_party and system libs data
    lcov --extract raw-${REV}.info \*mongo/src/mongo\* -o  lcov-${REV}-${1}.info --rc lcov_branch_coverage=1
    if [ $? != 0 ]; then
        error_disp $test
        mv raw-${REV}.info failed-raw-${REV}-${1}.info
        echo lcov pass 2 failed
        echo run data saved in failed-raw-${REV}-${1}.info
        echo coverage data loss risk, please re-run:
        echo lcov --extract failed-raw-${REV}-${1}.info \*mongo/src/mongo\* -o  lcov-${REV}-${1}.info --rc lcov_branch_coverage=1
        [ $DO_LOOP == 1 ] && return 1 || exit 1
    fi  

    rm raw-${REV}.info

    # Append all the test files to a single for reporting,
    cat lcov-${REV}-*.info > lcov-${REV}.info

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
    echo '--loop run all phases repeatedly on change in git hash'
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

# wonder if I should switch to getopt and case this mess up
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
    elif [ "$1" == "--loop" ]; then
        DO_LOOP=1
        DO_PULL=1
        DO_CLEAN=1
    elif [ "$1" == "--skip-git" ]; then
        DO_GIT=0
    elif [ "$1" == "--skip-build" ]; then
        DO_BUILD=0
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

# Get CPU count to populate -j on builds
if [ $(uname) == "Darwin" ]; then
    CPUS=$(sysctl machdep.cpu.core_count| cut -f2 -d" ")
else
    CPUS=$(cat /proc/cpuinfo | grep -c processor)
fi

# Main execution of work items:
if [ $DO_LOOP == 1 ]; then
    while [ 1 ]; do
        OLD_REV=$REV
        do_git_tasks
        if [ $OLD_REV != $REV ]; then
            run_build
            if [ $? -eq 0 ]; then
                run_unittests
                if [ $? -eq 0 ]; then
                    run_jstests
                fi
            fi
        else
            echo New git revision not found, sleeping
            time
            sleep 300
        fi
    done
else
    # skip logic now in do_git_tasks, always call
    do_git_tasks
    if [ $DO_BUILD != 0 ]; then
        run_build
    fi
    if [ $DO_TESTS != 0 ]; then
        if [ $DO_UNIT != 0 ]; then
            run_unittests
        fi
        if [ $DO_JSTEST != 0 ]; then
            run_jstests
        fi
    fi
    # only run if tests aren't
    if [ $DO_COV != 0 ]; then
        run_coverage report_only
    fi

    if [ $DO_TESTS != 0 ]; then
        echo ${failedtests[@]}
    fi
fi

