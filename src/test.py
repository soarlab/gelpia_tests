

from color_printing import *

import math
import os.path as path
import re



def float_diff(expected, result):
    if (math.isinf(expected)
        and math.isinf(result)
        and math.copysign(1, expected) == math.copysign(1, result)):
        return 0.0, 0.0

    diff = result - expected
    if diff == 0.0:
        return 0.0, 0.0
    if expected == 0.0:
        if math.copysign(1.0, diff) == 1.0:
            return diff, float("inf")
        return diff, float("-inf")

    rel_diff = diff / abs(expected)
    return diff, rel_diff

def float_abs_diff(expected, result):
    diff, rel_diff = float_diff(expected, result)
    return abs(diff), abs(rel_diff)




class Test():
    MODES = {
        "MIN",
        "MAX",
    }

    MAIN_STATES = [
        "NOT_RAN",
        "CRASH",
        "FAILED",
        "TIMEOUT",
        "RAN_OUT",
        "RAN",
    ]

    MAIN_STATES_FMT = {
        "NOT_RAN" : lambda t : magenta(t),
        "CRASH"   : lambda t : red(t),
        "FAILED"  : lambda t : bold(red(t)),
        "TIMEOUT" : lambda t : cyan(t),
        "RAN_OUT" : lambda t : yellow(t),
        "RAN"     : lambda t : green(t),
    }

    STRICT_STATES = [
        "NOT_APPLICABLE",
        "BROKEN",
        "FAR",
        "CLOSE",
        "EXACT",
    ]

    STRICT_STATES_FMT = {
        "NOT_APPLICABLE" : lambda t : magenta(t),
        "BROKEN"         : lambda t : bold(red(t)),
        "FAR"            : lambda t : yellow(t),
        "CLOSE"          : lambda t : green(t),
        "EXACT"          : lambda t : bold(green(t)),
    }

    WIDTH_STATES = [
        "NOT_APPLICABLE",
        "WIDE",
        "NARROW",
        "POINT",
    ]

    WIDTH_STATES_FMT = {
        "NOT_APPLICABLE" : lambda t : magenta(t),
        "WIDE"           : lambda t : yellow(t),
        "NARROW"         : lambda t : green(t),
        "POINT"          : lambda t : bold(green(t)),
    }

    REGRESSION_STATES = [
        "NOT_APPLICABLE",
        "FAR_WORSE",
        "WORSE",
        "SAME",
        "BETTER",
        "FAR_BETTER",
    ]

    REGRESSION_STATES_FMT = {
        "NOT_APPLICABLE" : lambda t : magenta(t),
        "FAR_WORSE"      : lambda t : bold(red(t)),
        "WORSE"          : lambda t : yellow(t),
        "SAME"           : lambda t : green(t),
        "BETTER"         : lambda t : green(t),
        "FAR_BETTER"     : lambda t : bold(green(t)),
    }

    def __init__(self, execution, bound, rel_bound, timeout):
        self.execution = execution
        self.bound = bound
        self.rel_bound = rel_bound
        self.timeout = timeout

        self.mode = "MAX"
        for part in execution.command.split():
            if part.endswith(".dop"):
                self.path = part
                self.name = path.split(part)[-1]
                continue
            if part == "--mode=min":
                self.mode = "MIN"
                continue

        self.expected = self.extract_expected()

        self.regression_range = None
        self.answer_range = None
        self.main_state = "NOT_RAN"
        self.strict_state = "NOT_APPLICABLE"
        self.width_state = "NOT_APPLICABLE"
        self.regression_state = "NOT_APPLICABLE"

    def extract_expected(self):
        with open(self.path, 'r') as f:
            data = f.read()

        min_match = re.search(r'\#[ \t]*minimum:[ \t]*([^ \n]+)', data)
        max_match = re.search(r'\#[ \t]*maximum:[ \t]*([^ \n]+)', data)

        expected_min = float(min_match.group(1))
        expected_max = float(max_match.group(1))

        if self.mode == "MIN":
            return expected_min
        return expected_max

    def set_regression(self, regression_range):
        self.regression_range = regression_range

    def run(self):
        self.execution.run()
        self.answer_range = self.parse_answer()
        self.main_state = self.calculate_main_state()
        self.strict_state = self.calculate_strict_state()
        self.width_state = self.calculate_width_state()
        self.regression_state = self.calculate_regression_state()

    def parse_answer(self):
        max_upper = None
        max_lower = None
        min_upper = None
        min_lower = None

        output = self.execution.stdout
        max_upper_match = re.search(r"Maximum upper bound (.*)", output)
        max_lower_match = re.search(r"Maximum lower bound (.*)", output)
        min_upper_match = re.search(r"Minimum upper bound (.*)", output)
        min_lower_match = re.search(r"Minimum lower bound (.*)", output)

        if max_upper_match is not None:
            max_upper = float(max_upper_match.group(1))
        if max_lower_match is not None:
            max_lower = float(max_lower_match.group(1))
        if min_upper_match is not None:
            min_upper = float(min_upper_match.group(1))
        if min_lower_match is not None:
            min_lower = float(min_lower_match.group(1))

        if self.mode == "MIN":
            return (min_lower, min_upper)
        else:
            return (max_lower, max_upper)

    def calculate_main_state(self):
        if self.execution.retcode != 0:
            return "CRASH"
        if (self.execution.elapsed > self.timeout and
            self.answer_range == (None, None)):
            return "TIMEOUT"
        if (self.execution.elapsed > self.timeout and
            self.answer_range != (None, None)):
            return "RAN_OUT"
        if self.answer_range == (None, None):
            return "FAILED"
        return "RAN"

    def calculate_strict_state(self):
        if self.main_state not in {"RAN", "RAN_OUT"}:
            return "NOT_APPLICABLE"
        comp = (lambda a,b: a<b) if self.mode == "MIN" else (lambda a,b: a>b)
        outer = self.answer_range[0] if self.mode == "MIN" else self.answer_range[1]
        if comp(self.expected, outer):
            return "BROKEN"
        abs_diff, rel_abs_diff = float_abs_diff(outer, self.expected)
        if abs_diff == 0.0:
            return "EXACT"
        if abs_diff < self.bound or rel_abs_diff < self.rel_bound:
            return "CLOSE"
        return "FAR"

    def calculate_width_state(self):
        if self.main_state not in {"RAN", "RAN_OUT"}:
            return "NOT_APPLICABLE"
        abs_diff, rel_abs_diff = float_abs_diff(*self.answer_range)
        if abs_diff == 0.0:
            return "POINT"
        if abs_diff < self.bound or rel_abs_diff < self.rel_bound:
            return "NARROW"
        return "WIDE"

    def calculate_regression_state(self):
        if (self.main_state not in {"RAN", "RAN_OUT"}
            or self.regression_range is None):
            return "NOT_APPLICABLE"
        comp = (lambda a,b: a<b) if self.mode == "MIN" else (lambda a,b: a>b)
        outer = self.answer_range[0] if self.mode == "MIN" else self.answer_range[1]
        old_outer = self.regression_range[0] if self.mode == "MIN" else self.regression_range[1]
        abs_diff, rel_abs_diff = float_abs_diff(outer, old_outer)
        if abs_diff == 0.0:
            return "SAME"
        if comp(old_outer, outer):
            if abs_diff < self.bound or rel_abs_diff < self.rel_bound:
                return "BETTER"
            return "FAR_BETTER"
        else:
            if abs_diff < self.bound or rel_abs_diff < self.rel_bound:
                return "WORSE"
            return "FAR_WORSE"

    @staticmethod
    def tsv_header(do_regression):
        header = ["Benchmark",
                  "Expected",
                  "AnswerLow",
                  "AnswerHigh",
                  "Elapsed",
                  "MainState",
                  "StrictState",
                  "WidthState"]
        if do_regression:
            header.append("RegressionState")
        return "\t".join(header)

    def tsv_row(self):
        row = [str(t) for t in [
            self.name,
            self.expected,
            self.answer_range[0],
            self.answer_range[1],
            self.execution.elapsed,
            self.main_state,
            self.strict_state,
            self.width_state]]
        if self.regression_range is not None:
            row.append(self.regression_state)
        return "\t".join(row)

    @staticmethod
    def regression_header():
        return "\t".join(["File",
                          "AnswerLow",
                          "AnswerHigh",
                          "Elapsed"])

    def regression_row(self):
        return "\t".join([str(t) for t in [
            self.path,
            self.answer_range[0],
            self.answer_range[1],
            self.execution.elapsed,]])
