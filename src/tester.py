#!/usr/bin/env python3


from color_printing import *
from execution import Execution
from test import Test

import argparse
import glob
import multiprocessing
import os.path as path
import sys




def write_regressionfile(args, tests):
    lines = list()
    lines.append("flags: {}".format(args.flags))
    lines.append("timeout: {}".format(args.timeout))
    lines.append("mode: {}".format("MIN" if args.min else "MAX"))
    lines.append("abs_tol: {}".format(args.abs_tol))
    lines.append("rel_tol: {}".format(args.rel_tol))
    lines.append("")
    lines.append(Test.regression_header())
    for t in tests:
        lines.append(t.regression_row())
    lines.append("")
    data = "\n".join(lines)
    with open(args.o, "w") as f:
        f.write(data)

def read_regressionfile(filename):
    with open(filename, "r") as f:
        lines = f.readlines()
    seen_header = False
    benchmarks = dict()
    for line in lines:
        line = line.strip()
        if line == "":
            continue
        if not seen_header:
            if line.startswith("flags: "):
                flags = line[7:]
                continue
            if line.startswith("timeout: "):
                timeout = int(line[9:])
                continue
            if line.startswith("mode: "):
                mode = line[6:]
                continue
            if line.startswith("abs_tol: "):
                abs_tol = float(line[8:])
                continue
            if line.startswith("rel_tol: "):
                rel_tol = float(line[8:])
                continue
            if line == Test.regression_header():
                seen_header = True
                continue
        parts = line.split("\t")
        benchmarks[parts[0]] = (float(parts[1]), float(parts[2]))
    return flags, timeout, mode, abs_tol, rel_tol, benchmarks

def run_test(t):
    try:
        t.run()
        print(t.tsv_row(), flush=True)
    except KeyboardInterrupt as e:
        raise e
    return t


def parse_args(argv):
  num_cpus = multiprocessing.cpu_count() // 2

  parser = argparse.ArgumentParser()
  parser.add_argument("--exe",
                      help="What executable to run",
                      type=str,
                      default="gelpia")
  parser.add_argument("--flags",
                      help="Additional command line arguments for the tool under test, should not contain time limit or optimization mode",
                      default="",
                      type=str,
                      nargs="?")
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
                      help="Find minimums instead of maximum",
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
  parser.add_argument("-r",
                      help="File containing existing regression information",
                      type=str)
  parser.add_argument("-o",
                      help="Output regression file to create a new baseline",
                      type=str)
  parser.add_argument("benchmark_dir")

  args = parser.parse_args(args=argv[1:])

  return args


def main(argv):
    args = parse_args(argv)

    tests = list()

    if args.r is not None:
        flags, timeout, mode, bound, rel_bound, benchmarks = read_regressionfile(args.r)

        for filename, regression_range in benchmarks.items():
            command = "{} --mode={} --timeout={} {} {}".format(args.exe,
                                                               mode.lower(),
                                                               timeout,
                                                               flags,
                                                               filename)
            execution = Execution(command)
            test = Test(execution, bound, rel_bound, timeout)
            test.set_regression(regression_range)
            tests.append(test)

    else:
        files = glob.glob(path.join(args.benchmark_dir, "**"), recursive=True)
        files = [f for f in files if f.endswith(".dop")]
        files.sort()
        for filename in files:
            command = "{} --mode={} --timeout={} {} {}".format(args.exe,
                                                               "min" if args.min else "max",
                                                               args.timeout,
                                                               args.flags,
                                                               filename)
            execution = Execution(command)
            test = Test(execution, args.abs_tol, args.rel_tol, args.timeout)
            tests.append(test)

    total = len(tests)
    print("{} benchmarks to process".format(total))

    proc_count = min(total, args.procs)
    print("Creating Pool with '{}' Workers\n".format(proc_count), flush=True)
    print(Test.tsv_header(args.r is not None))
    try:
        with multiprocessing.Pool(processes=proc_count) as pool:
            tests = pool.map(run_test, tests)
    except KeyboardInterrupt as e:
        raise e

    main_states = {k:0 for k in Test.MAIN_STATES}
    strict_states = {k:0 for k in Test.STRICT_STATES}
    width_states = {k:0 for k in Test.WIDTH_STATES}
    regression_states = {k:0 for k in Test.REGRESSION_STATES}

    for t in tests:
        main_states[t.main_state] += 1
        strict_states[t.strict_state] += 1
        width_states[t.width_state] += 1
        regression_states[t.regression_state] += 1

    print()

    print("MAIN_STATE")
    for k in Test.MAIN_STATES:
        fmt = Test.MAIN_STATES_FMT[k]
        print("{}: {}".format(fmt(k), main_states[k]))
    main_total = sum(v for v in main_states.values())
    print("TOTAL: {}\n".format(main_total))

    print("STRICT_STATE")
    for k in Test.STRICT_STATES:
        fmt = Test.STRICT_STATES_FMT[k]
        print("{}: {}".format(fmt(k), strict_states[k]))
    strict_total = sum(v for v in strict_states.values())
    print("TOTAL: {}\n".format(strict_total))

    print("WIDTH_STATE")
    for k in Test.WIDTH_STATES:
        fmt = Test.WIDTH_STATES_FMT[k]
        print("{}: {}".format(fmt(k), width_states[k]))
    width_total = sum(v for v in width_states.values())
    print("TOTAL: {}\n".format(width_total))

    if args.r:
        print("REGRESSION_STATE")
        for k in Test.REGRESSION_STATES:
            fmt = Test.REGRESSION_STATES_FMT[k]
            print("{}: {}".format(fmt(k), regression_states[k]))
        regression_total = sum(v for v in regression_states.values())
        print("TOTAL: {}\n".format(regression_total))

    if args.o:
        write_regressionfile(args, tests)

    return (main_states["CRASH"]
            + main_states["FAILED"]
            + strict_states["BROKEN"]
            + regression_states["FAR_WORSE"])

if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except KeyboardInterrupt:
        print("Caught ctrl-c, bye")
        sys.exit(0)
