OK = 200
BAD_REQUEST = 400
NOT_FOUND = 404
METHOD_NOT_ALLOWED = 405
INTERNAL_SERVER_ERROR = 500
NOT_IMPLEMENTED = 501

code_reason_map = {
    OK: "OK",
    BAD_REQUEST: "Bad Request",
    NOT_FOUND: "Not Found",
    METHOD_NOT_ALLOWED: "Method Not Allowed",
    INTERNAL_SERVER_ERROR: "Internal Server Error",
    NOT_IMPLEMENTED: "Not Implemented"
}

class HTTPException(Exception):
    def __init__(self, code, msg):
        self.code = code
        self.msg = msg