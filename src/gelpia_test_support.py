

import re




def get_result(output):
    max_l_match = re.search(r"Maximum lower bound (.*)", output)

    if max_l_match is not None:
        max_u_match = re.search(r"Maximum upper bound (.*)", output)
        l = max_l_match.group(1)
        u = max_u_match.group(1)
        return float(l), float(u)

    min_l_match = re.search(r"Minimum lower bound (.*)", output)
    if min_l_match is not None:
        min_u_match = re.search(r"Minimum upper bound (.*)", output)
        l = min_l_match.group(1)
        u = min_u_match.group(1)
        return float(l), float(u)

    print("Unable to parse: {}".format(output))
    return None, None

