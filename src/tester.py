#!/usr/bin/env python3

from math import isnan, isinf

import argparse
import glob
import multiprocessing
import os.path as path
import multiprocessing.pool as pool
import re
import subprocess
import sys
import time


STATUS_FMT = {"FAILED"    : lambda t : red(bold(t)),
              "TIMEOUT"   : lambda t : cyan(t),
              "UNKNOWN"   : lambda t : yellow(t),
              "CLOSE"     : lambda t : green(bold(t)),
              "FAR"       : lambda t : green(t),
              "BAD CLOSE" : lambda t : magenta(t),
              "BAD FAR"   : lambda t : magenta(bold(t)),}

STATUS_COUNT = {"FAILED"    : 0,
                "TIMEOUT"   : 0,
                "UNKNOWN"   : 0,
                "CLOSE"     : 0,
                "FAR"       : 0,
                "BAD CLOSE" : 0,
                "BAD FAR"   : 0,}


if sys.stdout.isatty():
  do_fmt = True
else:
  do_fmt = False

def fmt(tag, text):
  if do_fmt:
    return tag+text+'\033[0m'
  else:
    return text

  
def bold(text):
  return fmt('\033[1m', text)


def color(color_code, text):
  return fmt('\033[0;3{}m'.format(color_code), text)
             

def red(text):
  return color(1, text)

def green(text):
  return color(2, text)

def yellow(text):
  return color(3, text)

def blue(text):
  return color(4, text)

def magenta(text):
  return color(5, text)

def cyan(text):
  return color(6, text)

  
def get_result(output):
  match = re.search(r'\[([^,]+), \{', output)
  if match:
    return float(match.group(1))
  else:
    return float('nan')

  
def get_expected(filename):
  with open(filename, 'r') as f:
    match = re.search(r'\#[ \t]*answer:[ \y]*([^ \n]+)', f.read())
    if match:
      return float(match.group(1))
    else:
      return float('nan')


def are_close(expected, result):
  if abs(expected - result) < 1.2*expected:
    return True

  return isinf(expected) and isinf(result)


def are_rigerous(expected, result):
  if isinf(expected) and isinf(result):
    return True

  return expected <= result


def compare_result(expected, result, timeoutp):
  if isnan(result):
    if timeoutp:
      return "TIMEOUT"
    else:
      return "FAILED"

  if isnan(expected):
    return "UNKNOWN"
  
  res = "CLOSE" if are_close(expected, result) else "FAR"
  if not are_rigerous(expected, result):
    res = "BAD "+res
  return res


def process_test(cmd, test, expected):
  cmd = " ".join(cmd)
  str_result = "{}\n".format(cmd)

  t0 = time.time()
  p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  out, err  = p.communicate()
  out = out.decode('utf-8')
  err = err.decode('utf-8')
  elapsed = time.time() - t0

  # get the test results
  result = get_result(out+err)
  state = compare_result(expected, result, elapsed>=TIMEOUT)
  str_result += "State: {}\n".format(STATUS_FMT[state](state))

  str_result += "Answer: {} \n".format('no answer found' if isnan(result) else result)
  str_result += "Expected: {}\n".format('unknown' if isnan(expected) else expected)
  str_result += "Time: {}\n\n".format(elapsed)

  return str_result, state


def tally_result(tup):
  """
  Tallies the result of each worker. This will only be called by the main thread.
  """
  str_result, state = tup
  print(str_result)
  STATUS_COUNT[state] += 1


def main():
  """
  Main entry point for the test suite.
  """
  global TIMEOUT
  t0 = time.time()
  num_cpus = multiprocessing.cpu_count()//2

  # configure the CLI
  parser = argparse.ArgumentParser()
  parser.add_argument("--threads", action="store", dest="n_threads", default=num_cpus, type=int,
                      help="execute regressions using the selected number of threads in parallel")
  parser.add_argument("--exe", type=str, help="What executable to run", default="gelpia")
  parser.add_argument("--timeout", type=int, help="How long each executable has, 0 for no timout", default=60)
  parser.add_argument("--dreal", action='store_const', const=True, default=False)
  parser.add_argument("benchmark_dir")
  args = parser.parse_args()

  TIMEOUT = args.timeout
  
  # change mode
  if args.dreal:
    flags = ["--dreal"]
  else:
    flags = []

  exe = args.exe
  base = path.basename(args.exe)
  if base == "gelpia":
    exten = ".txt"
    pref = "@"
  elif base == "dop_gelpia":
    exten = ".dop"
    pref = ""
  else:
    print(yellow("WARNING") + ": assuming gelpia compatable executable")
    exten = ".txt"
    pref = "@"
  
  try:
    # start the tests
    print("Running benchmarks...")

    # start processing the tests.
    results = []
    tests = sorted(glob.glob(path.join(args.benchmark_dir,"*"+exten)))
    total = len(tests)
    print("{} benchmarks to process".format(total))
    
    n_threads = min(total, args.n_threads)
    print("Creating Pool with '{}' Workers\n".format(n_threads))
    p = multiprocessing.pool.ThreadPool(processes=n_threads)

    for test in tests:
      # build up the subprocess command
      cmd = [exe,
             pref+test,
             "-t {}".format(args.timeout)] + flags
      expected = get_expected(test)

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
    print("Caught KeyboardInterrupt, terminating workers")
    p.terminate() # terminate any remaining workers
    p.join()
  else:
    print("Quitting normally")
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
  for status in statuses:
    label = fmtstr.format(status)
    print("{} : {}".format(STATUS_FMT[status](label), STATUS_COUNT[status]))

  if (total != sum(STATUS_COUNT.values())):
    print(red("\nERROR:")+"number of tests does not equal total, there is a bug in {}".format(sys.argv[0]))


if __name__=="__main__":
  main()

