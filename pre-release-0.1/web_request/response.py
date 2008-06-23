class Response(object): 
    status_code = 200
    extra_headers = None
    content_type = "text/plain"
    data = ""
    def __init__(self, data="", content_type=None, headers = None, status_code=None):
        if data:
            self.data = data
        if content_type:
            self.content_type = content_type
        if headers:
            self.extra_headers = headers
        if status_code:
            self.status_code = status_code
            
