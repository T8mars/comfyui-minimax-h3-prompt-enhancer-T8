"""Three independent, default-Off, single-enhancer style examples."""
import argparse
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from visual_styles import load_catalog, selection_label, OFF, COLOR_ONLY
from build_directional_skill_workflows import generate as originals
from build_example_workflows import _workflow, _socket, _show_text_node

STEMS = ('visual_style_color_h3', 'visual_style_creator_seedance20', 'visual_style_combined_h3')
PROMPT = ('60秒，一个连续镜头。成年女子穿红色外套，右手拿车票，沿车站既有通道向前走。'
          '她持续移动，结尾仍在通道中；无对白、无新增人物、无字幕，不新增道具。'
          '保留红色外套与自然肤色，不改变动作、镜头数和结束状态。')


def generate():
    source = originals()
    catalog = {row['id']: row for row in load_catalog()[0]['entries']}
    result = {}
    for stem in STEMS:
        target = 'seedance20' if stem.endswith('seedance20') else 'h3'
        template = source['directional_zhenzhen_pov_' + target]
        key = copy.deepcopy(template['nodes'][0]); key['id'] = 1; key['outputs'][0]['links'] = [1]
        main = copy.deepcopy(next(n for n in template['nodes'] if n['type'].endswith('PromptEnhancerT8')))
        main.update(id=2, pos=[520, 60], title='仅一个增强器 / One enhancer · ' + target)
        main['widgets_values'][0] = PROMPT
        main['widgets_values'][2 if target == 'h3' else 3] = 60 if target == 'h3' else '60'
        main['widgets_values'][3 if target == 'h3' else 4] = '1'
        main['widgets_values'][35:] = ['none', 'off', 'off']
        for inp in main['inputs']: inp['link'] = 1 if inp['name'] == 'api_key' else None
        for output in main['outputs']: output['links'] = None
        main['outputs'][0]['links'] = [2]
        main['inputs'].extend([_socket('combat_camera_config', 'T8_COMBAT_CAMERA_CONFIG', None),
            _socket('speech_reference', 'T8_SPEECH_REFERENCE', None),
            _socket('storyboard_director_config', 'T8_STORYBOARD_DIRECTOR_CONFIG', None)])
        if target == 'h3': main['inputs'].append(_socket('visual_marker_config', 'T8_H3_VISUAL_MARKER_CONFIG', None))
        for kind in ('color', 'creator'): main['inputs'].append(_socket(kind + '_style_config', f'T8_{kind.upper()}_STYLE_CONFIG', None))
        show = _show_text_node(3, 2, [1180, 100]); show['title'] = '原生提示词结果 / Native prompt'
        nodes, links = [key, main, show], [[1, 1, 0, 2, 4, 'STRING'], [2, 2, 0, 3, 0, 'STRING']]
        kinds = ['color', 'creator'] if 'combined' in stem else ['creator' if target == 'seedance20' else 'color']
        for i, kind in enumerate(kinds):
            nid, lid = 4 + i, 3 + i
            cls = 'T8ColorStyleConfig' if kind == 'color' else 'T8CreatorStyleConfig'
            values = [OFF, selection_label(catalog['022' if kind == 'color' else '181'])]
            if kind == 'color': values.append(COLOR_ONLY)
            sock = next(j for j, v in enumerate(main['inputs']) if v['name'] == kind + '_style_config')
            main['inputs'][sock]['link'] = lid
            custom_type = f'T8_{kind.upper()}_STYLE_CONFIG'
            nodes.append({'id': nid, 'type': cls, 'title': '先预览，再开启 On / Preview then enable',
                'pos': [0, 400 + i * 280], 'size': [480, 220], 'flags': {}, 'order': 0, 'mode': 0,
                'inputs': [], 'outputs': [{'name': kind + '_style_config', 'type': custom_type, 'links': [lid]}],
                'properties': {'Node name for S&R': cls}, 'widgets_values': values})
            links.append([lid, nid, 0, 2, sock, custom_type])
        nodes.append({'id': 6, 'type': 'Note', 'pos': [1180, 560], 'size': [480, 340], 'flags': {}, 'order': 0, 'mode': 0,
            'properties': {}, 'widgets_values': ['操作：1.填写你的LLM渠道/API Key；2.点“浏览风格与帮助”；3.选择风格后将配置节点切为开启 / On；4.运行。\n两个入口独立；导演不会自动带入色彩。默认Off用于安全试用。\n每例只有1个增强器，不自动运行两路付费对照。色卡不是LUT，不修改输入图；实验建议不代表真实成片效果。\nConfigure your provider/key, browse, select, enable On, then queue. One enhancer only. Color and creator choices are independent.']})
        result[stem] = _workflow(stem, nodes, links)
    return result


def check():
    for stem, expected in generate().items():
        actual = json.loads((ROOT / 'example_workflows' / (stem + '.json')).read_text(encoding='utf-8'))
        assert actual == expected, stem
        nodes = {n['id']: n for n in actual['nodes']}
        assert nodes[1]['widgets_values'] == ['']
        assert len(nodes[2]['widgets_values']) == 38
        assert sum(n['type'].endswith('PromptEnhancerT8') for n in nodes.values()) == 1
        for lid, src, out, dst, inp, kind in actual['links']:
            assert nodes[src]['outputs'][out]['type'] == nodes[dst]['inputs'][inp]['type'] == kind
            assert lid in nodes[src]['outputs'][out]['links'] and nodes[dst]['inputs'][inp]['link'] == lid
    print('Visual styles: 3 independent default-Off examples, blank keys, stable 38 controls.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--check', action='store_true')
    if parser.parse_args().check: check()
    else:
        from generate_workflow_thumbnails import make_card
        for stem, workflow in generate().items():
            (ROOT / 'example_workflows' / (stem + '.json')).write_text(json.dumps(workflow, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
            make_card('色彩 / 导演 · 独立入口', stem.replace('visual_style_', ''), (74, 108, 122)).save(
                ROOT / 'example_workflows' / (stem + '.jpg'), 'JPEG', quality=88, optimize=True, progressive=True)
