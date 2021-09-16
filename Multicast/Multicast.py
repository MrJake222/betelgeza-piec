import socket
import select
import uasyncio as asyncio
from Multicast.MulticastException import MulticastException, BAD_REQUEST
import Logger.Logger as Logger
from WiFi import WiFi

MCAST_GRP = "239.255.173.63"
MCAST_PORT = 1200
BUFSIZE = 32

def _aton(ip):
    sp = ip.split(".")
    arr = bytearray(8)
    for i in range(4): arr[i] = int(sp[i])
    for i in range(4, 8): arr[i] = 0
    return arr

class Multicast:
    def __init__(self, name, wifi: WiFi, loglevel=Logger.INFO):
        self.name = name.lower()
        self.wifi = wifi
        self._logger = Logger.Logger("mcast", loglevel=loglevel)

        self._srv_sock = None
        self._grp = None

        self._client_sock = None
        self._poll = None

        self._should_listen = True
        self._stopped_listening = asyncio.Event()
        self._stopped_listening.set()

    async def start(self, grp=MCAST_GRP, port=MCAST_PORT):
        self._srv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._srv_sock.setsockopt(socket.IPPROTO_IP, socket.SO_REUSEADDR, 1)

        self._srv_sock.setblocking(False)
        self._srv_sock.bind((grp, port))
        self._grp = grp

        # join multicast group
        self._srv_sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, _aton(grp))

        # client socket
        self._client_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self._poll = select.poll()
        self._poll.register(self._srv_sock)

        self._stopped_listening.clear()
        self._should_listen = True

        asyncio.create_task(self._listen())
        self._logger.info("multicast listener started.")

    def _listen(self):
        while self._should_listen:
            for s, ev in self._poll.ipoll():
                if ev & select.POLLIN:
                    buf, (c_ip, c_port) = s.recvfrom(BUFSIZE)
                    self._logger.debug("multicast request from {}:{}.".format(c_ip, c_port))
                    c_port = int(c_port)
                    buf = buf.decode()

                    try:
                        try:
                            action, params = buf.split(" ", 1)
                            params = params.split(" ")
                        except ValueError:
                            raise MulticastException(BAD_REQUEST, "error unpacking action/parameters")

                        self._logger.trace("action: {}, params: {}.".format(action, params))

                        if action == "ID":
                            # identify
                            try:
                                name = params[0].lower()
                            except IndexError:
                                raise MulticastException(BAD_REQUEST, "error unpacking parameters in {}".format(action))

                            if name == "any" or name == self.name:
                                self._logger.info("-> {} {}".format(action, name))

                                self._logger.trace("responding ID {} {}.".format(self.name, self.wifi.get_current_ip()))
                                self._client_sock.sendto("ID {} {}".format(self.name, self.wifi.get_current_ip()).encode(), (c_ip, c_port))

                        # TODO add more actions
                        else:
                            raise MulticastException(BAD_REQUEST, "action not supported: {}".format(action))

                        self._logger.debug("response sent")

                    except MulticastException as e:
                        self._logger.warn("{}, code={}.".format(e.msg, e.code))
                        self._client_sock.sendto("ERR {} {}".format(e.code, e.msg).encode(), (c_ip, c_port))


            await asyncio.sleep(0.1)

        self._poll.unregister(self._srv_sock)
        self._srv_sock.setsockopt(socket.IPPROTO_IP, socket.IP_DROP_MEMBERSHIP, _aton(self._grp))

        self._stopped_listening.set()

    async def stop(self):
        self._should_listen = False
        await self._stopped_listening.wait()

        self._logger.info("multicast listener stopped.")

