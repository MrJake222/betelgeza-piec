import uasyncio as asyncio
import logger.Logger as Logger
import WiFi
from WebServer.HTTPException import *
from WebServer.WebRequest import WebRequest
from WebServer.WebResponse import WebResponse
from WebServer.WebServer import WebServer

LOGLEVEL = Logger.DEBUG
logger = Logger.Logger("main", loglevel=LOGLEVEL)
wifi = WiFi.WiFi(loglevel=LOGLEVEL)
srv = WebServer(loglevel=LOGLEVEL)

@srv.route("/set_config")
async def set_config(req: WebRequest, resp: WebResponse):

    resp.header("content-type", "text/html")

    resp.body("<h1>Set config</h1>")
    resp.body("<h3>Current mode: {} {}</h3>".format(wifi.getModeStr(), wifi.getSSID()))

    if req.is_get():
        resp.body("<form action='/set_config' method='POST'>")
        resp.body("<input type='radio' name='mode' value='ap'/> AP")
        resp.body("<input type='radio' name='mode' value='sta'/> STA<br/>")
        resp.body("<input type='text' name='ssid'/><br/>")
        resp.body("<input type='text' name='pass'/><br/>")
        resp.body("<input type='submit' value='Set config'/>")
        resp.body("</form>")

    elif req.is_post():
        # Change config
        try:
            mode = req.get_data("mode")
        except KeyError:
            raise HTTPException(BAD_REQUEST, "No mode given.")

        if mode == "ap":
            if wifi.getMode() != WiFi.MODE_AP:
                resp.body("Starting AP.")
                logger.info("starting AP.")
                await resp.send()
                wifi.start_ap()

            else:
                resp.body("Not modified.")

        elif mode == "sta":
            try:
                ssid = req.get_data("ssid")
                password = req.get_data("pass")
            except KeyError:
                raise HTTPException(BAD_REQUEST, "STA mode requires SSID and PASS")

            if wifi.getMode() != WiFi.MODE_STA:
                resp.body("Starting STA mode, ssid={}.".format(ssid))
                logger.info("starting STA mode ssid={}.".format(ssid))
                await resp.send()
                await wifi.start_sta_connect(ssid, password, new_config=True)

            elif ssid != wifi.getSSID():
                resp.body("Changing AP, ssid={}.".format(ssid))
                logger.info("changing AP, ssid={}.".format(ssid))
                await resp.send()
                await wifi.start_sta_connect(ssid, password, new_config=True)

            else:
                resp.body("Not modified.")

        else:
            raise HTTPException(BAD_REQUEST, "Wrong mode given.")

async def main():
    await wifi.start()
    await srv.start()

    while True:
        await asyncio.sleep(10)

asyncio.run(main())