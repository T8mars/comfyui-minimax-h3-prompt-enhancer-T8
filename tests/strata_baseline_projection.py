"""Exact, opt-in additions allowed by the pre-Strata frozen gates.

Old branches, inputs, widgets, examples and execute signatures remain compared.
The new branch behavior is tested separately over real isolated HTTP/VIDEO.
"""
import ast
import copy

GUARDS = {
    "_provider_config": "is_strata_mode(api_mode)",
    "_resolve_llm_model": "is_strata_mode(api_mode)",
    "_video_duration": "current_strata_run() is not None",
    "_validate_video_source": "current_strata_run() is not None",
    "_validate_hybrid_video_payload": "current_strata_run() is not None",
    "_request_completion": "chat_url == STRATA_CHAT_URL",
    "build_provider_config": "provider == PROVIDER_STRATA",
    "merge_provider_config": "provider == PROVIDER_STRATA",
}

def project_strata_guard(function):
    result = copy.deepcopy(function)
    test = GUARDS.get(function.name)
    if test:
        matches = [node for node in result.body if isinstance(node, ast.If) and ast.unparse(node.test) == test]
        if len(matches) != 1 or not any(isinstance(node, ast.Return) for node in ast.walk(matches[0])):
            raise AssertionError("Unexpected Strata guard projection: " + function.name)
        result.body.remove(matches[0])
    result.decorator_list = [node for node in result.decorator_list if ast.unparse(node) != "strata_execution"]
    return result

def project_strata_ui(text):
    # Only append the new provider option to the old mode recognizer.
    return text.replace(', "Strata 本地服务（桥接）"', '')
