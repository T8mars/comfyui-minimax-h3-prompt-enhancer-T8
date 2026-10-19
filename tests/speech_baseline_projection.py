"""Project only exact reviewed opt-in speech additions from frozen old gates."""
import ast
import copy


def project_speech_signature(arguments):
    args = copy.deepcopy(arguments)
    if args.args and args.args[-1].arg == "visual_marker_config":
        if not isinstance(args.defaults[-1], ast.Constant) or args.defaults[-1].value is not None:
            raise AssertionError("Visual marker default must remain None")
        args.args.pop(); args.defaults.pop()
    if not args.args or args.args[-1].arg != "storyboard_director_config":
        raise AssertionError("Storyboard must be the final optional argument")
    if not isinstance(args.defaults[-1], ast.Constant) or args.defaults[-1].value is not None:
        raise AssertionError("Storyboard default must remain None")
    args.args.pop(); args.defaults.pop()
    if not args.args or args.args[-1].arg != "speech_reference":
        raise AssertionError("Speech must be the final optional argument")
    if not args.defaults or not isinstance(args.defaults[-1], ast.Constant) or args.defaults[-1].value is not None:
        raise AssertionError("Speech execute default must remain None")
    args.args.pop(); args.defaults.pop()
    return args


def project_speech_schema(method):
    method = copy.deepcopy(method)
    found = 0
    for call in ast.walk(method):
        if not isinstance(call, ast.Call):
            continue
        for keyword in call.keywords:
            if keyword.arg != "inputs" or not isinstance(keyword.value, ast.List):
                continue
            values = keyword.value.elts
            if values and isinstance(values[-1], ast.Call) and ast.unparse(values[-1].func) == "VisualMarkerConfigIO.Input":
                marker = values[-1]
                if len(marker.args) != 1 or ast.literal_eval(marker.args[0]) != "visual_marker_config":
                    raise AssertionError("Unexpected visual marker input")
                options = {item.arg: item.value for item in marker.keywords}
                if ast.literal_eval(options["optional"]) is not True or ast.literal_eval(options["lazy"]) is not True:
                    raise AssertionError("Visual marker must stay optional and lazy")
                values.pop()
            if not values or not isinstance(values[-1], ast.Call) or ast.unparse(values[-1].func) != "T8StoryboardDirectorConfigIO.Input":
                raise AssertionError("Storyboard schema input must be appended after speech")
            storyboard = values[-1]
            if not storyboard.args or ast.literal_eval(storyboard.args[0]) != "storyboard_director_config":
                raise AssertionError("Unexpected storyboard input ID")
            options = {item.arg: item.value for item in storyboard.keywords}
            if ast.literal_eval(options["optional"]) is not True or ast.literal_eval(options["lazy"]) is not True:
                raise AssertionError("Storyboard must stay optional and lazy")
            values.pop()
            if not values or not isinstance(values[-1], ast.Call) or ast.unparse(values[-1].func) != "SpeechReferenceIO.Input":
                raise AssertionError("Speech schema input must be appended")
            speech = values[-1]
            if not speech.args or ast.literal_eval(speech.args[0]) != "speech_reference":
                raise AssertionError("Unexpected speech input ID")
            options = {item.arg: item.value for item in speech.keywords}
            if ast.literal_eval(options["optional"]) is not True or ast.literal_eval(options["lazy"]) is not True:
                raise AssertionError("Speech must stay optional and lazy")
            values.pop(); found += 1
    if found != 1:
        raise AssertionError("Expected exactly one appended speech socket")
    return method


def project_seedance_speech_quality(method):
    """Remove the reviewed active-only adapter, not arbitrary function changes."""
    method = copy.deepcopy(method)
    if method.name != "seedance_quality_result" or method.args.kwonlyargs[-1].arg != "speech_reference":
        raise AssertionError("Unexpected speech quality adapter signature")
    default = method.args.kw_defaults[-1]
    if not isinstance(default, ast.Constant) or default.value is not None:
        raise AssertionError("Inactive speech quality default must remain None")
    branch = ast.parse('''
if speech_reference is not None:
    try:
        from .speech_output import check_speech_seedance
    except ImportError:
        from speech_output import check_speech_seedance
    checker = check_speech_seedance
else:
    checker = check_seedance
''').body[0]
    if ast.dump(method.body[0]) != ast.dump(branch):
        raise AssertionError("Only the exact opt-in speech checker branch may change")
    method.body.pop(0)
    method.args.kwonlyargs.pop(); method.args.kw_defaults.pop()
    calls = [call for call in ast.walk(method) if isinstance(call, ast.Call)
             and isinstance(call.func, ast.Name) and call.func.id == "checker"]
    if len(calls) != 1:
        raise AssertionError("Expected exactly one selected Seedance checker call")
    call = calls[0]
    expected = ast.parse("checker(text, language=language, source=source, shot_count=shot_count)", mode="eval").body
    if ast.dump(call) != ast.dump(expected):
        raise AssertionError("Speech adapter must retain every original checker argument")
    call.func.id = "check_seedance"
    return method
