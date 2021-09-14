class WebRequest:
    def __init__(self, method):
        self.method = method
        self.path = None
        self._headers = {}
        self._urldata = {}
        self._data = {}

    def is_get(self):
        return self.method == "GET"

    def is_post(self):
        return self.method == "POST"

    def set_header(self, key, value):
        self._headers[key] = value

    def has_header(self, key):
        return key in self._headers

    def get_header(self, key):
        return self._headers[key]

    def parse_url(self, url):
        url_split = url.split("?")
        self.path = url_split[0]

        if len(url_split) == 2:
            for entry in url_split[1].split("&"):
                key, value = entry.split("=") # raises ValueError
                self._urldata[key] = value

        elif len(url_split) > 2:
            raise ValueError("Splitted URL (by ?) more than two parts.")

    def has_urldata(self, key):
        return key in self._urldata

    def get_urldata(self, key):
        return self._urldata[key]

    def set_data(self, key, value):
        self._data[key] = value

    def has_data(self, key):
        return key in self._data

    def get_data(self, key):
        return self._data[key]