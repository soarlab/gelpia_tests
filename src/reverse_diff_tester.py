#!/usr/bin/env python3

import argparse
import glob
import multiprocessing
import re
import struct
import subprocess
import sys
import time

import multiprocessing.pool as pool
import os.path as path

from color_printing import *


STATUS_FMT = {
    # Tool crashed
    "CRASH"     : lambda t : red(bold(t)),
    # Tool gave incorrect answer
    "INCORRECT" : lambda t : red(bold(t)),
    # Tool completed running, but true answer is unknown
    "UNKNOWN"   : lambda t : yellow(t),
    # Tool completed with correct answer
    "CORRECT"   : lambda t : green(t),
}

STATUS_COUNT = {k:0 for k in STATUS_FMT}




def mass_replace(string, replacement):
    '''
    Replaces all left items in string with corresponding right items.
    replacement is a list of string pairs
    '''
    for old, new in replacement:
        string = string.replace(old, new)
    return string


def compare_result(expected, result):
    '''
    Compares equality of two expressions, returnin a state string.
    inputs will be canonicalized before comparison
    '''
    if expected is None:
        return "UNKNOWN"
    replacement = [
        (" ", ""),
        ("\"", ""),
        ("Integer",""),
        ("Input",""),
        ("'",""),
        (",",""),
        ("neg", "-"),
        ("[","("),
        ("]",")"),
        ("powi","pow"),
        ("(SymbolicConstpi)", "(pi)"),
        ("(ConstantInterval(Float3.141592653589793115997963468544185161590576171875)(Float3.141592653589793560087173318606801331043243408203125))", "(pi)"),
    ]
    expected_string = mass_replace("".join(expected), replacement)
    result_string = mass_replace("".join(result), replacement)
    expected_list = sorted([line for line in expected_string.splitlines()
                            if line!=""])
    result_list = sorted([line for line in result_string.splitlines()
                          if line!=""])
    if expected_list == result_list:
        return "CORRECT"
    else:
        print(expected_list)
        print(result_list)
        return "INCORRECT"


def get_expected(filename):
    ''' Grabs all answers from given file '''
    with open(filename, 'r') as f:
        data = f.read()

    ansmatch = re.findall(r'\#[ \t]*answer:[ \t]*([^\n]+)', data)

    if ansmatch:
        return [a + "\n" for a in ansmatch]
    else:
        return None


def process_test(cmd, test, expected):
    '''
    Runs given test and compares the result to the expected result
    returns a status string and a state string
    '''
    cmd = " ".join(cmd)

    try:
        t0 = time.time()
        p = subprocess.Popen(cmd, shell=True,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err  = p.communicate()
        out = out.decode('utf-8')
        err = err.decode('utf-8')
        retcode = p.returncode
        elapsed = time.time() - t0

        # get the test results
        result = (out + err).splitlines(True)
        state = compare_result(expected, result)

    except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        print("ERROR: Unable to run command")
        print("\ncommand used:")
        print(cmd)
        print("python exception:")
        print(e)
        print(exc_type, fname, exc_tb.tb_lineno)
        try:
            print("\ncommand output: {}".format(out))
        except:
            pass
        try:
            print("\ncommand error: {}".format(err))
        except:
            pass

        result = ""
        state = "CRASH"

    printstate = STATUS_FMT[state](state)
    expected_str = ['unknown'] if expected is None else expected

    str_result = "Test: {}\n".format(test)
    str_result += "State: {}\n".format(printstate)
    str_result += "Expected:\n  {}".format("  ".join(expected_str))
    str_result += "Result:\n  {}".format("  ".join(result))
    str_result += "Time: {}\n\n".format(elapsed)

    return str_result, state


def tally_result(tup):
    ''' Combines results of test runners '''
    str_result, state = tup
    if VERBOSE == True or state in {"INCORRECT", "CRASH"}:
        print(str_result, flush=True)
    STATUS_COUNT[state] += 1


VERBOSE = False
def main():
    global VERBOSE

    t0 = time.time()
    num_cpus = multiprocessing.cpu_count()

    # configure the CLI
    parser = argparse.ArgumentParser()
    parser.add_argument("--procs", action="store", dest="n_procs",
                        default=num_cpus, type=int,
                        help="Use the selected number of procs in parallel")
    parser.add_argument("--rd", type=str, help="Reverse diff pass script",
                        required=True)
    parser.add_argument("--skip", action='store_const',
                        const=True, default=False,
                        help="Skip tests with unknown answers")
    parser.add_argument("-v", action='store_const',
                        const=True, default=False,
                        help="Print all test outputs")
    parser.add_argument("benchmark_dir")
    args = parser.parse_args()

    exe = args.rd
    VERBOSE = args.v
    base = path.basename(args.rd)

    try:
        # start the tests
        print("Running benchmarks...")

        # start processing the tests.
        results = []
        tests = sorted(glob.glob(path.join(args.benchmark_dir,"**"),
                                 recursive=True))
        tests = [f for f in tests if f.endswith(".dop")]
        total = len(tests)
        print("{} benchmarks to process".format(total))

        n_procs = min(total+1, args.n_procs)
        print("Creating Pool with '{}' Workers\n".format(n_procs), flush=True)
        p = multiprocessing.pool.ThreadPool(processes=n_procs)

        for test in tests:
            # build up the subprocess command
            cmd = ["python3", exe, test, "test"]
            expected = get_expected(test)
            if args.skip and expected=="":
                STATUS_COUNT["SKIPPED"] += 1
                if VERBOSE:
                    printstate = STATUS_FMT["SKIPPED"]("SKIPPED")
                    print("{}\n".format(test))
                    print("State:\n  {}\n\n".format(printstate))
                continue

            r = p.apply_async(process_test,
                              args=(cmd[:], test, expected),
                              callback=tally_result)

            results.append(r)

        # keep the main thread active while there are active workers
        for r in results:
            r.wait()

    except KeyboardInterrupt:
        print("\nCaught KeyboardInterrupt, terminating workers")
        p.terminate() # terminate any remaining workers
        p.join()
    else:
        print("\nQuitting normally")
        # close the pool. this prevents any more tasks from being submitted.
        p.close()
        p.join() # wait for all workers to finish their tasks

    # log the elapsed time
    elapsed_time = time.time() - t0
    print(' ELAPSED TIME [{}]\n'.format(round(elapsed_time, 2)))

    # log the test results
    statuses = sorted(STATUS_COUNT.keys())
    maxlabel = max([len(s) for s in statuses])
    fmtstr = "{{:{}}}".format(maxlabel)
    tests_ran = sum(STATUS_COUNT.values())
    for status in statuses:
        label = fmtstr.format(status)
        print("{} : {}".format(STATUS_FMT[status](label), STATUS_COUNT[status]))
    label = fmtstr.format("TOTAL")
    print("\n{} : {}".format(label, tests_ran))

    if (total != sum(STATUS_COUNT.values())):
        print(red("\nERROR:")+"number of tests ran({}) does not equal total tests({}), there is a bug in {}".format(tests_ran, total, sys.argv[0]))


if __name__=="__main__":
    main()
