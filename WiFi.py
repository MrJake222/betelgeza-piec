import uasyncio as asyncio
import Logger.Logger as Logger
import config_parser
import network

CONFIG_FILE = "wifi.cfg"
AP_SSID = "ESP 8266"
AP_PASS = "test1234"
MAX_TRIES = 20

# config keys
C_MODE = "mode"
C_SSID = "ssid"
C_PASS = "pass"

MODE_STA = 0
MODE_AP = 1

class WiFi:
    def __init__(self, loglevel=Logger.INFO):
        self.logger = Logger.Logger("wifi", loglevel=loglevel)
        self._mode = None
        self._ssid = None
        self._password = None

    async def start(self):
        try:
            config = config_parser.read_dict(CONFIG_FILE)
            self.logger.debug("loaded config file.")

            if int(config[C_MODE]) == MODE_STA:
                self.logger.debug("connecting to {} pass={}.".format(config[C_SSID], config[C_PASS]))
                await self.start_sta_connect(config[C_SSID], config[C_PASS], new_config=False)
            else:
                self.logger.debug("starting AP ssid={}.".format(AP_SSID))
                self.start_ap()

        except OSError:
            self.logger.debug("no config file, starting AP mode.")
            self.start_ap()

    async def start_sta_connect(self, ssid, password, new_config):
        # Disable AP mode
        network.WLAN(network.AP_IF).active(False)

        sta = network.WLAN(network.STA_IF)
        sta.active(True)

        if sta.isconnected():
            sta.disconnect()
            while sta.isconnected():
                await asyncio.sleep(0.1)

        sta.connect(ssid, password)

        while not sta.isconnected():
            try_no = 1
            while not sta.isconnected() and (try_no <= MAX_TRIES or not new_config):
                self.logger.debug("trying to connect, try {}.".format(try_no))
                await asyncio.sleep_ms(500)
                try_no += 1

            if sta.isconnected():
                if new_config:
                    self.logger.debug("connected to new network, saving config.")
                    config = { C_MODE: MODE_STA, C_SSID: ssid, C_PASS: password }
                    config_parser.save_dict(CONFIG_FILE, config)
                    self.logger.info("config saved.")
                # old config -> do nothing

            else:
                # not connected
                if new_config:
                    # probably wrong password
                    # revert to AP
                    # TODO LEDs
                    self.logger.info("reverting WiFi configuration. starting {} mode".format(self.get_mode_str()))

                    if self._mode == MODE_AP:
                        self.start_ap()
                    else:
                        await self.start_sta_connect(self._ssid, self._password, new_config=False)

                    return

                # old config cannot fail

        self._mode = MODE_STA
        self._ssid = ssid
        self._password = password
        ip, _, _, _ = sta.ifconfig()
        self.logger.info("connected to {}, ip={}.".format(ssid, ip))

    def start_ap(self):
        # Disable STA mode
        network.WLAN(network.STA_IF).active(False)

        ap = network.WLAN(network.AP_IF)
        ap.active(True)
        ap.config(essid=AP_SSID, password=AP_PASS)

        self._mode = MODE_AP
        self._ssid = AP_SSID
        self._password = AP_PASS
        ip, _, _, _ = ap.ifconfig()
        self.logger.info("started AP <{}> pass={}, ip={}".format(AP_SSID, AP_PASS, ip))

        config = { C_MODE: MODE_AP }
        config_parser.save_dict(CONFIG_FILE, config)
        self.logger.info("config saved.")

    def get_mode(self):
        return self._mode

    def get_mode_str(self):
        if self._mode == MODE_STA: return "STA"
        elif self._mode == MODE_AP: return "AP"
        else: return "<unspecified>"

    def get_ssid(self):
        return self._ssid

    def get_active_interface(self):
        if self._mode == MODE_AP:
            return network.WLAN(network.AP_IF)
        elif self._mode == MODE_STA:
            return network.WLAN(network.STA_IF)
        else:
            return None

    def get_current_ip(self):
        wlan = self.get_active_interface()
        if wlan == None:
            return None

        ip, _, _, _ = wlan.ifconfig()
        return ip