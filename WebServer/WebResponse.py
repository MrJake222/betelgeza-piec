from WebServer.HTTPException import HTTPException, OK, BAD_REQUEST, INTERNAL_SERVER_ERROR, code_reason_map

_FILE_BUF = bytearray(64)

async def json_dump_stream(obj, write):
    if obj is None:
        await write("null")

    elif isinstance(obj, str):
        await write('"')
        await write(obj)
        await write('"')

    elif isinstance(obj, bool):
        if obj:
            await write('true')
        else:
            await write('false')

    elif isinstance(obj, int) or isinstance(obj, float):
        await write(str(obj))

    elif isinstance(obj, bytes):
        # treating bytes as ascii string
        await write('"')
        for x in obj: await write(chr(x))
        await write('"')

    elif isinstance(obj, dict):
        await write('{')
        for i, key in enumerate(obj):
            await write('"')
            await write(key)
            await write('":')
            await json_dump_stream(obj[key], write)
            if i < len(obj)-1: await write(',')
        await write('}')

    elif isinstance(obj, list) or isinstance(obj, tuple):
        await write('[')
        for i, entry in enumerate(obj):
            await json_dump_stream(entry, write)
            if i < len(obj)-1: await write(',')
        await write(']')

    else:
        raise ValueError("unsupported value {}".format(type(obj)))

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

    def define_send(self, send):
        self.send = send

    async def send_internal(self, req, logger, writer):
        # req is None when exception happens before request is fully received
        if req != None and self.body_should_stringify():
            try:
                accept = req.get_header("accept")  # raises KeyError
            except KeyError:
                raise HTTPException(BAD_REQUEST, "Client did not sent Accept header (required for stringified data).")

            accept = accept.split(",")
            accept = [x.split(";")[0] for x in accept] # remove quality factor
            if "application/json" in accept or "*/*" in accept:
                self.header("content-type", "application/json")
                await self.write_headers(writer)

                # used in json_dump_stream
                async def stream_write(s):
                    writer.write(s)
                    await writer.drain()

                try:
                    await json_dump_stream(self._body, stream_write)
                except ValueError as e:
                    raise HTTPException(INTERNAL_SERVER_ERROR, "JSON stringify error: {}.".format(e))

                logger.trace("body sent as json.")

            else:
                raise HTTPException(BAD_REQUEST, "Client does not accept stringified data (accept={}).".format(accept))

        elif isinstance(self._body, str):
            await self.write_headers(writer)
            writer.write(self._body)
            await writer.drain()
            logger.trace("body sent as string.")

        elif self._body == None:
            raise HTTPException(INTERNAL_SERVER_ERROR, "Body is None on {} {}.".format(req.method, req.path))

        else:
            raise HTTPException(INTERNAL_SERVER_ERROR, "Can't stringify body(type={}) on {} {}.".format(type(self._body), req.method, req.path))

        await writer.wait_closed()
        self.isSent = True

    async def write_headers(self, writer):
        writer.write("HTTP/1.1 {} {}\r\n".format(self._code, code_reason_map[self._code]))
        for key in self._headers:
            writer.write("{}: {}\r\n".format(key, self._headers[key]))

        writer.write("\r\n")
        await writer.drain()

    async def send_file(self, file, writer):
        f = open(file, "rb")

        ext_map = {
            "txt": "text/plain",
            "html": "text/html",
            "css": "text/css"
        }

        ext_pos = file.rfind(".") + 1
        ext = file[ext_pos:]
        try:
            self.header("content-type", ext_map[ext])
        except KeyError:
            raise HTTPException(INTERNAL_SERVER_ERROR, "Unsupported file extension type.")

        await self.write_headers(writer)

        mv = memoryview(_FILE_BUF)
        while True:
            read = f.readinto(_FILE_BUF)
            if read == 0:
                break

            writer.write(mv[:read])
            await writer.drain()

        await writer.wait_closed()
        self.isSent = True

        f.close()