import Logger.Logger as Logger
import uasyncio as asyncio
from WebServer.HTTPException import *
from WebServer.WebRequest import WebRequest
from WebServer.WebResponse import WebResponse

SUPPORTED_METHODS = ("GET", "POST")
HEADER_CONTENT_HTML = {"content-type": "text/html"}
HEADER_CONTENT_JSON = {"content-type": "application/json"}

class WebServer:
    def __init__(self, loglevel=Logger.INFO):
        self.logger = Logger.Logger("websrv", loglevel=loglevel)
        self.srv = None
        self.routes = {}

    async def start(self, addr="0.0.0.0", port=80, backlog=5):

        self.srv = await asyncio.start_server(self.handle_client, addr, port, backlog=backlog)
        self.logger.info("web server started.")

    async def stop(self):

        self.srv.close()
        await self.srv.wait_closed()
        self.logger.info("web server stopped.")

    async def handle_client(self, reader, writer):

        in_addr, in_port = reader.get_extra_info("peername")
        self.logger.debug("connection from {}:{}.".format(in_addr, in_port))
        resp = WebResponse()

        readAll = False
        connection_closed = False

        try:
            first_line = await reader.readline()

            try:
                method, url, _ = first_line.decode().split(" ")
            except ValueError:
                # Not enough values to unpack
                # malformed first_line
                self.logger.warn("first_line=\"{}\" malformed, bad request.".format(first_line))
                if first_line == b"": readAll = True
                raise HTTPException(BAD_REQUEST, "First line of the request was malformed.")

            req = WebRequest(method)

            try:
                req.parse_url(url)
            except ValueError as e:
                # Not enough values to unpack
                # Or too long splitted URL
                # malformed url
                self.logger.warn("url=\"{}\" malformed, {}, bad request.".format(url, e))
                raise HTTPException(BAD_REQUEST, "URL \"{}\" is malformed, reason: {}".format(url, e))

            self.logger.info("-> {} {}".format(req.method, req.path))

            while True:
                # Read and parse headers
                line = await reader.readline()
                if line == b"\r\n": break
                self.logger.trace("header: {}".format(line))

                try:
                    key, value = line.decode().strip().split(": ")
                except ValueError:
                    # Not enough values to unpack
                    # malformed header
                    self.logger.warn("header=\"{}\" malformed, bad request.".format(line))
                    raise HTTPException(BAD_REQUEST, "Header \"{}\" of the request was malformed.".format(line))

                req.set_header(key.lower(), value)
                # Using lowercase format i.e. content-type, content-length

            self.logger.trace("headers parsed.")

            if req.has_header("content-length"):
                l = int(req.get_header("content-length"))
                if l > 0:
                    # There is data
                    data_raw = await reader.readexactly(l)
                    readAll = True

                    ctype = req.get_header("content-type")
                    if ctype == "application/x-www-form-urlencoded":
                        for entry in data_raw.decode().split("&"):
                            try:
                                key, value = entry.split("=")
                            except ValueError:
                                # Not enough values to unpack
                                # malformed form data
                                self.logger.warn("POST data not a valid application/x-www-form-urlencoded string.")
                                self.logger.warn("received \"{}\", bad request.".format(line))
                                raise HTTPException(BAD_REQUEST, "POST data=\"{}\" not a valid application/x-www-form-urlencoded string.".format(line))

                            req.set_data(key, value)

                    # TODO add more content types (for ex. JSON)
                    else:
                        self.logger.warn("content-type=\"{}\" not implemented.".format(ctype))
                        raise HTTPException(NOT_IMPLEMENTED, "Content-type \"{}\" is not implemented".format(ctype))

            readAll = True
            self.logger.trace("data parsed.")

            if req.method not in SUPPORTED_METHODS:
                self.logger.warn("method=\"{}\" not implemented.".format(req.method))
                raise HTTPException(NOT_IMPLEMENTED, "Method \"{}\" is not implemented".format(req.method))

            self.logger.trace("resolving route.")

            try:
                route = self.routes[req.path]
            except KeyError:
                self.logger.warn("path=\"{}\" not found.".format(req.path))
                raise HTTPException(NOT_FOUND, "Path \"{}\" not found".format(req.path))

            try:
                func = route[req.method]
            except KeyError:
                self.logger.warn("method=\"{}\" not allowed on {}.".format(req.method, req.path))
                raise HTTPException(METHOD_NOT_ALLOWED, "Method \"{}\" is not allowed on {}".format(req.method, req.path))

            async def send(): await resp.send_internal(req, self.logger, writer)
            resp.define_send(send)

            self.logger.trace("calling route, sending response.")
            await func(req, resp) # raises HTTPException
            self.logger.trace("route finished gracefully.")

            if not resp.isSent:
                await resp.send()
                connection_closed = True

        except HTTPException as e:
            if not readAll:
                await reader.read(-1)

            resp.clear()
            resp.code(e.code)
            resp.body("<h1>{}</h1>".format(code_reason_map[e.code]))
            resp.body("<pre>{}</pre>".format(e.msg))

            await resp.send_internal(None, self.logger, writer, body_must_be_string=True)
            connection_closed = True

        finally:
            if not connection_closed:
                if not readAll:
                    await reader.read(-1)

                await writer.drain()
                await writer.wait_closed()

                self.logger.debug("response sent.")

    def route(self, url, methods=SUPPORTED_METHODS):
        """Add route

        Example:
            @srv.route("/", methods="GET")
            async def root(req: WebRequest, resp: WebResponse):
                ...
                resp.header()
                ...
                resp.body()
                resp.body()
                ...
                resp.send() or raise HTTPException(code, msg)
                ^ can be omitted

        Object-like body (tuple, list, dict) can be added only once and will be stringified automatically.

        If HTTPException is raised, body and headers will be ignored.
        """

        def decorator(func):

            self.logger.trace("adding route {} ({}) -> {}".format(url, methods, func))

            def add_route(method):
                if url not in self.routes:
                    self.routes[url] = {}

                self.routes[url][method] = func

            if isinstance(methods, str):
                add_route(methods)
            else:
                for method in methods:
                    add_route(method)

            return func

        return decorator