import re

def get_result(output):
    match = re.findall(r'min_\d+ += +\[([^,]+), +[^\]]+\]', output)
    if match != []:
        res = sum([float(m) for m in match])
        return res, res
    else:
        print(output)
        return None, None
