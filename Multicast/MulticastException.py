BAD_REQUEST = 1

class MulticastException(Exception):
    def __init__(self, code, msg):
        self.code = code
        self.msg = msg