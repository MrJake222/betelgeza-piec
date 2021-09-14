BLACK = "30"
RED = "31"
GREEN = "32"
YELLOW = "33"
BLUE = "34"
MAGENTA = "35"
CYAN = "36"
WHITE = "37"

colors = [BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE]

def getCode(color, bright=False):
    code = "\u001b[" + color
    if bright: code += ";1"
    code += "m"

    return code

def reset():
    return "\u001b[0m"