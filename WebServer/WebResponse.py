import json
from WebServer.HTTPException import *

class WebResponse:
    def __init__(self):
        self._code = OK
        self._headers = {}
        self._body = None
        self.send = None
        self.isSent = False

    def code(self, code):
        """Do not call directly, raise HTTPException."""
        self._code = code

    def clear(self):
        self._headers.clear()
        self._body = None

    def header(self, key, value):
        self._headers[key] = value

    def body(self, body):
        """Appends to body. Ignored when HTTPException raised."""
        if self._body == None:
            self._body = body
        else:
            if isinstance(body, str):
                self._body += body
            else:
                raise ValueError("Attempted to append to non-string body")

    def body_should_stringify(self):
        return isinstance(self._body, dict) or isinstance(self._body, list) or isinstance(self._body, tuple)

    def body_stringify_json(self):
        self._body = json.dumps(self._body)

    def define_send(self, send):
        self.send = send

    async def send_internal(self, req, logger, writer, body_must_be_string=False):
        # Used to omit body checking
        # If true req can be None
        if not body_must_be_string:
            if self.body_should_stringify():
                accept = None

                try:
                    accept = req.get_header("accept")  # raises KeyError
                    accept = accept.split(",")
                    accept = [x.split(";")[0] for x in accept] # remove quality factor
                    if "application/json" in accept or "*/*" in accept:
                        self.header("content-type", "application/json")
                        self.body_stringify_json()  # saved internally
                    # TODO Add more formats
                    else:
                        raise ValueError("body is list/tuple/dict and content-type != application/json")

                except KeyError:
                    logger.warn("client did not sent Accept header.".format(req.method, req.path))
                    raise HTTPException(BAD_REQUEST, "Client did not sent Accept header (required for stringified data).")

                except ValueError:
                    logger.warn("client not accepting stringified data.".format(req.method, req.path))
                    raise HTTPException(BAD_REQUEST, "Client does not accept stringified data (accept={}).".format(accept))

            elif isinstance(self._body, str):
                # do nothing if body string
                pass

            elif self._body == None:
                logger.warn("body is None on {} {}.".format(req.method, req.path))
                raise HTTPException(INTERNAL_SERVER_ERROR, "Body is None on {} {}.".format(req.method, req.path))

            else:
                logger.warn("can't stringify data on {} {}.".format(req.method, req.path))
                raise HTTPException(INTERNAL_SERVER_ERROR, "Can't stringify data on {} {}.".format(req.method, req.path))

        logger.trace("body ready to be sent.")
        self.write(writer)
        await writer.drain()
        await writer.wait_closed()
        self.isSent = True

        logger.debug("response sent.")

    def write(self, writer):
        writer.write("HTTP/1.1 {} {}\r\n".format(self._code, code_reason_map[self._code]))
        for key in self._headers:
            writer.write("{}: {}\r\n".format(key, self._headers[key]))

        writer.write("\r\n")
        writer.write(self._body)
        writer.drain()
