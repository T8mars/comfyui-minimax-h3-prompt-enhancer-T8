"""Cloud proxy routing without external requests or paid generation."""
import os
import ast
import unittest
from unittest.mock import patch

import requests
from urllib3.exceptions import MaxRetryError, NewConnectionError, ProxyError as PoolProxyError

from test_nodes import nodes, FakeResponse, SequencedChatSession
from cloud_route_baseline_projection import ORIGINAL_ROUTE, APPROVED_ROUTE, project_cloud_route_ast


def connect_failure(*, proxy=False):
    reason = NewConnectionError(None, "test connection was never established")
    if proxy:
        reason = PoolProxyError("test proxy unreachable", reason)
    wrapped = MaxRetryError(None, "/v1/chat/completions", reason)
    return (requests.exceptions.ProxyError if proxy else requests.exceptions.ConnectionError)(wrapped)


class CloudProxyTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_explicit_https_proxy_is_used_before_direct_for_upload_and_chat(self):
        proxy = "http://127.0.0.1:18765"
        with patch.dict(os.environ, {"HTTPS_PROXY": proxy}):
            for url in (nodes.UPLOAD_URL, nodes.CHAT_COMPLETIONS_URL):
                self.assertEqual(nodes._seedance_request_route_kwargs(url, 1, True)["proxies"]["https"], proxy)
                self.assertEqual(nodes._seedance_request_route_kwargs(url, 2, True)["proxies"], nodes.DIRECT_ROUTE_PROXIES)
                self.assertEqual(nodes._seedance_request_route_kwargs(url, 3, True)["proxies"]["https"], proxy)

    def test_no_proxy_bypass_and_lowercase_precedence_follow_requests(self):
        for bypass in ("api.seedance.nz", "*", "api.seedance.nz:443"):
            with self.subTest(bypass=bypass), patch.dict(os.environ, {"HTTPS_PROXY": "http://127.0.0.1:18765", "NO_PROXY": bypass}):
                url = "https://api.seedance.nz:443/v1/files/upload"
                self.assertEqual(nodes._seedance_request_route_kwargs(url, 1, True)["proxies"], nodes.DIRECT_ROUTE_PROXIES)
        with patch.dict(os.environ, {"HTTPS_PROXY": "http://upper.invalid:1", "https_proxy": "http://lower.invalid:2"}):
            self.assertEqual(nodes._seedance_request_route_kwargs(nodes.UPLOAD_URL, 1, True)["proxies"]["https"], "http://lower.invalid:2")
        with patch.dict(os.environ, {"ALL_PROXY": "http://all.invalid:3"}):
            self.assertEqual(nodes._seedance_request_route_kwargs(nodes.UPLOAD_URL, 1, True)["proxies"]["all"], "http://all.invalid:3")

    def test_no_explicit_environment_keeps_legacy_direct_first_even_with_system_proxy(self):
        system = {"https": "http://system.invalid:1"}
        with patch.object(requests.utils, "get_environ_proxies", return_value=system):
            self.assertEqual(nodes._seedance_request_route_kwargs(nodes.UPLOAD_URL, 1, True)["proxies"], nodes.DIRECT_ROUTE_PROXIES)
            self.assertEqual(nodes._seedance_request_route_kwargs(nodes.UPLOAD_URL, 2, True)["proxies"], system)

    def test_other_endpoints_are_not_assigned_seedance_routing(self):
        with patch.object(requests.utils, "get_environ_proxies", side_effect=AssertionError("must not override other providers")):
            self.assertEqual(nodes._seedance_request_route_kwargs("https://custom.invalid/v1/chat/completions", 1, False), {})

    def test_frozen_gate_allows_only_the_reviewed_route_body(self):
        self.assertEqual(ast.dump(project_cloud_route_ast(ast.parse(APPROVED_ROUTE))), ast.dump(ast.parse(ORIGINAL_ROUTE)))
        for altered in (APPROVED_ROUTE.replace('index + 1', 'index + 2'), APPROVED_ROUTE.replace('return {}', 'return None')):
            with self.assertRaisesRegex(AssertionError, 'Unreviewed'):
                project_cloud_route_ast(ast.parse(altered))

    def test_only_typed_preconnection_failures_gain_safe_retry(self):
        for proxy in (False, True):
            failure = connect_failure(proxy=proxy)
            self.assertTrue(nodes._is_retryable_seedance_network_error(failure))
            self.assertFalse(nodes._is_ambiguous_seedance_network_error(failure))
        for kind in (requests.exceptions.ConnectionError, requests.exceptions.ProxyError,
                     requests.exceptions.ReadTimeout, requests.exceptions.ChunkedEncodingError):
            failure = kind("test request may already have been accepted")
            self.assertFalse(nodes._is_retryable_seedance_network_error(failure))
            self.assertTrue(nodes._is_ambiguous_seedance_network_error(failure))

    def test_upload_can_switch_route_after_confirmed_connect_failure(self):
        class Session:
            calls = []
            def post(self, url, **kwargs):
                self.calls.append(kwargs)
                if len(self.calls) == 1:
                    raise connect_failure()
                return FakeResponse(200, {"url": "https://assets.example/test.png"})
        session = Session()
        proxy = {"https": "http://127.0.0.1:18765"}
        with patch.object(requests.utils, "get_environ_proxies", return_value=proxy), patch.object(nodes.time, "sleep"):
            self.assertEqual(nodes._upload_media(session, "test-placeholder", b"image", "test.png", "image/png"), "https://assets.example/test.png")
        self.assertEqual([v["proxies"] for v in session.calls], [nodes.DIRECT_ROUTE_PROXIES, proxy])

    def test_unreachable_explicit_proxy_can_fall_back_before_any_paid_post(self):
        session = SequencedChatSession([connect_failure(proxy=True), FakeResponse(200, {"choices": [{"message": {"content": "test result"}}]})])
        proxy = "http://127.0.0.1:18765"
        with patch.dict(os.environ, {"HTTPS_PROXY": proxy}), patch.object(nodes.time, "sleep"):
            result = nodes._request_completion(session, "test-placeholder", [{"role": "user", "content": "test"}], "balanced")
        self.assertEqual(result, "test result")
        self.assertEqual(len(session.chat_requests), 2)
        self.assertEqual(session.chat_requests[0]["proxies"]["https"], proxy)
        self.assertEqual(session.chat_requests[1]["proxies"], nodes.DIRECT_ROUTE_PROXIES)


if __name__ == "__main__":
    unittest.main()
