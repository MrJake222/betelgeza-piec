import uasyncio as asyncio
import Logger.Logger as Logger
import WiFi
from WebServer.HTTPException import *
from WebServer.WebRequest import WebRequest
from WebServer.WebResponse import WebResponse
from WebServer.WebServer import WebServer
from Multicast.Multicast import Multicast

LOGLEVEL = Logger.DEBUG
logger = Logger.Logger("main", loglevel=LOGLEVEL)
wifi = WiFi.WiFi(loglevel=LOGLEVEL)
srv = WebServer(loglevel=LOGLEVEL)
mcast = Multicast("esp8266", wifi, loglevel=Logger.TRACE)

@srv.route("/set_config", methods="GET")
async def set_config_get(req: WebRequest, resp: WebResponse):

    resp.header("content-type", "text/html")

    resp.body("<h1>Set config</h1>")
    resp.body("<h3>Current mode: {} {}</h3>".format(wifi.get_mode_str(), wifi.get_ssid()))

    resp.body("<form action='/set_config' method='POST'>")
    resp.body("<input type='radio' name='mode' value='ap'/> AP")
    resp.body("<input type='radio' name='mode' value='sta'/> STA<br/>")
    resp.body("<input type='text' name='ssid'/><br/>")
    resp.body("<input type='text' name='pass'/><br/>")
    resp.body("<input type='submit' value='Set config'/>")
    resp.body("</form>")

@srv.route("/set_config", methods="POST")
async def set_config_post(req: WebRequest, resp: WebResponse):

    resp.header("content-type", "text/html")

    # Change config
    try:
        mode = req.get_data("mode")
    except KeyError:
        raise HTTPException(BAD_REQUEST, "No mode given.")

    if mode == "ap":
        if wifi.get_mode() != WiFi.MODE_AP:
            resp.body("Starting AP.")
            logger.info("starting AP.")
            await resp.send()
            await stop_servers()
            wifi.start_ap()
            await start_servers()

        else:
            resp.body("Not modified.")

    elif mode == "sta":
        try:
            ssid = req.get_data("ssid")
            password = req.get_data("pass")
        except KeyError:
            raise HTTPException(BAD_REQUEST, "STA mode requires SSID and PASS")

        if wifi.get_mode() != WiFi.MODE_STA or ssid != wifi.get_ssid():
            resp.body("Starting STA mode, ssid={}.".format(ssid))
            logger.info("starting STA mode ssid={}.".format(ssid))
            await resp.send()
            await stop_servers()
            await wifi.start_sta_connect(ssid, password, new_config=True)
            await start_servers()

        else:
            resp.body("Not modified.")

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

asyncio.run(main())