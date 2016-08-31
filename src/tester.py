#!/usr/bin/env python3

from math import isnan, isinf

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

STATUS_FMT = {"FAILED"    : lambda t : red(bold(t)),
              "TIMEOUT"   : lambda t : cyan(t),
              "UNKNOWN"   : lambda t : yellow(t),
              "CLOSE"     : lambda t : green(t),
              "EXACT"     : lambda t : green(t),
              "FAR"       : lambda t : green(bold(t)),
              "BAD_CLOSE" : lambda t : magenta(t),
              "BAD_FAR"   : lambda t : magenta(bold(t)),
              "SKIPPED"   : lambda t : bold(t),}

STATUS_COUNT = {"FAILED"    : 0,
                "TIMEOUT"   : 0,
                "UNKNOWN"   : 0,
                "CLOSE"     : 0,
                "EXACT"     : 0,
                "FAR"       : 0,
                "BAD_CLOSE" : 0,
                "BAD_FAR"   : 0,
                "SKIPPED"   : 0,}




def compare_result(expected, result, timeoutp):
  if isnan(result):
    if timeoutp:
      return "TIMEOUT"
    else:
      return "FAILED"

  if isnan(expected):
    return "UNKNOWN"

  if expected == result:
    return "EXACT"

  res = "CLOSE" if are_close(expected, result) else "FAR"
  if not are_rigerous(expected, result):
    res = "BAD_"+res
  return res


def get_expected(filename):
  with open(filename, 'r') as f:
    data = f.read()

  ansmatch = re.search(r'\#[ \t]*answer:[ \y]*([^ \n]+)', data)
  maxmatch = re.search(r'\#[ \t]*maximum:[ \y]*([^ \n]+)', data)
  minmatch = re.search(r'\#[ \t]*minimum:[ \y]*([^ \n]+)', data)

  try:
    if DREAL:
      if minmatch:
        return float(minmatch.group(1) if minmatch.group(1)!="?" else 'nan')
      else:
        return float('nan')

    else:
      if ansmatch:
        return float(ansmatch.group(1) if ansmatch.group(1)!="?" else 'nan')
      elif maxmatch:
        return float(maxmatch.group(1) if maxmatch.group(1)!="?" else 'nan')
      else:
        return float('nan')
  except:
    return float('nan')



def to_ulps(x):
  n = struct.unpack('<q', struct.pack('<d', x))[0]
  return -(n + 2**63) if n < 0 else n


def ulps_between(x, y):
  if isnan(x) or isnan(y):
    return float('nan')
  return abs(to_ulps(x) - to_ulps(y))


def are_close(expected, result):
  if isinf(expected) and isinf(result):
    return True
  abs_diff = abs(expected-result)
  if expected == 0.0:
    return abs_diff < 0.00001
  return abs_diff < 0.00001 or abs_diff/abs(expected) < 0.01



def are_rigerous(expected, result):
  if isinf(expected) and isinf(result):
    return True

  if DREAL:
    return expected >= result
  else:
    return expected <= result


def process_test(cmd, test, expected):
  all_dirs, basename = path.split(test)
  unused, last_dir = path.split(all_dirs)
  testname = path.join(last_dir, basename)
  cmd = " ".join(cmd)


  t0 = time.time()
  p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  out, err  = p.communicate()
  out = out.decode('utf-8')
  err = err.decode('utf-8')
  elapsed = time.time() - t0

  # get the test results
  result = support.get_result(out+err, DREAL)
  state = compare_result(expected, result, elapsed>=TIMEOUT)

  printstate = STATUS_FMT[state](state)
  ulps = ulps_between(expected, result)
  ulps = "unknown" if isnan(ulps) else ulps
  abs_diff = abs(result-expected)
  abs_diff = "unknown" if isnan(abs_diff) else abs_diff
  if isinf(result) and isinf(expected):
    abs_diff = 0
  expected = 'unknown' if isnan(expected) else expected
  result = 'no_answer_found' if isnan(result) else result

  if elapsed >= TIMEOUT:
    elapsed = yellow(str(elapsed))

  if CSV:
    str_result = "{}, {}, {}, {}, {}, {}, {}".format(testname,
                                                     state,
                                                     expected,
                                                     result,
                                                     abs_diff,
                                                     ulps,
                                                     elapsed)

  else:
    str_result = "{}\n".format(cmd)
    str_result += "Full stdout:\n  {}\n".format(out.strip().replace("\n", "\n  "))
    if err.strip() != "":
      str_result += "Full stderr:\n  {}\n".format(err.strip().replace("\n", "\n  "))
    str_result += "State:     {}\n".format(printstate)
    str_result += "Expected:  {}\n".format(expected)
    str_result += "Result:    {}\n".format(result)
    str_result += "Abs Diff:  {}\n".format(abs_diff)
    str_result += "ULPs Diff: {}\n".format(ulps)
    str_result += "Time:      {}\n\n\n\n".format(elapsed)

  return str_result, state


def tally_result(tup):
  """
  Tallies the result of each worker. This will only be called by the main thread.
  """
  str_result, state = tup
  print(str_result, flush=True)
  STATUS_COUNT[state] += 1

support = None
def main():
  """
  Main entry point for the test suite.
  """
  global TIMEOUT, support, CSV, DREAL
  t0 = time.time()
  num_cpus = multiprocessing.cpu_count()//2

  # configure the CLI
  parser = argparse.ArgumentParser()
  parser.add_argument("--flags", nargs="+", help="Additional command line arguments for the tool under test", default=[])
  parser.add_argument("--threads", action="store", dest="n_threads", default=num_cpus, type=int,
                      help="execute regressions using the selected number of threads in parallel")
  parser.add_argument("--exe", type=str, help="What executable to run", default="gelpia")
  parser.add_argument("--timeout", type=int, help="How long each executable has, 0 for no timout", default=60)
  parser.add_argument("--dreal", action='store_const', const=True, default=False)
  parser.add_argument("--csv", action='store_const', const=True, default=False)
  parser.add_argument("--skip", action='store_const', help="Skip tests with unknown answers", const=True, default=False)
  parser.add_argument("benchmark_dir")
  args = parser.parse_args()

  TIMEOUT = args.timeout
  CSV = args.csv
  DREAL = args.dreal
  flags = args.flags

  # change mode
  if args.dreal:
    flags += ["--dreal"]
  else:
    flags += []

  exe = args.exe
  base = path.basename(args.exe)
  if base == "gelpia":
    exten = ".txt"
    pref = "@"
    import gelpia_test_support as support
  elif base == "dop_gelpia":
    exten = ".dop"
    pref = ""
    import gelpia_test_support as support
  elif base == "dOp_wrapper":
    exten = ".dop"
    pref = ""
    flags = []
    import dop_test_support as support
  else:
    print(yellow("WARNING") + ": assuming gelpia compatable executable")
    exten = ".txt"
    pref = "@"
    import gelpia_test_support as support

  try:
    # start the tests
    print("Running benchmarks...")

    # start processing the tests.
    results = []
    tests = sorted(glob.glob(path.join(args.benchmark_dir,"**"),
                             recursive=True))
    tests = [f for f in tests if f.endswith(exten)]
    total = len(tests)
    print("{} benchmarks to process".format(total))

    n_threads = min(total+1, args.n_threads)
    print("Creating Pool with '{}' Workers\n".format(n_threads), flush=True)
    p = multiprocessing.pool.ThreadPool(processes=n_threads)

    if CSV:
      print("File, Status, Expected, Result, Absolute_Difference, ULPs_Difference, Time")

    for test in tests:
      # build up the subprocess command
      cmd = [exe,
             pref+test,
             "-t {}".format(args.timeout)] + flags
      expected = get_expected(test)
      if args.skip and isnan(expected):
        STATUS_COUNT["SKIPPED"] += 1
        continue

      if False:#"bad hack ian should remove":
        tally_result(process_test(cmd[:], test, expected))
      else:
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
  print(' ELAPSED TIME [{}]'.format(round(elapsed_time, 2)))

  # log the test results
  statuses = sorted(STATUS_COUNT.keys())
  maxlabel = max([len(s) for s in statuses])
  fmtstr = "{{:{}}}".format(maxlabel)
  tests_ran = sum(STATUS_COUNT.values())
  for status in statuses:
    label = fmtstr.format(status)
    print("{} : {}".format(STATUS_FMT[status](label), STATUS_COUNT[status]))
  label = fmtstr.format("TOTAL")
  print("{} : {}".format(label, tests_ran))

  if (total != sum(STATUS_COUNT.values())):
    print(red("\nERROR:")+"number of tests ran({}) does not equal total tests({}), there is a bug in {}".format(tests_ran, total, sys.argv[0]))


if __name__=="__main__":
  main()
