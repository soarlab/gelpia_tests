#!/usr/bin/env python3

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

STATUS_FMT = {"UNKNOWN"   : lambda t : yellow(t),
              "CORRECT"   : lambda t : green(t),
              "INCORRECT" : lambda t : red(bold(t)),
              "SKIPPED"   : lambda t : bold(t),}

STATUS_COUNT = {"UNKNOWN"   : 0,
                "CORRECT"   : 0,
                "INCORRECT" : 0,
                "SKIPPED"   : 0,}

def mass_replace(string, replacement):
    for old,new in replacement:
        string = string.replace(old, new)
    return string

def compare_result(expected, result):
    replacement = [("['ConstantInterval', ['Float', '3.141592653589793115997963468544185161590576171875'], ['Float', '3.141592653589793560087173318606801331043243408203125']]", "[pi]"),
                   (" ", ""),
                   ("\"", ""),
                   ("Integer",""),
                   ("Input",""),
                   ("'",""),
                   (",",""),
                   ("neg", "-"),
                   ("[","("),
                   ("]",")"),
                   ("powi","pow")]
    expected = "".join(expected)
    result = "".join(result)
    e = mass_replace(expected, replacement)
    r = mass_replace(result, replacement)
    if e == "":
        return "UNKNOWN"
    e_list = sorted([line for line in e.splitlines() if line!=""])
    r_list = sorted([line for line in r.splitlines() if line!=""])
    if e_list == r_list:
        return "CORRECT"
    else:
        return "INCORRECT"

def get_expected(filename):
    with open(filename, 'r') as f:
        data = f.read()

    ansmatch = re.findall(r'\#[ \t]*answer:[ \y]*([^\n]+)', data)

    if ansmatch:
        return [a+"\n" for a in ansmatch]
    else:
        return ""



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
  result = (out+err).splitlines(True)
  state = compare_result(expected, result)

  printstate = STATUS_FMT[state](state)
  expected = ['unknown'] if expected=="" else expected

  str_result = "{}\n".format(cmd)
  str_result += "State:\n  {}\n".format(printstate)
  str_result += "Expected:\n  {}\n".format("  ".join(expected))
  str_result += "Result:\n  {}\n".format("  ".join(result))
  str_result += "Time:\n  {}\n\n".format(elapsed)

  return str_result, state

def tally_result(tup):
  """
  Tallies the result of each worker. This will only be called by the main thread.
  """
  str_result, state = tup
  print(str_result, flush=True)
  STATUS_COUNT[state] += 1


def main():
  """
  Main entry point for the test suite.
  """
  t0 = time.time()
  num_cpus = multiprocessing.cpu_count()

  # configure the CLI
  parser = argparse.ArgumentParser()
  parser.add_argument("--threads", action="store", dest="n_threads", default=num_cpus, type=int,
                      help="execute regressions using the selected number of threads in parallel")
  parser.add_argument("--rd", type=str, help="Reverse diff pass script", default="gelpia")
  parser.add_argument("--skip", action='store_const', help="Skip tests with unknown answers", const=True, default=False)
  parser.add_argument("benchmark_dir")
  args = parser.parse_args()

  if args.rd == "gelpia":
      print("this will be fixed")
      assert(0)

  exe = args.rd
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

    n_threads = min(total+1, args.n_threads)
    print("Creating Pool with '{}' Workers\n".format(n_threads), flush=True)
    p = multiprocessing.pool.ThreadPool(processes=n_threads)

    for test in tests:
      # build up the subprocess command
      cmd = ["python3", exe, test, "test"]
      expected = get_expected(test)
      if args.skip and expected=="":
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
