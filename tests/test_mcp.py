import importlib.util
import sys
import unittest


@unittest.skipUnless(importlib.util.find_spec('mcp'), 'Install .[solidworks] for protocol integration tests')
class McpTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_stdio_handshake_schemas_success_and_tool_error(self):
        from anyio import fail_after
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        parameters = StdioServerParameters(command=sys.executable, args=['-m', 'tests.mcp_fixture'])
        with fail_after(20):
            async with stdio_client(parameters) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = (await session.list_tools()).tools
                    self.assertEqual(len(tools), 13)
                    self.assertFalse(any('script' in tool.name or 'save' in tool.name for tool in tools))
                    doc = await session.call_tool('sw_active_document')
                    self.assertFalse(doc.isError)
                    token = doc.structuredContent['data']['document_token']
                    display = await session.call_tool('sw_get_display_state')
                    self.assertTrue(display.structuredContent['data']['visibility']['planes'])
                    hidden = await session.call_tool('sw_set_display_visibility', {
                        'expected_document_token': token, 'target': 'planes', 'visible': False})
                    self.assertFalse(hidden.isError)
                    self.assertFalse(hidden.structuredContent['data']['visible'])
                    display = await session.call_tool('sw_get_display_state')
                    self.assertFalse(display.structuredContent['data']['visibility']['planes'])
                    for name, extra in [('sw_zoom_to_fit', {}),
                                        ('sw_get_component_visibility', {'occurrence_path': 'rail-2'}),
                                        ('sw_set_component_visibility', {'occurrence_path': 'rail-2', 'visible': False})]:
                        result = await session.call_tool(name, {'expected_document_token': token, **extra})
                        self.assertFalse(result.isError, result)
                    selection = await session.call_tool('sw_select_component', {'expected_document_token': token, 'occurrence_path': 'rail-2'})
                    self.assertFalse(selection.isError)
                    self.assertEqual(selection.structuredContent['data']['selected_count'], 1)
                    bad = await session.call_tool('sw_rebuild', {'expected_document_token': '0' * 24})
                    self.assertTrue(bad.isError)
                    self.assertEqual(bad.structuredContent['errors'][0]['code'], 'DOCUMENT_CHANGED')
                    bad = await session.call_tool('sw_component_tree', {'max_depth': 0})
                    self.assertTrue(bad.isError)
                    bad = await session.call_tool('not_a_tool')
                    self.assertTrue(bad.isError)

    @unittest.skipIf(sys.platform == 'win32', 'Non-Windows failure-path test')
    async def test_production_server_reports_platform_error_without_mock_fallback(self):
        from anyio import fail_after
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        parameters = StdioServerParameters(command=sys.executable, args=['-m', 'cadkin.mcp_server'])
        with fail_after(20):
            async with stdio_client(parameters) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool('sw_session_status')
                    self.assertTrue(result.isError)
                    self.assertEqual(result.structuredContent['errors'][0]['code'], 'UNSUPPORTED_PLATFORM')
