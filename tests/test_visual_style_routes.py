"""Owned loopback HTTP boundaries; never contact a user server or model."""
import importlib
import types
import unittest
from unittest.mock import patch

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from test_directional_skills import h3

routes = importlib.import_module(h3.__package__ + '.visual_style_routes')


class VisualStyleRouteTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        table = web.RouteTableDef()
        fake = types.SimpleNamespace(PromptServer=types.SimpleNamespace(instance=types.SimpleNamespace(routes=table)))
        with patch.dict('sys.modules', server=fake), patch.object(routes, '_REGISTERED', False):
            self.assertTrue(routes.register_visual_style_routes())
            self.assertTrue(routes.register_visual_style_routes())
        app = web.Application()
        app.add_routes(table)
        self.client = TestClient(TestServer(app))
        await self.client.start_server()
        self.addAsyncCleanup(self.client.close)

    async def test_read_only_catalog_detail_and_invalid_ids(self):
        base = '/t8-prompt-enhancer/visual-styles/'
        response = await self.client.get(base + 'catalog')
        self.assertEqual(response.status, 200)
        self.assertEqual(len((await response.json())['entries']), 200)
        for kind in ('color', 'creator'):
            response = await self.client.get(base + kind + '/001')
            self.assertEqual(response.status, 200)
            self.assertEqual((await response.json())['model_calls'], 0)
        for path in ('color/999', 'PRIVATE/001', 'creator/PRIVATE'):
            response = await self.client.get(base + path)
            self.assertEqual(response.status, 400)
            self.assertEqual(response.headers['Cache-Control'], 'no-store')
            self.assertNotIn('PRIVATE', await response.text())
        self.assertEqual((await self.client.post(base + 'catalog')).status, 405)

    async def test_foreign_and_malformed_origin_are_forbidden_not_internal_errors(self):
        local_origin = str(self.client.make_url('/')).rstrip('/')
        response = await self.client.get('/t8-prompt-enhancer/visual-styles/catalog', headers={'Origin': local_origin})
        self.assertEqual(response.status, 200)
        for origin in ('https://evil.invalid', 'http://[', 'http://[not-an-ipv6]',
                       local_origin.replace('http:', 'https:'), local_origin.replace('http:', 'ftp:'),
                       local_origin + '/path', local_origin + '?query', local_origin + '#fragment'):
            with self.subTest(origin=origin):
                response = await self.client.get('/t8-prompt-enhancer/visual-styles/catalog', headers={'Origin': origin})
                self.assertEqual(response.status, 403)
                self.assertEqual(response.headers['Cache-Control'], 'no-store')
                self.assertNotIn(origin, await response.text())


if __name__ == '__main__':
    unittest.main()
