

import re




def get_result(output):
    try:
        match = re.search(r"Maximum is in \[([^,]*), ([^\]]*)\]", output)
        l = float(match.group(1))
        h = float(match.group(2))
        return l, h
    except:
        pass

    try:
        match = re.search(r"Minimum is in \[([^,]*), ([^\]]*)\]", output)
        l = float(match.group(1))
        h = float(match.group(2))
        return l, h
    except:
        pass

    print("BAD: {}".format(output))
    return None, None

