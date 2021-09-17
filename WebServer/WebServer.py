import Logger.Logger as Logger
import uasyncio as asyncio
from WebServer.HTTPException import HTTPException, BAD_REQUEST, NOT_FOUND, METHOD_NOT_ALLOWED, INTERNAL_SERVER_ERROR, NOT_IMPLEMENTED
from WebServer.WebRequest import WebRequest
from WebServer.WebResponse import WebResponse

SUPPORTED_METHODS = ("GET", "POST")

def gen_status_report(status, message):
    return {
        "status": status,
        "message": message
    }

class WebServer:
    def __init__(self, loglevel=Logger.INFO, static="/static"):
        self.logger = Logger.Logger("websrv", loglevel=loglevel)
        self.srv = None
        self.routes = {}
        self._static_folder = static

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
        req = None
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
                if first_line == b"": readAll = True
                raise HTTPException(BAD_REQUEST, "First line ({}) of the request was malformed.".format(first_line), early=True)

            req = WebRequest(method)

            try:
                req.parse_url(url)
            except ValueError as e:
                # Not enough values to unpack
                # Or too long splitted URL
                # malformed url
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
                                raise HTTPException(BAD_REQUEST, "POST data=\"{}\" not a valid application/x-www-form-urlencoded string.".format(line))

                            req.set_data(key, value)

                    # TODO add more content types (for ex. JSON)
                    else:
                        raise HTTPException(NOT_IMPLEMENTED, "Content-type \"{}\" is not implemented".format(ctype))

            readAll = True
            self.logger.trace("data parsed.")

            if req.method not in SUPPORTED_METHODS:
                raise HTTPException(NOT_IMPLEMENTED, "Method \"{}\" is not implemented".format(req.method))

            self.logger.trace("resolving route.")

            if req.path in self.routes:
                # there is route
                route = self.routes[req.path]

                try:
                    func = route[req.method]
                except KeyError:
                    raise HTTPException(METHOD_NOT_ALLOWED, "Method \"{}\" is not allowed on {}".format(req.method, req.path))

                async def send(): await resp.send_internal(req, self.logger, writer)
                resp.define_send(send)

                self.logger.trace("calling route, sending response.")

                # raises HTTPException, can raise MemoryError
                await func(req, resp)
                if not resp.isSent:
                    await resp.send()

                self.logger.trace("route finished gracefully.")

            elif method == "GET" and self._static_folder != None:
                # no route, try file, only with GET, if static folder set
                if req.path == "/": req.path = "/index.html"
                req.path = self._static_folder + req.path

                try:
                    await resp.send_file(req.path, writer)
                except OSError:
                    # no such file
                    raise HTTPException(NOT_FOUND, "Path \"{}\" not found".format(req.path))

            else:
                # no route
                raise HTTPException(NOT_FOUND, "Path \"{}\" not found".format(req.path))

            if resp.isSent:
                connection_closed = True

        except MemoryError as e:
            self.logger.error("Out of Memory.")
            self.logger.error(str(e))

            if not readAll:
                await reader.read(-1)

            resp.clear()
            resp.code(INTERNAL_SERVER_ERROR)
            resp.body("<h1>Out of Memory</h1>")

            await resp.send_internal(req, self.logger, writer)
            connection_closed = True

            import micropython
            micropython.mem_info(1)

        except HTTPException as e:
            self.logger.warn("HTTPException {}.".format(e.get_reason()))
            self.logger.warn(e.msg)

            if not readAll:
                await reader.read(-1)

            resp.clear()
            resp.code(e.code)

            if e.early:
                # req is None, no JSON support (no headers)
                resp.body("<h1>{}</h1>".format(e.get_reason()))
                resp.body("<pre>{}</pre>".format(e.msg))

            else:
                resp.body(gen_status_report("error", e.msg))

            await resp.send_internal(req, self.logger, writer)
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