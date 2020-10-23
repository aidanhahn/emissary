from abstract_tests import AmbassadorTest, HTTP

from kat.harness import Query


class ErrorResponseOnStatusCode(AmbassadorTest):
    """
    Check that we can return a customized error response where the body is built as a formatted string.
    """
    def init(self):
        self.target = HTTP()

    def config(self):
        yield self, f'''
---
apiVersion: getambassador.io/v1
kind: Module
name: ambassador
ambassador_id: {self.ambassador_id}
config:
  error_response_overrides:
  - on_status_code: 401
    body:
      text_format: 'you get a 401'
  - on_status_code: 403
    body:
      text_format: 'and you get a 403'
  - on_status_code: 404
    body:
      text_format: 'cannot find the thing'
  - on_status_code: 418
    body:
      text_format: '2teapot2reply'
  - on_status_code: 500
    body:
      text_format: 'a five hundred happened'
  - on_status_code: 501
    body:
      text_format: 'very not implemented'
  - on_status_code: 503
    body:
      text_format: 'the upstream probably died'
  - on_status_code: 504
    body:
      text_format: 'took too long, sorry'
---
apiVersion: ambassador/v2
kind:  Mapping
name:  {self.target.path.k8s}
ambassador_id: {self.ambassador_id}
prefix: /target/
service: {self.target.path.fqdn}
---
apiVersion: ambassador/v2
kind:  Mapping
name:  {self.target.path.k8s}-invalidservice
ambassador_id: {self.ambassador_id}
prefix: /target/invalidservice
service: {self.target.path.fqdn}-invalidservice
'''

    def queries(self):
        # [0]
        yield Query(self.url("does-not-exist/"), expected=404)
        # [1]
        yield Query(self.url("target/"), headers={"requested-status": "401"}, expected=401)
        # [2]
        yield Query(self.url("target/"), headers={"requested-status": "403"}, expected=403)
        # [3]
        yield Query(self.url("target/"), headers={"requested-status": "404"}, expected=404)
        # [4]
        yield Query(self.url("target/"), headers={"requested-status": "418"}, expected=418)
        # [5]
        yield Query(self.url("target/"), headers={"requested-status": "500"}, expected=500)
        # [6]
        yield Query(self.url("target/"), headers={"requested-status": "501"}, expected=501)
        # [7]
        yield Query(self.url("target/"), headers={"requested-status": "503"}, expected=503)
        # [8]
        yield Query(self.url("target/"), headers={"requested-status": "504"}, expected=504)
        # [9]
        yield Query(self.url("target/"))
        # [10]
        yield Query(self.url("target/invalidservice"), expected=503)

    def check(self):
        # [0]
        assert self.results[0].text == 'cannot find the thing', \
            f"unexpected response body: {self.results[0].text}"

        # [1]
        assert self.results[1].text == 'you get a 401', \
            f"unexpected response body: {self.results[1].text}"

        # [2]
        assert self.results[2].text == 'and you get a 403', \
            f"unexpected response body: {self.results[2].text}"

        # [3]
        assert self.results[3].text == 'cannot find the thing', \
            f"unexpected response body: {self.results[3].text}"

        # [4]
        assert self.results[4].text == '2teapot2reply', \
            f"unexpected response body: {self.results[4].text}"

        # [5]
        assert self.results[5].text == 'a five hundred happened', \
            f"unexpected response body: {self.results[5].text}"

        # [6]
        assert self.results[6].text == 'very not implemented', \
            f"unexpected response body: {self.results[6].text}"

        # [7]
        assert self.results[7].text == 'the upstream probably died', \
            f"unexpected response body: {self.results[7].text}"

        # [8]
        assert self.results[8].text == 'took too long, sorry', \
            f"unexpected response body: {self.results[8].text}"

        # [9] should just succeed
        assert self.results[9].text == None, \
            f"unexpected response body: {self.results[9].text}"

        # [10] envoy-generated 503, since the upstream is 'invalidservice'.
        assert self.results[10].text == 'the upstream probably died', \
            f"unexpected response body: {self.results[10].text}"


class ErrorResponseReturnBodyFormattedText(AmbassadorTest):
    """
    Check that we can return a customized error response where the body is built as a formatted string.
    """
    def init(self):
        self.target = HTTP()

    def config(self):
        yield self, f'''
---
apiVersion: getambassador.io/v1
kind: Module
name: ambassador
ambassador_id: {self.ambassador_id}
config:
  error_response_overrides:
  - on_status_code: 404
    body:
      text_format: 'there has been an error: %RESPONSE_CODE%'
  - on_status_code: 429
    body:
      text_format: '<html>2fast %PROTOCOL%</html>'
      content_type: 'text/html'
  - on_status_code: 504
    body:
      text_format: '<html>2slow %PROTOCOL%</html>'
      content_type: 'text/html; charset="utf-8"'
---
apiVersion: ambassador/v2
kind:  Mapping
name:  {self.target.path.k8s}
ambassador_id: {self.ambassador_id}
prefix: /target/
service: {self.target.path.fqdn}
'''

    def queries(self):
        # [0]
        yield Query(self.url("does-not-exist/"), expected=404)

        # [1]
        yield Query(self.url("target/"), headers={"requested-status": "429"}, expected=429)

        # [2]
        yield Query(self.url("target/"), headers={"requested-status": "504"}, expected=504)

    def check(self):
        # [0]
        print("headers = %s" % self.results[0].headers)
        assert self.results[0].text == "there has been an error: 404", \
            f"unexpected response body: {self.results[0].text}"
        assert self.results[0].headers["Content-Type"] == ["text/plain"], \
            f"unexpected Content-Type: {self.results[0].headers}"

        # [1]
        assert self.results[1].text == "<html>2fast HTTP/1.1</html>", \
            f"unexpected response body: {self.results[1].text}"
        assert self.results[1].headers["Content-Type"] == ["text/html"], \
            f"unexpected Content-type: {self.results[1].headers}"

        # [2]
        assert self.results[2].text == "<html>2slow HTTP/1.1</html>", \
            f"unexpected response body: {self.results[2].text}"
        assert self.results[2].headers["Content-Type"] == ["text/html; charset=\"utf-8\""], \
            f"unexpected Content-Type: {self.results[2].headers}"


class ErrorResponseReturnBodyFormattedJson(AmbassadorTest):
    """
    Check that we can return a customized error response where the body is built from a text source.
    """
    def init(self):
        self.target = HTTP()

    def config(self):
        yield self, f'''
---
apiVersion: getambassador.io/v1
kind: Module
name: ambassador
ambassador_id: {self.ambassador_id}
config:
  error_response_overrides:
  - on_status_code: 401
    body:
      json_format:
        error: 'unauthorized'
  - on_status_code: 404
    body:
      json_format:
        custom_error: 'truth'
        code: '%RESPONSE_CODE%'
  - on_status_code: 429
    body:
      json_format:
        custom_error: 'yep'
        toofast: 'definitely'
        code: 'code was %RESPONSE_CODE%'
---
apiVersion: ambassador/v2
kind:  Mapping
name:  {self.target.path.k8s}
ambassador_id: {self.ambassador_id}
prefix: /target/
service: {self.target.path.fqdn}
'''

    def queries(self):
        yield Query(self.url("does-not-exist/"), expected=404)
        yield Query(self.url("target/"), headers={"requested-status": "429"}, expected=429)
        yield Query(self.url("target/"), headers={"requested-status": "401"}, expected=401)

    def check(self):
        # [0]
        # Strange gotcha: it looks like we always get an integer code here
        # even though the field specifier above is wrapped in single quotes.
        assert self.results[0].json == { "custom_error": "truth", "code": 404 }, \
            f"unexpected response body: {self.results[0].json}"
        assert self.results[0].headers["Content-Type"] == ["application/json"], \
            f"unexpected Content-Type: {self.results[0].headers}"

        # [1]
        assert self.results[1].json == { "custom_error": "yep", "toofast": "definitely", "code": "code was 429" }, \
            f"unexpected response body: {self.results[1].json}"
        assert self.results[1].headers["Content-Type"] == ["application/json"], \
            f"unexpected Content-Type: {self.results[1].headers}"

        # [2]
        assert self.results[2].json == { "error": "unauthorized" }, \
            f"unexpected response body: {self.results[2].json}"
        assert self.results[2].headers["Content-Type"] == ["application/json"], \
            f"unexpected Content-Type: {self.results[2].headers}"


class ErrorResponseReturnBodyTextSource(AmbassadorTest):
    """
    Check that we can return a customized error response where the body is built as a formatted string.
    """
    def init(self):
        self.target = HTTP()

    def config(self):
        yield self, f'''
---
apiVersion: getambassador.io/v1
kind: Module
name: ambassador
ambassador_id: {self.ambassador_id}
config:
  error_response_overrides:
  - on_status_code: 500
    body:
      text_format_source:
        filename: '/etc/issue'
      content_type: 'application/etcissue'
  - on_status_code: 503
    body:
      text_format_source:
        filename: '/etc/motd'
      content_type: 'application/motd'
  - on_status_code: 504
    body:
      text_format_source:
        filename: '/etc/shells'
---
apiVersion: ambassador/v2
kind:  Mapping
name:  {self.target.path.k8s}
ambassador_id: {self.ambassador_id}
prefix: /target/
service: {self.target.path.fqdn}
'''

    def queries(self):
        # [0]
        yield Query(self.url("target/"), headers={"requested-status": "500"}, expected=500)

        # [1]
        yield Query(self.url("target/"), headers={"requested-status": "503"}, expected=503)

        # [2]
        yield Query(self.url("target/"), headers={"requested-status": "504"}, expected=504)

    def check(self):
        # [0] Sorry for using /etc/issue...
        print("headers = %s" % self.results[0].headers)
        assert "Welcome to Alpine Linux" in self.results[0].text, \
            f"unexpected response body: {self.results[0].text}"
        assert self.results[0].headers["Content-Type"] == ["application/etcissue"], \
            f"unexpected Content-Type: {self.results[0].headers}"

        # [1] ...and sorry for using /etc/motd...
        assert "You may change this message by editing /etc/motd." in self.results[1].text, \
            f"unexpected response body: {self.results[1].text}"
        assert self.results[1].headers["Content-Type"] == ["application/motd"], \
            f"unexpected Content-Type: {self.results[1].headers}"

        # [2] ...and sorry for using /etc/shells
        assert "# valid login shells" in self.results[2].text, \
            f"unexpected response body: {self.results[2].text}"
        assert self.results[2].headers["Content-Type"] == ["text/plain"], \
            f"unexpected Content-Type: {self.results[2].headers}"

class ErrorResponseMappingBypass(AmbassadorTest):
    """
    Check that we can return a bypass custom error responses at the mapping level
    """
    def init(self):
        self.target = HTTP()

    def config(self):
        yield self, f'''
---
apiVersion: getambassador.io/v1
kind: Module
name: ambassador
ambassador_id: {self.ambassador_id}
config:
  error_response_overrides:
  - on_status_code: 404
    body:
      text_format: 'this is a custom 404 response'
      content_type: 'text/custom'
  - on_status_code: 418
    body:
      text_format: 'bad teapot request'
  - on_status_code: 503
    body:
      text_format: 'the upstream is not happy'
---
apiVersion: ambassador/v2
kind:  Mapping
name:  {self.target.path.k8s}
ambassador_id: {self.ambassador_id}
prefix: /target/
service: {self.target.path.fqdn}
---
apiVersion: ambassador/v2
kind:  Mapping
name:  {self.target.path.k8s}-invalidservice
ambassador_id: {self.ambassador_id}
prefix: /target/invalidservice
service: {self.target.path.fqdn}-invalidservice
---
apiVersion: ambassador/v2
kind:  Mapping
name:  {self.target.path.k8s}-bypass
ambassador_id: {self.ambassador_id}
prefix: /bypass/
service: {self.target.path.fqdn}
bypass_error_response_overrides: true
---
apiVersion: ambassador/v2
kind:  Mapping
name:  {self.target.path.k8s}-target-bypass
ambassador_id: {self.ambassador_id}
prefix: /target/bypass/
service: {self.target.path.fqdn}
bypass_error_response_overrides: true
---
apiVersion: ambassador/v2
kind:  Mapping
name:  {self.target.path.k8s}-bypass-invalidservice
ambassador_id: {self.ambassador_id}
prefix: /bypass/invalidservice
service: {self.target.path.fqdn}-invalidservice
bypass_error_response_overrides: true
'''

    def queries(self):
        # [0]
        yield Query(self.url("bypass/"), headers={"requested-status": "404"}, expected=404)
        # [1]
        yield Query(self.url("target/"), headers={"requested-status": "404"}, expected=404)
        # [2]
        yield Query(self.url("target/bypass/"), headers={"requested-status": "418"}, expected=418)
        # [3]
        yield Query(self.url("target/"), headers={"requested-status": "418"}, expected=418)
        # [4]
        yield Query(self.url("target/invalidservice"), expected=503)
        # [5]
        yield Query(self.url("bypass/invalidservice"), expected=503)
        # [6]
        yield Query(self.url("bypass/"), headers={"requested-status": "503"}, expected=503)
        # [7]
        yield Query(self.url("target/"), headers={"requested-status": "503"}, expected=503)
        # [8]
        yield Query(self.url("bypass/"), headers={"requested-status": "200"})
        # [9]
        yield Query(self.url("target/"), headers={"requested-status": "200"})

    def check(self):
        # [0]
        assert self.results[0].text is None, \
            f"unexpected response body: {self.results[0].text}"

        # [1]
        assert self.results[1].text == 'this is a custom 404 response', \
            f"unexpected response body: {self.results[1].text}"
        assert self.results[1].headers["Content-Type"] == ["text/custom"], \
            f"unexpected Content-Type: {self.results[1].headers}"

        # [2]
        assert self.results[2].text is None, \
            f"unexpected response body: {self.results[2].text}"

        # [3]
        assert self.results[3].text == 'bad teapot request', \
            f"unexpected response body: {self.results[3].text}"

        # [4]
        assert self.results[4].text == 'the upstream is not happy', \
            f"unexpected response body: {self.results[4].text}"

        # [5]
        assert self.results[5].text == 'no healthy upstream', \
            f"unexpected response body: {self.results[5].text}"
        assert self.results[5].headers["Content-Type"] == ["text/plain"], \
            f"unexpected Content-Type: {self.results[5].headers}"

        # [6]
        assert self.results[6].text is None, \
            f"unexpected response body: {self.results[6].text}"

        # [7]
        assert self.results[7].text == 'the upstream is not happy', \
            f"unexpected response body: {self.results[7].text}"

        # [8]
        assert self.results[8].text is None, \
            f"unexpected response body: {self.results[8].text}"

        # [9]
        assert self.results[9].text is None, \
            f"unexpected response body: {self.results[9].text}"

class ErrorResponseMappingBypassAlternate(AmbassadorTest):
    """
    Check that we can alternate between serving a custom error response and not
    serving one. This is a baseline sanity check against Envoy's response map
    filter incorrectly persisting state across filter chain iterations.
    """
    def init(self):
        self.target = HTTP()

    def config(self):
        yield self, f'''
---
apiVersion: getambassador.io/v1
kind: Module
name: ambassador
ambassador_id: {self.ambassador_id}
config:
  error_response_overrides:
  - on_status_code: 404
    body:
      text_format: 'this is a custom 404 response'
      content_type: 'text/custom'
---
apiVersion: ambassador/v2
kind:  Mapping
name:  {self.target.path.k8s}
ambassador_id: {self.ambassador_id}
prefix: /target/
service: {self.target.path.fqdn}
---
apiVersion: ambassador/v2
kind:  Mapping
name:  {self.target.path.k8s}-invalidservice
ambassador_id: {self.ambassador_id}
prefix: /target/invalidservice
service: {self.target.path.fqdn}-invalidservice
---
apiVersion: ambassador/v2
kind:  Mapping
name:  {self.target.path.k8s}-bypass
ambassador_id: {self.ambassador_id}
prefix: /bypass/
service: {self.target.path.fqdn}
bypass_error_response_overrides: true
'''

    def queries(self):
        # [0]
        yield Query(self.url("target/"), headers={"requested-status": "404"}, expected=404)
        # [1]
        yield Query(self.url("bypass/"), headers={"requested-status": "404"}, expected=404)
        # [2]
        yield Query(self.url("target/"), headers={"requested-status": "404"}, expected=404)

    def check(self):
        # [0]
        assert self.results[0].text == 'this is a custom 404 response', \
            f"unexpected response body: {self.results[0].text}"
        assert self.results[0].headers["Content-Type"] == ["text/custom"], \
            f"unexpected Content-Type: {self.results[0].headers}"

        # [1]
        assert self.results[1].text is None, \
            f"unexpected response body: {self.results[1].text}"

        # [2]
        assert self.results[2].text == 'this is a custom 404 response', \
            f"unexpected response body: {self.results[2].text}"
        assert self.results[2].headers["Content-Type"] == ["text/custom"], \
            f"unexpected Content-Type: {self.results[2].headers}"
