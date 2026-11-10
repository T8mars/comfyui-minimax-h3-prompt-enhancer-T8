"""Response ownership regressions at the actual H3 cloud transport boundary."""
import unittest
from unittest.mock import patch

import requests
from test_h3_image_node import h, Node, Response, Session, StreamResponse, reply


class TrackedResponse(Response):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.close_count = 0

    def close(self):
        self.close_count += 1


class ResponseCleanupTests(unittest.TestCase):
    def test_json_and_http_failure_exit_close_exactly_once_without_resending(self):
        class BadJSON(TrackedResponse):
            def json(self): raise ValueError("bad JSON")
        class MissingContent(TrackedResponse):
            def json(self): return {"choices": []}
        for response, error in ((TrackedResponse(reply()), False), (TrackedResponse(reply(), status=401), True),
                                (BadJSON(""), True), (MissingContent(""), True),
                                (TrackedResponse(reply(), finish="length"), True), (TrackedResponse(""), True)):
            with self.subTest(response=type(response).__name__, status=response.status_code):
                session = Session(response)
                with patch.object(h.requests, "Session", return_value=session):
                    if error:
                        with self.assertRaises(Exception): Node.execute(prompt="A cup.", api_key="test-placeholder")
                    else:
                        self.assertEqual(Node.execute(prompt="A cup.", api_key="test-placeholder").result[1], "4:3")
                self.assertEqual(response.close_count, 1)
                self.assertEqual(len(session.calls), 1)
                self.assertTrue(session.closed)

    def test_each_correction_response_is_closed_and_sse_keeps_one_close(self):
        a, b = TrackedResponse("bad"), TrackedResponse(reply())
        session = Session(a, b)
        with patch.object(h.requests, "Session", return_value=session):
            Node.execute(prompt="A cup.", api_key="test-placeholder")
        self.assertEqual((a.close_count, b.close_count), (1, 1))
        class TrackedStream(StreamResponse):
            def __init__(self, **kwargs): super().__init__(reply(), **kwargs); self.close_count = 0
            def close(self): self.close_count += 1
        for error in (None, requests.exceptions.ChunkedEncodingError("disconnect")):
            response = TrackedStream(error=error); session = Session(response)
            with patch.object(h.requests, "Session", return_value=session):
                Node.execute(prompt="A cup.", api_key="test-placeholder")
            self.assertEqual(response.close_count, 1)
            self.assertEqual(len(session.calls), 1)


if __name__ == "__main__": unittest.main()
