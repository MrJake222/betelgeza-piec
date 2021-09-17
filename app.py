import binascii
import uasyncio as asyncio
import Logger.Logger as Logger
import WiFi
from WebServer.HTTPException import *
from WebServer.WebRequest import WebRequest
from WebServer.WebResponse import WebResponse
from WebServer.WebServer import WebServer, gen_status_report
from Multicast.Multicast import Multicast

LOGLEVEL = Logger.DEBUG
logger = Logger.Logger("main", loglevel=LOGLEVEL)
wifi = WiFi.WiFi(loglevel=LOGLEVEL)
srv = WebServer(loglevel=LOGLEVEL)
mcast = Multicast("esp8266", wifi, loglevel=LOGLEVEL)

name_map = ("ssid", "bssid", "channel", "rssi", "authmode", "hidden")
auth_map = ("open", "WEP", "WPA-PSK", "WPA2-PSK", "WPA/WPA2-PSK")

@srv.route("/wifi_scan", methods="GET")
async def wifi_scan(req: WebRequest, resp: WebResponse):
    netinfo = []

    for network in wifi.scan():
        net = {}
        for i, val in enumerate(network):
            if i == 1: val = binascii.hexlify(val, ":")
            elif i == 4: val = auth_map[int(val)]
            net[name_map[i]] = val

        net["connected"] = (net["ssid"].decode() == wifi.get_ssid())
        netinfo.append(net)

    resp.header("content-type", "application/json")
    resp.body(netinfo)

@srv.route("/wifi_mode", methods="GET")
async def wifi_scan(req: WebRequest, resp: WebResponse):
    resp.header("content-type", "application/json")
    resp.body({"mode": wifi.get_mode_str()})

@srv.route("/set_config", methods="POST")
async def set_config_post(req: WebRequest, resp: WebResponse):
    # Change config
    resp.header("content-type", "application/json")

    def send_status_log(status):
        logger.info("wifi status: {}".format(status))
        resp.body(gen_status_report("ok", status))

    try:
        mode = req.get_data("mode")
    except KeyError:
        raise HTTPException(BAD_REQUEST, "No mode given.")

    if mode == "ap":
        if wifi.get_mode() != WiFi.MODE_AP:
            send_status_log("Starting AP.")
            await resp.send()
            await stop_servers()
            wifi.start_ap()
            await start_servers()

        else:
            send_status_log("Not modified.")

    elif mode == "sta":
        try:
            ssid = req.get_data("ssid")
            password = req.get_data("pass")
        except KeyError:
            raise HTTPException(BAD_REQUEST, "STA mode requires SSID and PASS")

        if wifi.get_mode() != WiFi.MODE_STA or ssid != wifi.get_ssid():
            send_status_log("Starting STA mode, ssid={}.".format(ssid))
            await resp.send()
            await stop_servers()
            await wifi.start_sta_connect(ssid, password, new_config=True)
            await start_servers()

        else:
            send_status_log("Not modified.")

    else:
        raise HTTPException(BAD_REQUEST, "Wrong mode given.")

connections = (srv, mcast)

async def start_servers():
    await asyncio.gather(*[x.start() for x in connections])
    logger.debug("servers started.")

async def stop_servers():
    await asyncio.gather(*[x.stop() for x in connections])
    logger.debug("servers stopped.")

async def main():
    await wifi.start()
    await start_servers()

    while True:
        await asyncio.sleep(10)

def start():
    asyncio.run(main())