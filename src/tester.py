#!/usr/bin/env python3


from math import isnan, isinf, copysign

import os
import argparse
import glob
import multiprocessing
import os.path as path
import multiprocessing.pool as pool
import re
import struct
import subprocess
import sys
import time

from color_printing import *

class Object:
    pass

STATUS_ORDER = ["CRASH", "BROKEN", "FAILED",
                "BAD_FAR", "BAD_CLOSE",
                "TIMEOUT",
                "FAR", "CLOSE",
                "EXACT",
                "SKIPPED", "UNKNOWN",
                "TIMEOUT"]
STATUS_FMT = {
  # Tool crashed
  "CRASH"     : lambda t : red(bold(t)),
  # Tool completed running, but true answer is unknown
  "UNKNOWN"   : lambda t : yellow(t),
  # Test was skipped
  "SKIPPED"   : lambda t : bold(t),
  # Test reached timeout
  "TIMEOUT"   : lambda t : cyan(t),
  # Answer was exactly correct
  "EXACT"     : lambda t : green(t),
  # Answer was close according to metric used
  "CLOSE"     : lambda t : green(t),
  # Answer was far according to metric used
  "FAR"       : lambda t : green(bold(t)),
  # Non-Gelpia was used and answer was wrong, and close according to metric used
  "BAD_CLOSE" : lambda t : magenta(t),
  # Non-Gelpia was used and answer was wrong, and far according to metric used
  "BAD_FAR"   : lambda t : magenta(bold(t)),
  # Gelpia was used and answer was wrong
  "BROKEN"    : lambda t : red(bold(t)),
  # Did not crash, but no output found
  "FAILED"    : lambda t : red(t),
}

STATUS_COUNT = {k:0 for k in STATUS_FMT}



def float_diff(expected, result):
    abs_diff = result - expected
    if expected == 0.0:
        if result == 0.0:
            rel_diff = 0.0
        else:
            rel_diff = float("inf") if abs_diff > 0.0 else float("-inf")
    elif (isinf(expected)
          and isinf(result)
          and copysign(1, expected) == copysign(1, result)):
          abs_diff = 0.0
          rel_diff = 0.0
    else:
        rel_diff = abs_diff / abs(expected)
    return abs_diff, rel_diff


def calculate_result(args, test_state, strict_bounds):
    result = test_state.result
    if result[0] is None or result[1] is None:
        if test_state.elapsed > args.timeout:
            test_state.state = "TIMEOUT"
            test_state.abs_diff = float("nan")
            test_state.rel_diff = float("nan")
            return
        else:
            test_state.state = "FAILED"
            test_state.abs_diff = float("nan")
            test_state.rel_diff = float("nan")
            return

    if args.min:
        expected_point = test_state.expected[0]
    else:
        expected_point = test_state.expected[1]

    if expected_point is None:
        test_state.state = "UNKNOWN"
        test_state.abs_diff = float("nan")
        test_state.rel_diff = float("nan")
        return

    if result[0] == expected_point and result[1] == expected_point:
        test_state.state = "EXACT"
        test_state.abs_diff = 0.0
        test_state.rel_diff = 0.0
        return

    if strict_bounds and (expected_point < result[0]
                          or result[1] < expected_point):
        test_state.state = "BROKEN"
        test_state.abs_diff = float("nan")
        test_state.rel_diff = float("nan")
        return

    if args.min:
        result_point = result[0]
        comp = lambda a, b : a>b
    else:
        result_point = result[1]
        comp = lambda a, b : a<b

    abs_diff, rel_diff = float_diff(expected_point, result_point)
    test_state.abs_diff = abs_diff
    test_state.rel_diff = rel_diff

    if abs(abs_diff) < args.abs_tol or abs(rel_diff) < args.rel_tol:
        if comp(abs_diff, 0.0):
            test_state.state = "BAD_CLOSE"
            return
        else:
            test_state.state = "CLOSE"
            return
    else:
        if comp(abs_diff, 0.0):
            test_state.state = "BAD_FAR"
            return
        else:
            test_state.state = "FAR"
            return


def tally_result(tup):
    args = tup[0]
    test_state = tup[1]
    idx = 0 if args.min else 1

    if args.tsv:
        print("{}\t{}\t{}\t{}\t{}\t{}\t{}".format(test_state.test,
                                                  test_state.state,
                                                  test_state.expected[idx],
                                                  test_state.result[idx],
                                                  test_state.abs_diff,
                                                  test_state.rel_diff,
                                                  test_state.elapsed))
    elif args.v or test_state.state in {"CRASH", "TIMEOUT", "BROKEN", "FAILED"}:
        print(("Test:     {}\n"
               "State:    {}\n"
               "Expected: {}\n"
               "Result:   {}\n"
               "Abs_Diff: {}\n"
               "Rel_Diff: {}\n"
               "Time:     {}\n"
               "\n").format(test_state.test,
                            STATUS_FMT[test_state.state](test_state.state),
                            test_state.expected[idx],
                            test_state.result,
                            test_state.abs_diff,
                            test_state.rel_diff,
                            test_state.elapsed))

    STATUS_COUNT[test_state.state] += 1


def process_test(args, cmd, test, strict_bounds, expected):
    try:
        t0 = time.time()
        p = subprocess.Popen(" ".join(cmd), shell=True,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err  = p.communicate()
        out = out.decode('utf-8')
        err = err.decode('utf-8')
        retcode = p.returncode
        elapsed = time.time() - t0

        result = SUPPORT.get_result(out+"\n"+err)

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

        result = "CRASH"

    retval = Object()
    retval.test = test
    retval.expected = expected
    retval.result = result
    retval.elapsed = elapsed
    retval.state = None

    if result == "CRASH":
        retval.state = "CRASH"
        test_state.abs_diff = float("nan")
        test_state.rel_diff = float("nan")

    else:
        calculate_result(args, retval, strict_bounds)

    return args, retval


def get_expected(args, test):
    with open(test, 'r') as f:
        data = f.read()

    min_match = re.search(r'\#[ \t]*minimum:[ \t]*([^ \n]+)', data)
    max_match = re.search(r'\#[ \t]*maximum:[ \t]*([^ \n]+)', data)

    if min_match is None or min_match.group(1) == "?":
        test_min = None
    else:
        test_min = float(min_match.group(1))

    if max_match is None or max_match.group(1) == "?":
        test_max = None
    else:
        test_max = float(max_match.group(1))

    return (test_min, test_max)


def print_error(e):
    print("python exception:")
    print(e)


def do_parallel_tests(args, tests, my_pool, prefix, strict_bounds):
    was_interrupted = False
    results = list()

    try:
        for test in tests:
            expected = get_expected(args, test)
            if args.skip and expected is None:
                STATUS_COUNT["SKIPPED"] += 1
                continue
            cmd = [args.exe]
            cmd += [prefix + test]
            cmd += ["-t {}".format(args.timeout)]
            cmd += args.flags

            result = my_pool.apply_async(process_test,
                                      args=(args, cmd, test,
                                            strict_bounds, expected),
                                      callback=tally_result,
                                      error_callback=print_error)
            results.append(result)

        for result in results:
            result.wait()

    except KeyboardInterrupt:
        print("\nCaught KeyboardInterrupt, terminating workers\n")
        my_pool.terminate()
        my_pool.join()
        return True

    my_pool.close()
    my_pool.join()
    return False


def parse_args():
  num_cpus = multiprocessing.cpu_count() // 2

  parser = argparse.ArgumentParser()
  parser.add_argument("--exe",
                      help="What executable to run",
                      type=str,
                      default="gelpia")
  parser.add_argument("--flags",
                      help="Additional command line arguments for the tool under test",
                      default=[],
                      nargs="+")
  parser.add_argument("--procs",
                      help="Execute regressions using the selected number of procs in parallel",
                      type=int,
                      default=num_cpus,
                      action="store")
  parser.add_argument("--timeout",
                      help="Per test time limit in seconds, 0 for no timout",
                      type=int,
                      default=60)
  parser.add_argument("--min",
                      help="Tool used finds minimum",
                      action='store_const',
                      const=True,
                      default=False)
  parser.add_argument("--tsv",
                      help="Output in TSV format",
                      action='store_const',
                      const=True,
                      default=False)
  parser.add_argument("--skip",
                      help="Skip tests with unknown answers",
                      action='store_const',
                      const=True,
                      default=False)
  parser.add_argument("--abs-tol",
                       help="Absolute tolerance for 'CLOSE' results",
                       type=float,
                       default=1e-12)
  parser.add_argument("--rel-tol",
                       help="Relative tolerance for 'CLOSE' results",
                       type=float,
                       default=0.01)
  parser.add_argument("-v",
                      help="Print all test output",
                      action='store_const',
                      const=True,
                      default=False)
  parser.add_argument("benchmark_dir")

  args = parser.parse_args()

  return args


SUPPORT = None
def main():
    global SUPPORT

    args = parse_args()

    base = path.basename(args.exe)
    if base == "gelpia":
        strict_bounds = True
        file_extension = ".txt"
        prefix = "@"
        if args.min:
            args.flags += ["--dreal"]
        import gelpia_test_support as SUPPORT
    elif base == "dop_gelpia":
        strict_bounds = True
        file_extension = ".dop"
        prefix = ""
        if args.min:
            args.flags += ["--dreal"]
        import gelpia_test_support as SUPPORT
    elif base == "dOp_wrapper":
        strict_bounds = False
        file_extension = ".dop"
        prefix = ""
        args.min = True
    else:
        print(yellow("WARNING") + ": assuming gelpia compatable executable")
        strict_bounds = True
        file_extension = ".txt"
        prefix = "@"
        if maximize:
            args.flags += ["--dreal"]
        import gelpia_test_support as SUPPORT

    if args.v:
        print("Tester Configuration:")
        print("  exe:            '{}'".format(args.exe))
        print("  flags:          '{}'".format(" ".join(args.flags)))
        print("  file_extension: '{}'".format(file_extension))
        print("  prefix:         '{}'".format(prefix))
        print("  timeout:        {}".format(args.timeout))
        print("  goal:           {}".format("minimize" if args.min else "maximize"))
        print("  abs_tol:        {}".format(args.abs_tol))
        print("  rel_tol:        {}".format(args.rel_tol))
        print("  strict_bounds:  {}".format(strict_bounds))

    files = glob.glob(path.join(args.benchmark_dir, "**"), recursive=True)
    files.sort()
    tests = [f for f in files if f.endswith(file_extension)]
    total = len(tests)
    print("{} benchmarks to process".format(total))

    proc_count = min(total, args.procs)
    print("Creating Pool with '{}' Workers\n".format(proc_count), flush=True)
    my_pool = multiprocessing.pool.ThreadPool(processes=proc_count)

    if args.tsv:
        print("Test\tState\tExpected\tResult\tAbs Diff\tRel Diff\tTime")

    was_interrupted = do_parallel_tests(args, tests, my_pool, prefix, strict_bounds)

    statuses = STATUS_ORDER
    if args.skip:
        statuses.remove("UNKNOWN")
    else:
        statuses.remove("SKIPPED")

    if strict_bounds:
        statuses.remove("BAD_FAR")
        statuses.remove("BAD_CLOSE")
    else:
        statuses.remove("BROKEN")

    maxlabel = max([len(s) for s in statuses])
    fmtstr = "{{:{}}}".format(maxlabel)
    tests_ran = sum(STATUS_COUNT.values())
    print()
    for status in statuses:
        label = fmtstr.format(status)
        print("{} : {}".format(STATUS_FMT[status](label), STATUS_COUNT[status]))
    label = fmtstr.format("TOTAL")
    print("\n{} : {}".format(label, tests_ran))

    if not was_interrupted and tests_ran != total:
        print(red("\nERROR:") +
              "number of tests ran({}) does not equal total tests({}), "
              "there is a bug in {}".format(tests_ran, total, sys.argv[0]))
        return -1

    return 0

if __name__ == "__main__":
    sys.exit(main())
