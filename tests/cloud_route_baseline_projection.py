"""Permit only the reviewed cloud route fix in otherwise frozen node sources."""
import ast


OLD_DOC = """Try an explicit direct route before falling back to the environment.

    Seedance.nz users frequently inherit an unavailable system proxy. The first
    attempt therefore bypasses it. A safe pre-connection retry may use the
    environment route. Custom OpenAI-compatible endpoints never inherit this
    Seedance.nz-only policy.
    """
NEW_DOC = """Prefer an explicit proxy environment; otherwise keep legacy direct-first.

    Requests resolves HTTPS_PROXY/ALL_PROXY, lowercase variants and NO_PROXY.
    System-only proxies retain direct-first for existing desktop workflows.
    Safe retries alternate routes within the original bounded attempt budget.
    Other providers never inherit this Seedance.nz-only routing policy.
    """
ORIGINAL_ROUTE = '''def _seedance_request_route_kwargs(
    url: str,
    attempt: int,
    enabled: bool,
) -> dict[str, dict[str, str]]:
    """''' + OLD_DOC + '''"""
    if not enabled:
        return {}
    index = max(int(attempt) - 1, 0) % len(SEEDANCE_ROUTE_SEQUENCE)
    route = SEEDANCE_ROUTE_SEQUENCE[index]
    if route == "direct":
        return {"proxies": dict(DIRECT_ROUTE_PROXIES)}
    return {"proxies": requests.utils.get_environ_proxies(url)}
'''
APPROVED_ROUTE = ORIGINAL_ROUTE.replace(OLD_DOC, NEW_DOC).replace(
    '    route = SEEDANCE_ROUTE_SEQUENCE[index]\n',
    '    route = SEEDANCE_ROUTE_SEQUENCE[index]\n'
    '    if seedance_prefers_environment_proxy(url):\n'
    '        route = SEEDANCE_ROUTE_SEQUENCE[(index + 1) % len(SEEDANCE_ROUTE_SEQUENCE)]\n')


def project_cloud_route_ast(tree):
    """Do not erase other function bodies, schemas, imports or unknown changes."""
    original, approved = (ast.parse(text).body[0] for text in (ORIGINAL_ROUTE, APPROVED_ROUTE))
    guard = ast.parse('if seedance_preconnect_failure(error):\n    return True').body[0]
    predicate = ast.parse('not seedance_preconnect_failure(error)', mode='eval').body
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == 'provider_transport':
            if [(v.name, v.asname) for v in node.names] == [
                ('request_chat_completion', None), ('seedance_prefers_environment_proxy', None),
                ('seedance_preconnect_failure', None)]:
                node.names = node.names[:1]
        if not isinstance(node, ast.FunctionDef):
            continue
        if node.name == '_seedance_request_route_kwargs':
            if ast.dump(node) == ast.dump(original):
                continue
            assert ast.dump(node) == ast.dump(approved), 'Unreviewed cloud route function change'
            node.body = original.body
        elif node.name == '_is_retryable_seedance_network_error':
            if node.body and ast.dump(node.body[0]) == ast.dump(guard):
                node.body.pop(0)
        elif node.name == '_is_ambiguous_seedance_network_error':
            if len(node.body) == 1 and isinstance(node.body[0], ast.Return):
                value = node.body[0].value
                if isinstance(value, ast.BoolOp) and isinstance(value.op, ast.And) and len(value.values) == 3:
                    if ast.dump(value.values[-1]) == ast.dump(predicate):
                        value.values.pop()
    return tree
