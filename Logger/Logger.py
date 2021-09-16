import Logger.colors as c

ERROR = 1
WARN = 2
INFO = 3
DEBUG = 4
TRACE = 5

class Logger:
    def __init__(self, tag, loglevel=INFO):
        self.tag = tag
        self.loglevel = loglevel

    @staticmethod
    def write(msg):
        # for now standard print to stdout
        print(msg)

    def _write_level(self, msg, char, color=c.WHITE, bright=False):
        out = c.getCode(color, bright=bright)
        out += "[{} {}] ".format(char, self.tag)
        out += msg+c.reset()
        self.write(out)

    def error(self, msg):
        if self.loglevel >= ERROR:
            self._write_level(msg, "E", color=c.RED)

    def warn(self, msg):
        if self.loglevel >= WARN:
            self._write_level(msg, "W", color=c.YELLOW)

    def info(self, msg):
        if self.loglevel >= INFO:
            self._write_level(msg, "I", color=c.GREEN)

    def debug(self, msg):
        if self.loglevel >= DEBUG:
            self._write_level(msg, "D")

    def trace(self, msg):
        if self.loglevel >= TRACE:
            self._write_level(msg, "T", color=c.BLACK, bright=True)