"""Apply only the reviewed target-ceiling fix to historical expected baselines."""


def allow_h3_target_ceiling_fix(source):
    if isinstance(source, bytes):
        source = source.decode("utf-8")
    source = source.replace("\r\n", "\n")
    for before, after, count in (
        ("not 80 <= int(description_word_target) <= 1000", "int(description_word_target) < 80", 1),
        ("description_word_target must be 0 (auto) or between 80 and 1000.",
         "description_word_target must be 0 (auto) or an integer of at least 80.", 2),
        ("                    max=1000,\n", "                    max=9_007_199_254_740_991,\n", 1),
    ):
        if source.count(before) != count:
            raise AssertionError(f"Historical H3 target clause changed: {before}")
        source = source.replace(before, after)
    return source


def allow_h3_target_widget_range(inputs):
    values = [item.as_dict() for item in inputs]
    indices = [i for i, item in enumerate(inputs) if item.id == "description_word_target"]
    if len(indices) != 1 or values[indices[0]].get("max") != 1000:
        raise AssertionError("Historical H3 target maximum must be exactly 1000")
    values[indices[0]]["max"] = 9_007_199_254_740_991
    return values
