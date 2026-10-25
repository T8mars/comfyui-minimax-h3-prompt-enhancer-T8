"""Explicitly project only the two audited opt-in presentation additions."""
import ast
import copy

NAMES = ['color_style_config', 'creator_style_config']


def without_style_names(names):
    assert names[-2:] == NAMES, names[-2:]
    return names[:-2]


def without_style_signature(signature):
    parameters = list(signature.parameters.values())
    assert [p.name for p in parameters[-2:]] == NAMES
    assert all(p.default is None for p in parameters[-2:])
    return signature.replace(parameters=parameters[:-2])


def without_style_inputs(inputs):
    assert [v.id for v in inputs[-2:]] == NAMES
    assert all(v.optional and v.lazy for v in inputs[-2:])
    return inputs[:-2]


def project_style_ast(source):
    """Unrecognized changes survive this transform and still fail frozen gates."""
    class Projection(ast.NodeTransformer):
        def visit_ImportFrom(self, node):
            if node.module in ('visual_styles', 'visual_style_nodes') or (node.module is None and [v.name for v in node.names] == ['visual_styles']):
                return None
            return node

        def visit_Import(self, node):
            return None if [v.name for v in node.names] == ['visual_styles'] else node

        def visit_Try(self, node):
            if all(isinstance(v, ast.ImportFrom) and (v.module == 'visual_style_nodes' or v.module is None) for v in node.body):
                assert [v.names[0].name for v in node.body] == ['visual_styles', 'ColorStyleIO']
                return None
            return self.generic_visit(node)

        def visit_FunctionDef(self, node):
            if node.name == 'fingerprint_inputs':
                assert len(node.body) == 1 and isinstance(node.body[0], ast.Return)
                assert ast.unparse(node.body[0].value.func) == 'visual_styles.consumer_fingerprint'
                return None
            for field, defaults in (('args', 'defaults'), ('kwonlyargs', 'kw_defaults')):
                args, defs = getattr(node.args, field), getattr(node.args, defaults)
                if node.name != 'check_lazy_status' and [v.arg for v in args[-2:]] == NAMES:
                    assert all(ast.unparse(v) == 'None' for v in defs[-2:])
                    del args[-2:]; del defs[-2:]
            # Lazy uses the existing missing sentinel rather than a default None.
            if node.name == 'check_lazy_status':
                for name in reversed(NAMES):
                    assert node.args.args[-1].arg == name
                    assert ast.unparse(node.args.defaults[-1]) == '_SPEECH_MISSING'
                    node.args.args.pop(); node.args.defaults.pop()
            return self.generic_visit(node)

        def visit_Assign(self, node):
            if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                name = node.targets[0].id
                if name in NAMES or name == 'style_rule':
                    assert isinstance(node.value, ast.Call) and ast.unparse(node.value.func) in (
                        'visual_styles.resolve_color_style', 'visual_styles.resolve_creator_style', 'visual_styles.visual_style_instruction')
                    return None
                if name == 'messages' and isinstance(node.value, ast.Call) and ast.unparse(node.value.func) == 'visual_styles.preserve_visual_styles_on_repair':
                    assert ast.unparse(node.value.args[0]) == 'messages'
                    return None
            return self.generic_visit(node)

        def visit_If(self, node):
            if ast.unparse(node.test) == 'style_rule':
                assert ast.unparse(node.body[0]) == 'system_rules.append(style_rule)'
                return None
            return self.generic_visit(node)

        def visit_Expr(self, node):
            if isinstance(node.value, ast.Call) and ast.unparse(node.value.func) == 'metadata.update' and node.value.args and isinstance(node.value.args[0], ast.Call) and ast.unparse(node.value.args[0].func) == 'visual_styles.style_metadata':
                return None
            return self.generic_visit(node)

        def visit_Call(self, node):
            if ast.unparse(node.func) == 'visual_styles.preserve_visual_styles_on_repair':
                return self.visit(node.args[0])
            node.keywords = [k for k in node.keywords if k.arg not in NAMES and not (
                k.arg is None and isinstance(k.value, ast.Call) and ast.unparse(k.value.func) == 'visual_styles.active_config_kwargs')]
            for kw in node.keywords:
                if kw.arg == 'inputs' and isinstance(kw.value, ast.List):
                    for name, constructor in reversed(list(zip(NAMES, ['ColorStyleIO.Input', 'CreatorStyleIO.Input']))):
                        last = kw.value.elts[-1]
                        assert isinstance(last, ast.Call) and ast.unparse(last.func) == constructor
                        assert ast.literal_eval(last.args[0]) == name
                        options = {k.arg: k.value for k in last.keywords}
                        assert ast.literal_eval(options['optional']) and ast.literal_eval(options['lazy'])
                        kw.value.elts.pop()
            return self.generic_visit(node)

        def visit_BinOp(self, node):
            if isinstance(node.op, ast.Add) and isinstance(node.right, ast.IfExp):
                right = node.right
                if isinstance(right.body, ast.List) and len(right.body.elts) == 1 and isinstance(right.body.elts[0], ast.Constant) and right.body.elts[0].value in NAMES:
                    name = right.body.elts[0].value
                    assert ast.unparse(right.test) == name + ' is None' and ast.unparse(right.orelse) == '[]'
                    return self.visit(node.left)
            return self.generic_visit(node)

    tree = copy.deepcopy(ast.parse(source))
    return Projection().visit(tree)
