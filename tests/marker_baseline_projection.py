"""Project only the reviewed active H3 marker quality hook from frozen gates."""
import ast


def project_marker_quality_hooks(tree):
    found = []
    forwarded = 0
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) or node.name not in {"h3_quality_result", "_checked_h3_quality_result"}:
            continue
        if node.args.kwonlyargs[-1].arg != "extra_contract" or ast.literal_eval(node.args.kw_defaults[-1]) is not None:
            raise AssertionError("Marker hook must be the final internal None default")
        node.args.kwonlyargs.pop(); node.args.kw_defaults.pop()
        found.append(node.name)
        for call in ast.walk(node):
            if not isinstance(call, ast.Call): continue
            for keyword in list(call.keywords):
                if keyword.arg == "extra_contract":
                    if (node.name != "h3_quality_result" or not isinstance(call.func, ast.Name)
                            or call.func.id != "_checked_h3_quality_result" or ast.unparse(keyword.value) != "extra_contract"):
                        raise AssertionError("Marker hook forwarding changed")
                    call.keywords.remove(keyword)
                    forwarded += 1
            if node.name != "_checked_h3_quality_result" or not isinstance(call.func, ast.Name) or call.func.id != "run_quality": continue
            for keyword in call.keywords:
                if keyword.arg == "check" and isinstance(keyword.value, ast.Lambda):
                    value = keyword.value.body
                    expected = ast.parse("extra_contract.quality_report(text, check_h3(text, **options)) if extra_contract is not None else check_h3(text, **options)", mode="eval").body
                    if ast.dump(value) != ast.dump(expected): raise AssertionError("Only exact opt-in marker checker may be projected")
                    keyword.value.body = value.orelse
                if keyword.arg is None and isinstance(keyword.value, ast.IfExp) and ast.unparse(keyword.value.test) == "extra_contract is not None":
                    expected = ast.parse("{'accept': lambda old,new,before,after: extra_contract.accept_candidate(old,new,before,after,protect_generated_vocals=drama)} if extra_contract is not None else {'accept': lambda old,new,before,after: accept_correction(old,new,before,after,protect_generated_vocals=True)} if drama else {}", mode="eval").body
                    if ast.dump(keyword.value) != ast.dump(expected): raise AssertionError("Only exact additive marker acceptance may be projected")
                    keyword.value = keyword.value.orelse
    if set(found) != {"h3_quality_result", "_checked_h3_quality_result"} or forwarded != 1:
        raise AssertionError("Both H3 internal hooks must remain explicit")
    return tree
