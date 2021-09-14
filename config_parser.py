import os

# Throws
def read_dict(path):
    out = {}
    f = open(path, "r")
    for line in f:
        key, val = line.strip().split("=")
        out[key] = val

    f.close()
    return out

def save_dict(path, dict):
    f = open(path, "w")
    for key in dict:
        val = str(dict[key])
        f.write(key+"="+val+"\n")

    f.close()