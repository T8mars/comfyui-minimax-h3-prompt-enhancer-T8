from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "example_workflows"

LOCAL_API_MODE = "本地 GGUF（llama.cpp / Qwen，离线）"
SEEDANCE_API_MODE = "贞贞平价小屋（推荐）"
LOCAL_MODEL = "Qwen3.8-27B-Q4_K_M.gguf"
LOCAL_MMPROJ = "AUTO（自动匹配）"
LOCAL_THINK = "关闭（推荐，速度优先）"
LOCAL_UNLOAD = "执行后卸载（推荐）"
LOCAL_MEMORY = "AUTO（显存不足时释放）"

H3_LOCAL_DEFAULTS = [LOCAL_MODEL, LOCAL_MMPROJ, 32768, 4096, LOCAL_THINK, "medium", 2.0, LOCAL_UNLOAD, LOCAL_MEMORY]
SEEDANCE_LOCAL_DEFAULTS = list(H3_LOCAL_DEFAULTS)
MUSIC_LOCAL_DEFAULTS = [LOCAL_MODEL, 32768, 4096, LOCAL_THINK, "medium", LOCAL_UNLOAD, LOCAL_MEMORY]

PROVIDER_WIDGETS = [
    # ComfyUI serializes required widgets before optional widgets.
    "Local Qwen", "AUTO（兼容策略）", LOCAL_MODEL, LOCAL_MMPROJ, 32768, 4096,
    LOCAL_THINK, "medium", 2.0, LOCAL_UNLOAD, LOCAL_MEMORY,
    "", "", "", "gemini-3.5-flash", "",
]


def _workflow_id(name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"https://github.com/T8mars/comfyui-minimax-h3-prompt-enhancer-T8/{name}"))


def _socket(name: str, socket_type: str, link: int | None, *, label: str | None = None) -> dict[str, Any]:
    value: dict[str, Any] = {"name": name, "shape": 7, "type": socket_type, "link": link}
    if label:
        value["label"] = label
    return value


def _provider_node(node_id: int, output_links: list[int], pos: list[float]) -> dict[str, Any]:
    return {
        "id": node_id,
        "type": "T8LLMProviderConfig",
        "pos": pos,
        "size": [440, 520],
        "flags": {},
        "order": 0,
        "mode": 0,
        "inputs": [],
        "outputs": [{"name": "provider_config", "type": "T8_LLM_PROVIDER_CONFIG", "links": output_links}],
        "properties": {"Node name for S&R": "T8LLMProviderConfig"},
        "widgets_values": list(PROVIDER_WIDGETS),
    }


def _h3_widgets(prompt: str, api_mode: str = LOCAL_API_MODE) -> list[Any]:
    return [
        prompt, "T2VA（文生音视频）", 15, "5", "balanced", 0, "中文", "官方增强",
        "现有兼容（保留中英文）", "无（仅核心规则）", "无（不使用 T8 案例）",
        api_mode, "gemini-3.5-flash", "", "", "", "", "", "", "", 0, "fixed",
        *H3_LOCAL_DEFAULTS,
    ]


def _seedance_widgets(prompt: str, api_mode: str = LOCAL_API_MODE) -> list[Any]:
    return [
        prompt, "AUTO（根据意图与素材判断）", "AUTO（自动判断）", "15", "5", "balanced",
        "AUTO（按内容判断）", "中文", "官方优化", "无（不使用 T8 案例）",
        "火山官方（@图片N/@视频N/@音频N）", "AUTO（按用户意图）", "AUTO（按场景添加）",
        api_mode, "gemini-3.5-flash", 0, "", "", "", "", "", "", "", "", 0, "fixed",
        *SEEDANCE_LOCAL_DEFAULTS,
    ]


def _music_widgets(prompt: str, api_mode: str = LOCAL_API_MODE) -> list[Any]:
    return [
        prompt, "生成新歌词（T8非官方）", "", "中文", 180, "balanced",
        "官方完整（2–4次请求，推荐）", "AUTO（按风格与时长）", 0, "AUTO",
        "English（官方默认）", 0, api_mode, "gemini-3.5-flash", 0, "fixed",
        "AUTO（从润色要求识别）", "Verse（主歌）", 0,
        "隐私隔离（不发送歌词给Caption阶段）", "开启（内存10分钟，推荐）",
        "", "", "不要直接模仿任何现有歌手或歌曲；副歌需要清晰且容易记忆的原创 hook。",
        "", "", "", "", "", "", "", *MUSIC_LOCAL_DEFAULTS,
    ]


def _h3_node(
    node_id: int,
    config_link: int | None,
    pos: list[float],
    *,
    prompt: str,
    output_links: list[int] | None = None,
    api_mode: str = LOCAL_API_MODE,
    api_key_link: int | None = None,
) -> dict[str, Any]:
    return {
        "id": node_id,
        "type": "MiniMaxH3PromptEnhancerT8",
        "pos": pos,
        "size": [620, 980],
        "flags": {},
        "order": 1,
        "mode": 0,
        "inputs": [
            _socket("first_frame", "IMAGE", None),
            _socket("last_frame", "IMAGE", None),
            _socket("reference_images.reference_image_0", "IMAGE", None, label="reference_image_0"),
            _socket("reference_videos.reference_video_0", "VIDEO", None, label="reference_video_0"),
            _socket("api_key", "STRING", api_key_link, label="API Key"),
            _socket("provider_config", "T8_LLM_PROVIDER_CONFIG", config_link, label="共享 LLM 渠道配置（可选）"),
        ],
        "outputs": [{"name": "enhanced_prompt", "type": "STRING", "links": output_links}],
        "properties": {"Node name for S&R": "MiniMaxH3PromptEnhancerT8"},
        "widgets_values": _h3_widgets(prompt, api_mode),
    }


def _seedance_node(
    node_id: int,
    config_link: int | None,
    pos: list[float],
    *,
    prompt: str,
    output_links: list[int] | None = None,
    api_mode: str = LOCAL_API_MODE,
    api_key_link: int | None = None,
) -> dict[str, Any]:
    return {
        "id": node_id,
        "type": "Seedance20PromptEnhancerT8",
        "pos": pos,
        "size": [620, 980],
        "flags": {},
        "order": 1,
        "mode": 0,
        "inputs": [
            _socket("first_frame", "IMAGE", None),
            _socket("last_frame", "IMAGE", None),
            _socket("reference_images.reference_image_0", "IMAGE", None, label="reference_image_0"),
            _socket("reference_videos.reference_video_0", "VIDEO", None, label="reference_video_0"),
            _socket("api_key", "STRING", api_key_link, label="提示词增强 LLM API Key"),
            _socket("provider_config", "T8_LLM_PROVIDER_CONFIG", config_link, label="共享 LLM 渠道配置（可选）"),
        ],
        "outputs": [{"name": "enhanced_prompt", "type": "STRING", "links": output_links}],
        "properties": {"Node name for S&R": "Seedance20PromptEnhancerT8"},
        "widgets_values": _seedance_widgets(prompt, api_mode),
    }


def _music_node(
    node_id: int,
    config_link: int | None,
    pos: list[float],
    *,
    prompt: str,
    lyrics_links: list[int] | None = None,
    caption_links: list[int] | None = None,
    api_mode: str = LOCAL_API_MODE,
    api_key_link: int | None = None,
) -> dict[str, Any]:
    return {
        "id": node_id,
        "type": "MiniMaxMusic3PromptEnhancerT8",
        "pos": pos,
        "size": [620, 940],
        "flags": {},
        "order": 1,
        "mode": 0,
        "inputs": [
            _socket("api_key", "STRING", api_key_link, label="LLM API Key"),
            _socket("provider_config", "T8_LLM_PROVIDER_CONFIG", config_link, label="共享 LLM 渠道配置（可选）"),
        ],
        "outputs": [
            {"name": "lyrics", "type": "STRING", "links": lyrics_links},
            {"name": "music_caption", "type": "STRING", "links": caption_links},
            {"name": "music3_payload_json", "type": "STRING", "links": None},
            {"name": "enhancement_report_json", "type": "STRING", "links": None},
        ],
        "properties": {"Node name for S&R": "MiniMaxMusic3PromptEnhancerT8"},
        "widgets_values": _music_widgets(prompt, api_mode),
    }


def _inspector_node(
    node_id: int,
    prompt_link: int,
    pos: list[float],
    *,
    warnings_links: list[int] | None = None,
    summary_links: list[int] | None = None,
) -> dict[str, Any]:
    return {
        "id": node_id,
        "type": "T8PromptInspector",
        "pos": pos,
        "size": [420, 360],
        "flags": {},
        "order": 2,
        "mode": 0,
        "inputs": [_socket("prompt", "STRING", prompt_link, label="待检查提示词")],
        "outputs": [
            {"name": "original_prompt", "type": "STRING", "links": None},
            {"name": "warnings_json", "type": "STRING", "links": warnings_links},
            {"name": "summary", "type": "STRING", "links": summary_links},
        ],
        "properties": {"Node name for S&R": "T8PromptInspector"},
        # Required widgets precede optional task_intent in ComfyUI's V1 order.
        "widgets_values": ["MiniMax H3", "5", "中文", "AUTO", 15, ""],
    }


def _prompt_text_node(
    node_id: int,
    output_links: list[int],
    pos: list[float],
    *,
    text: str,
    title: str | None = None,
) -> dict[str, Any]:
    node = {
        "id": node_id,
        "type": "T8PromptText",
        "pos": pos,
        "size": [420, 260],
        "flags": {},
        "order": 0,
        "mode": 0,
        "inputs": [],
        "outputs": [{"name": "text", "type": "STRING", "links": output_links}],
        "properties": {"Node name for S&R": "T8PromptText"},
        "widgets_values": [text],
    }
    if title:
        node["title"] = title
    return node


def _show_text_node(node_id: int, input_link: int, pos: list[float], *, order: int = 2) -> dict[str, Any]:
    return {
        "id": node_id,
        "type": "T8ShowText",
        "pos": pos,
        "size": [420, 300],
        "flags": {},
        "order": order,
        "mode": 0,
        "inputs": [_socket("text", "STRING", input_link, label="待显示文本")],
        "outputs": [{"name": "text", "type": "STRING", "links": None}],
        "properties": {"Node name for S&R": "T8ShowText"},
        "widgets_values": [],
    }


def _suite_node(
    node_id: int,
    node_type: str,
    pos: list[float],
    *,
    inputs: list[dict[str, Any]],
    outputs: list[tuple[str, str, list[int] | None]],
    widgets: list[Any],
    size: list[float] | None = None,
    order: int = 1,
) -> dict[str, Any]:
    return {
        "id": node_id,
        "type": node_type,
        "pos": pos,
        "size": size or [520, 520],
        "flags": {},
        "order": order,
        "mode": 0,
        "inputs": inputs,
        "outputs": [
            {"name": name, "type": socket_type, "links": links}
            for name, socket_type, links in outputs
        ],
        "properties": {"Node name for S&R": node_type},
        "widgets_values": widgets,
    }


def _workflow(name: str, nodes: list[dict[str, Any]], links: list[list[Any]]) -> dict[str, Any]:
    return {
        "id": _workflow_id(name),
        "revision": 0,
        "last_node_id": max(node["id"] for node in nodes),
        "last_link_id": max((link[0] for link in links), default=0),
        "nodes": nodes,
        "links": links,
        "groups": [],
        "config": {},
        "extra": {"ds": {"scale": 0.8, "offset": [80, 60]}},
        "version": 0.4,
    }


def _generated_workflows() -> dict[str, dict[str, Any]]:
    h3_prompt = "国风水墨竹林中，白衣剑客踏过浅水，镜头由低机位跟拍转为环绕，剑气掀起墨色涟漪，环境声与衣袂破风声清晰。"
    seedance_prompt = "15秒电影感追逐：雨夜霓虹街区，一名红衣女性穿过人群并跃上驶离的电车，保持人物服装、面部和空间方向一致。"
    music_prompt = "温暖的华语公路流行歌曲，女声由克制主歌走向明亮最终副歌，钢琴与原声吉他为核心，生成原创中文歌词。"
    return {
        "minimax_h3_prompt_enhancer_example": _workflow(
            "minimax_h3_prompt_enhancer_example",
            [
                _prompt_text_node(1, [1], [60, 260], text="", title="填写 API Key（保存工作流会包含明文）"),
                _h3_node(
                    2,
                    None,
                    [560, 60],
                    prompt=h3_prompt,
                    output_links=[2],
                    api_mode=SEEDANCE_API_MODE,
                    api_key_link=1,
                ),
                _show_text_node(3, 2, [1240, 300]),
            ],
            [[1, 1, 0, 2, 4, "STRING"], [2, 2, 0, 3, 0, "STRING"]],
        ),
        "seedance20_prompt_enhancer_example": _workflow(
            "seedance20_prompt_enhancer_example",
            [
                _prompt_text_node(1, [1], [60, 260], text="", title="填写 API Key（保存工作流会包含明文）"),
                _seedance_node(
                    2,
                    None,
                    [560, 60],
                    prompt=seedance_prompt,
                    output_links=[2],
                    api_mode=SEEDANCE_API_MODE,
                    api_key_link=1,
                ),
                _show_text_node(3, 2, [1240, 300]),
            ],
            [[1, 1, 0, 2, 4, "STRING"], [2, 2, 0, 3, 0, "STRING"]],
        ),
        "music3_prompt_lyrics_enhancer_example": _workflow(
            "music3_prompt_lyrics_enhancer_example",
            [
                _prompt_text_node(1, [1], [60, 260], text="", title="填写 API Key（保存工作流会包含明文）"),
                _music_node(
                    2,
                    None,
                    [560, 60],
                    prompt=music_prompt,
                    lyrics_links=[2],
                    caption_links=[3],
                    api_mode=SEEDANCE_API_MODE,
                    api_key_link=1,
                ),
                _show_text_node(3, 2, [1240, 100]),
                _show_text_node(4, 3, [1240, 440]),
            ],
            [[1, 1, 0, 2, 0, "STRING"], [2, 2, 0, 3, 0, "STRING"], [3, 2, 1, 4, 0, "STRING"]],
        ),
        "basic_workflow_multi_task_connections": _workflow(
            "basic_workflow_multi_task_connections",
            [
                _provider_node(1, [1, 2, 3], [40, 360]),
                _h3_node(2, 1, [540, 40], prompt=h3_prompt, output_links=[4]),
                _seedance_node(3, 2, [1220, 40], prompt=seedance_prompt, output_links=[5]),
                _music_node(4, 3, [1900, 40], prompt=music_prompt, lyrics_links=[6], caption_links=[7]),
                _show_text_node(5, 4, [540, 1080]),
                _show_text_node(6, 5, [1220, 1080]),
                _show_text_node(7, 6, [1900, 1020]),
                _show_text_node(8, 7, [2360, 1020]),
            ],
            [
                [1, 1, 0, 2, 5, "T8_LLM_PROVIDER_CONFIG"],
                [2, 1, 0, 3, 5, "T8_LLM_PROVIDER_CONFIG"],
                [3, 1, 0, 4, 1, "T8_LLM_PROVIDER_CONFIG"],
                [4, 2, 0, 5, 0, "STRING"],
                [5, 3, 0, 6, 0, "STRING"],
                [6, 4, 0, 7, 0, "STRING"],
                [7, 4, 1, 8, 0, "STRING"],
            ],
        ),
        "minimax_h3_local_qwen_example": _workflow(
            "minimax_h3_local_qwen_example",
            [
                _provider_node(1, [1], [60, 100]),
                _h3_node(2, 1, [580, 80], prompt=h3_prompt, output_links=[2]),
                _show_text_node(3, 2, [1260, 300]),
            ],
            [[1, 1, 0, 2, 5, "T8_LLM_PROVIDER_CONFIG"], [2, 2, 0, 3, 0, "STRING"]],
        ),
        "seedance20_local_qwen_example": _workflow(
            "seedance20_local_qwen_example",
            [
                _provider_node(1, [1], [60, 100]),
                _seedance_node(2, 1, [580, 80], prompt=seedance_prompt, output_links=[2]),
                _show_text_node(3, 2, [1260, 300]),
            ],
            [[1, 1, 0, 2, 5, "T8_LLM_PROVIDER_CONFIG"], [2, 2, 0, 3, 0, "STRING"]],
        ),
        "music3_local_qwen_example": _workflow(
            "music3_local_qwen_example",
            [
                _provider_node(1, [1], [60, 100]),
                _music_node(2, 1, [580, 80], prompt=music_prompt, lyrics_links=[2], caption_links=[3]),
                _show_text_node(3, 2, [1260, 100]),
                _show_text_node(4, 3, [1260, 440]),
            ],
            [
                [1, 1, 0, 2, 1, "T8_LLM_PROVIDER_CONFIG"],
                [2, 2, 0, 3, 0, "STRING"],
                [3, 2, 1, 4, 0, "STRING"],
            ],
        ),
        "prompt_inspector_local_qwen_example": _workflow(
            "prompt_inspector_local_qwen_example",
            [
                _provider_node(1, [1], [40, 100]),
                _h3_node(2, 1, [520, 60], prompt=h3_prompt, output_links=[2]),
                _inspector_node(3, 2, [1220, 180], warnings_links=[3], summary_links=[4]),
                _show_text_node(4, 3, [1700, 100], order=3),
                _show_text_node(5, 4, [1700, 460], order=3),
            ],
            [
                [1, 1, 0, 2, 5, "T8_LLM_PROVIDER_CONFIG"],
                [2, 2, 0, 3, 0, "STRING"],
                [3, 3, 1, 4, 0, "STRING"],
                [4, 3, 2, 5, 0, "STRING"],
            ],
        ),
        "text_utilities_example": _workflow(
            "text_utilities_example",
            [
                _prompt_text_node(
                    1,
                    [1],
                    [100, 120],
                    text="这里填写提示词、API Key 或任意 STRING；右侧节点会原样显示。",
                ),
                _show_text_node(2, 1, [620, 100], order=1),
            ],
            [[1, 1, 0, 2, 0, "STRING"]],
        ),
        "creative_direction_revision_example": _workflow(
            "creative_direction_revision_example",
            [
                _provider_node(1, [2, 3], [40, 420]),
                _suite_node(
                    2, "T8CreativeDirector", [520, 40], inputs=[],
                    outputs=[
                        ("creative_brief", "T8_CREATIVE_BRIEF", [1, 4]),
                        ("creative_brief_text", "STRING", None),
                        ("creative_brief_json", "STRING", None),
                    ],
                    widgets=[
                        "雨夜霓虹街区，一名红衣女性穿过人群寻找驶离的电车。",
                        "AUTO（下游判断）", "AUTO（下游判断）", "LOCK（锁定）",
                        "AUTO（下游判断）", "EVOLVE（允许演化）", "EVOLVE（允许演化）",
                        "AUTO（下游判断）", "短视频观众 / 电影感追逐", "从克制观察到快速冲刺",
                        "同一名成年女性，红色长风衣，短黑发", "雨夜街区和同一行进方向",
                        "冷蓝霓虹与红衣对比", "前慢后快，动作因果清楚", "雨声、脚步、电车铃",
                        "不改变身份、服装和结尾目标", "允许改变中段障碍与镜头角度",
                    ], size=[560, 760],
                ),
                _suite_node(
                    3, "T8CreativeCandidateLab", [1140, 40],
                    inputs=[
                        _socket("creative_brief", "T8_CREATIVE_BRIEF", 1),
                        _socket("api_key", "STRING", None),
                        _socket("provider_config", "T8_LLM_PROVIDER_CONFIG", 2),
                    ],
                    outputs=[
                        ("candidates_json", "STRING", [5]), ("comparison_report_json", "STRING", None),
                        ("candidate_1", "STRING", None), ("candidate_2", "STRING", None),
                        ("candidate_3", "STRING", None), ("candidate_4", "STRING", None),
                    ],
                    widgets=[
                        "设计三个不同的追逐机制", "MiniMax H3 + Seedance 2.0", "3",
                        "中（不同创作机制）", "creative", "中文", 0, "fixed",
                        "保持红衣人物、电车目标与雨夜空间",
                    ], size=[560, 620],
                ),
                _suite_node(
                    4, "T8CreativeCandidateSelector", [1760, 80],
                    inputs=[_socket("candidates_json", "STRING", 5)],
                    outputs=[("selected_candidate", "STRING", [6])],
                    widgets=["", 1], size=[380, 180], order=2,
                ),
                _suite_node(
                    5, "T8DirectedRevision", [2200, 40],
                    inputs=[
                        _socket("original_prompt", "STRING", 6),
                        _socket("creative_brief", "T8_CREATIVE_BRIEF", 4),
                        _socket("api_key", "STRING", None),
                        _socket("provider_config", "T8_LLM_PROVIDER_CONFIG", 3),
                    ],
                    outputs=[
                        ("revised_prompt", "STRING", [7]),
                        ("revision_report_json", "STRING", None),
                        ("unified_diff", "STRING", None),
                    ],
                    widgets=["", "只提高后半段速度，其他设定不变", "balanced", "中文", 0, "fixed", "红衣\n雨夜\n电车目标"],
                    size=[560, 500], order=3,
                ),
                _show_text_node(6, 7, [2820, 120], order=4),
            ],
            [
                [1, 2, 0, 3, 0, "T8_CREATIVE_BRIEF"],
                [2, 1, 0, 3, 2, "T8_LLM_PROVIDER_CONFIG"],
                [3, 1, 0, 5, 3, "T8_LLM_PROVIDER_CONFIG"],
                [4, 2, 0, 5, 1, "T8_CREATIVE_BRIEF"],
                [5, 3, 0, 4, 0, "STRING"],
                [6, 4, 0, 5, 0, "STRING"],
                [7, 5, 0, 6, 0, "STRING"],
            ],
        ),
        "creative_longform_storyboard_example": _workflow(
            "creative_longform_storyboard_example",
            [
                _provider_node(1, [3, 4], [40, 420]),
                _suite_node(
                    2, "T8CreativeDirector", [520, 40], inputs=[],
                    outputs=[("creative_brief", "T8_CREATIVE_BRIEF", [1, 2]), ("creative_brief_text", "STRING", None), ("creative_brief_json", "STRING", None)],
                    widgets=[
                        "90秒近未来短片：维修机器人护送一株植物穿越停电城市。",
                        "AUTO（下游判断）", "LOCK（锁定）", "LOCK（锁定）", "LOCK（锁定）",
                        "EVOLVE（允许演化）", "EVOLVE（允许演化）", "AUTO（下游判断）",
                        "科幻短片观众", "孤独出发—风险升级—晨光抵达", "同一台旧维修机器人和同一盆植物",
                        "断电城市，始终朝东方移动", "暗青工业空间逐步进入暖光", "每段有明确状态交接",
                        "机械声、风声，配乐逐步明亮", "不瞬移，不更换植物", "允许障碍和机位演化",
                    ], size=[560, 760],
                ),
                _suite_node(
                    3, "T8LongFormPlanner", [1140, 20],
                    inputs=[_socket("creative_brief", "T8_CREATIVE_BRIEF", 1), _socket("api_key", "STRING", None), _socket("provider_config", "T8_LLM_PROVIDER_CONFIG", 3)],
                    outputs=[("global_continuity_brief", "STRING", None), ("h3_segments_json", "STRING", [5]), ("seedance20_segments_json", "STRING", [6]), ("handoff_table_json", "STRING", None)],
                    widgets=["维修机器人护送植物抵达城市东侧温室", "MiniMax H3 + Seedance 2.0", 90, 15, "状态连续（推荐）", "balanced", "中文", 0, "fixed", "机器人划痕、植物叶片数量、东方移动方向保持一致"],
                    size=[580, 620],
                ),
                _suite_node(
                    4, "T8StoryboardPack", [1800, 20],
                    inputs=[_socket("creative_brief", "T8_CREATIVE_BRIEF", 2), _socket("reference_role_map", "T8_REFERENCE_ROLE_MAP", None), _socket("api_key", "STRING", None), _socket("provider_config", "T8_LLM_PROVIDER_CONFIG", 4)],
                    outputs=[("global_prompt", "STRING", [7]), ("shot_list_json", "STRING", None), ("keyframe_prompts_json", "STRING", None), ("transition_sound_json", "STRING", None)],
                    widgets=["为第一段设计可执行分镜", "MiniMax H3 + Seedance 2.0", 15, "5", "balanced", "中文", 0, "fixed"],
                    size=[580, 560],
                ),
                _show_text_node(5, 5, [2460, 20], order=3),
                _show_text_node(6, 6, [2460, 360], order=3),
                _show_text_node(7, 7, [2920, 180], order=3),
            ],
            [
                [1, 2, 0, 3, 0, "T8_CREATIVE_BRIEF"], [2, 2, 0, 4, 0, "T8_CREATIVE_BRIEF"],
                [3, 1, 0, 3, 2, "T8_LLM_PROVIDER_CONFIG"], [4, 1, 0, 4, 3, "T8_LLM_PROVIDER_CONFIG"],
                [5, 3, 1, 5, 0, "STRING"], [6, 3, 2, 6, 0, "STRING"], [7, 4, 0, 7, 0, "STRING"],
            ],
        ),
        "creative_music_video_suite_example": _workflow(
            "creative_music_video_suite_example",
            [
                _provider_node(1, [1, 4], [40, 320]),
                _suite_node(
                    2, "T8MusicCreativeLab", [540, 20],
                    inputs=[_socket("api_key", "STRING", None), _socket("provider_config", "T8_LLM_PROVIDER_CONFIG", 1)],
                    outputs=[("selected_result", "STRING", [2]), ("candidates_json", "STRING", None), ("song_titles_json", "STRING", None), ("soft_qa_report_json", "STRING", None), ("version_diff", "STRING", None)],
                    widgets=["歌词候选（T8非官方）", "温暖中文公路流行歌，女声，副歌明亮", "中文", "3", "balanced", 0, "fixed", "", "", "", "", "不要模仿现有歌曲"],
                    size=[580, 620],
                ),
                _suite_node(
                    3, "T8CreativeVersionStack", [1200, 80],
                    inputs=[_socket("base_version", "STRING", 2), _socket("versions.version_0", "STRING", None, label="version_0")],
                    outputs=[("selected_text", "STRING", [3]), ("version_history_json", "STRING", None), ("diff_from_previous", "STRING", None)],
                    widgets=["", 1, "AI候选\n人工修改版"], size=[480, 320], order=2,
                ),
                _suite_node(
                    4, "T8MusicVideoBeatSheet", [1760, 20],
                    inputs=[_socket("lyrics", "STRING", 3), _socket("api_key", "STRING", None), _socket("provider_config", "T8_LLM_PROVIDER_CONFIG", 4)],
                    outputs=[("beat_sheet", "T8_MUSIC_VIDEO_BEAT_SHEET", None), ("beat_sheet_json", "STRING", None), ("h3_direction", "STRING", [5]), ("seedance20_direction", "STRING", [6])],
                    widgets=["公路旅行MV，从清晨独行到傍晚抵达", 30, 0, "AUTO（根据时长与内容）", "中文", "balanced", 0, "fixed", "", "", "副歌进入时提高剪辑密度"],
                    size=[580, 600], order=3,
                ),
                _show_text_node(5, 5, [2420, 40], order=4),
                _show_text_node(6, 6, [2420, 400], order=4),
            ],
            [
                [1, 1, 0, 2, 1, "T8_LLM_PROVIDER_CONFIG"], [2, 2, 0, 3, 0, "STRING"],
                [3, 3, 0, 4, 0, "STRING"], [4, 1, 0, 4, 2, "T8_LLM_PROVIDER_CONFIG"],
                [5, 4, 2, 5, 0, "STRING"], [6, 4, 3, 6, 0, "STRING"],
            ],
        ),
        "creative_reference_dna_preset_example": _workflow(
            "creative_reference_dna_preset_example",
            [
                _provider_node(1, [1], [40, 420]),
                _suite_node(
                    2, "T8ReferenceRoleMapper", [520, 20],
                    inputs=[
                        _socket("reference_images.reference_image_0", "IMAGE", None, label="reference_image_0"),
                        _socket("reference_videos.reference_video_0", "VIDEO", None, label="reference_video_0"),
                        _socket("creative_brief", "T8_CREATIVE_BRIEF", None),
                        _socket("api_key", "STRING", None),
                        _socket("provider_config", "T8_LLM_PROVIDER_CONFIG", 1),
                    ],
                    outputs=[("reference_role_map", "T8_REFERENCE_ROLE_MAP", [2]), ("reference_role_map_json", "STRING", None), ("coverage_conflict_report", "STRING", None), ("reference_context_for_enhancer", "STRING", None)],
                    widgets=["产品短片：同一台复古相机从桌面进入户外拍摄", "balanced", "中文", 0, "fixed", "图片负责产品身份；视频负责手持动作。可连接自己的 IMAGE/VIDEO。"],
                    size=[580, 620],
                ),
                _suite_node(
                    3, "T8CreativeDNAMixer", [1180, 20], inputs=[],
                    outputs=[("creative_dna_mix", "T8_CREATIVE_DNA_MIX", [3]), ("creative_dna_instruction", "STRING", None), ("creative_dna_json", "STRING", None)],
                    widgets=["复古相机从静物陈列进入真实拍摄", "产品广告｜功能证据递进", "机械同行｜启动后稳定伴行", "平面重组｜几何节奏品牌片", "MiniMax H3 + Seedance 2.0"],
                    size=[560, 420],
                ),
                _suite_node(
                    4, "T8PersonalCreativePreset", [1180, 500], inputs=[],
                    outputs=[("personal_preset", "T8_PERSONAL_CREATIVE_PRESET", [4]), ("preset_instruction", "STRING", None), ("preset_json", "STRING", None)],
                    widgets=["我的复古产品片", "产品身份稳定、功能证据可见", "产品+操作+可见结果", "静物建立\n手部启动\n结果收束", "暖褐色、克制推镜", "仅保存文字规则，不包含第三方媒体", "不出现错误品牌文字"],
                    size=[560, 520],
                ),
                _suite_node(
                    5, "T8CreativeContextAssembler", [1820, 160],
                    inputs=[
                        _socket("creative_brief", "T8_CREATIVE_BRIEF", None),
                        _socket("reference_role_map", "T8_REFERENCE_ROLE_MAP", 2),
                        _socket("creative_dna_mix", "T8_CREATIVE_DNA_MIX", 3),
                        _socket("personal_preset", "T8_PERSONAL_CREATIVE_PRESET", 4),
                    ],
                    outputs=[("enhancer_context", "STRING", [5]), ("assembled_context_json", "STRING", None)],
                    widgets=["人物和品牌文字不得从案例中复制"], size=[520, 400], order=2,
                ),
                _show_text_node(6, 5, [2420, 220], order=3),
            ],
            [
                [1, 1, 0, 2, 4, "T8_LLM_PROVIDER_CONFIG"], [2, 2, 0, 5, 1, "T8_REFERENCE_ROLE_MAP"],
                [3, 3, 0, 5, 2, "T8_CREATIVE_DNA_MIX"], [4, 4, 0, 5, 3, "T8_PERSONAL_CREATIVE_PRESET"],
                [5, 5, 0, 6, 0, "STRING"],
            ],
        ),
    }


def _upgrade_existing() -> None:
    append_by_type = {
        "MiniMaxH3PromptEnhancerT8": (22, 31, H3_LOCAL_DEFAULTS),
        "Seedance20PromptEnhancerT8": (26, 35, SEEDANCE_LOCAL_DEFAULTS),
        "MiniMaxMusic3PromptEnhancerT8": (31, 38, MUSIC_LOCAL_DEFAULTS),
    }
    for path in EXAMPLES.glob("*.json"):
        if path.stem in _generated_workflows():
            continue
        workflow = json.loads(path.read_text(encoding="utf-8"))
        changed = False
        for node in workflow.get("nodes", []):
            contract = append_by_type.get(node.get("type"))
            if not contract:
                continue
            old_count, current_count, defaults = contract
            values = node.get("widgets_values")
            if not isinstance(values, list):
                raise RuntimeError(f"{path.name}: {node['type']} has no widget array")
            if len(values) == old_count:
                values.extend(defaults)
                changed = True
            elif len(values) != current_count:
                raise RuntimeError(f"{path.name}: unexpected {node['type']} widget count {len(values)}")
        if changed:
            path.write_text(json.dumps(workflow, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_thumbnail(path: Path, title: str, source: str, target: str, footer: str) -> None:
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", (640, 360), "#111827")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((36, 48, 604, 312), radius=24, fill="#1f2937", outline="#22c55e", width=4)
    draw.rounded_rectangle((70, 104, 250, 258), radius=16, fill="#0f172a", outline="#38bdf8", width=3)
    draw.rounded_rectangle((390, 104, 570, 258), radius=16, fill="#0f172a", outline="#a78bfa", width=3)
    draw.line((250, 181, 390, 181), fill="#86efac", width=7)
    draw.polygon([(390, 181), (370, 169), (370, 193)], fill="#86efac")
    font = ImageFont.load_default()
    draw.text((64, 68), title, fill="#f8fafc", font=font)
    draw.text((86, 174), source, fill="#7dd3fc", font=font)
    draw.text((416, 174), target, fill="#c4b5fd", font=font)
    draw.text((64, 282), footer, fill="#d1fae5", font=font)
    image.save(path, format="JPEG", quality=88, optimize=True)


def build() -> None:
    EXAMPLES.mkdir(parents=True, exist_ok=True)
    _upgrade_existing()
    thumbnails = {
        "minimax_h3_prompt_enhancer_example": ("MiniMax H3 - Cloud", "API Key STRING", "H3 prompt", "Enter your own key; no secret is bundled"),
        "seedance20_prompt_enhancer_example": ("Seedance 2.0 - Cloud", "API Key STRING", "video prompt", "Enter your own key; no secret is bundled"),
        "music3_prompt_lyrics_enhancer_example": ("Music 3 - Cloud", "API Key STRING", "lyrics + caption", "Enter your own key; no secret is bundled"),
        "basic_workflow_multi_task_connections": ("One Provider Config", "Shared provider", "H3 + S2 + Music", "Local Qwen: no API key required"),
        "minimax_h3_local_qwen_example": ("MiniMax H3 - Local Qwen", "Local Qwen 27B", "H3 prompt", "No API key; provider_config is connected"),
        "seedance20_local_qwen_example": ("Seedance 2.0 - Local Qwen", "Local Qwen 27B", "video prompt", "No API key; provider_config is connected"),
        "music3_local_qwen_example": ("Music 3 - Local Qwen", "Local Qwen 27B", "lyrics + caption", "No API key; text-only mode"),
        "prompt_inspector_local_qwen_example": ("Local Qwen + Prompt Inspector", "Local Qwen 27B", "local QA", "Enhance, inspect, then display"),
        "text_utilities_example": ("T8 STRING Utilities", "T8 Prompt Text", "T8 Show Text", "No third-party nodes required"),
        "creative_direction_revision_example": ("Creative Direction + Revision", "Director + Candidates", "Surgical revision", "One request per LLM node"),
        "creative_longform_storyboard_example": ("Long-form + Storyboard", "Shared creative brief", "H3 + Seedance plans", "Continuity-aware planning"),
        "creative_music_video_suite_example": ("Music Creative Suite", "Lyrics + versions", "H3 + Seedance beat sheet", "Text evidence only"),
        "creative_reference_dna_preset_example": ("Reference + Creative DNA", "User media roles", "Reusable context STRING", "Preview media is never sent"),
    }
    for stem, workflow in _generated_workflows().items():
        (EXAMPLES / f"{stem}.json").write_text(
            json.dumps(workflow, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        thumbnail = EXAMPLES / f"{stem}.jpg"
        _write_thumbnail(thumbnail, *thumbnails[stem])


def check() -> None:
    expected_counts = {
        "MiniMaxH3PromptEnhancerT8": 31,
        "Seedance20PromptEnhancerT8": 35,
        "MiniMaxMusic3PromptEnhancerT8": 38,
    }
    workflows = sorted(EXAMPLES.glob("*.json"))
    if len(workflows) != 13:
        raise RuntimeError(f"Expected 13 example workflows, found {len(workflows)}")
    expected_inputs = {
        "MiniMaxH3PromptEnhancerT8": [
            "first_frame", "last_frame", "reference_images.reference_image_0",
            "reference_videos.reference_video_0", "api_key", "provider_config",
        ],
        "Seedance20PromptEnhancerT8": [
            "first_frame", "last_frame", "reference_images.reference_image_0",
            "reference_videos.reference_video_0", "api_key", "provider_config",
        ],
        "MiniMaxMusic3PromptEnhancerT8": ["api_key", "provider_config"],
        "T8LLMProviderConfig": [],
        "T8PromptInspector": ["prompt"],
        "T8PromptText": [],
        "T8ShowText": ["text"],
        "T8CreativeDirector": [],
        "T8CreativeCandidateLab": ["creative_brief", "api_key", "provider_config"],
        "T8CreativeCandidateSelector": ["candidates_json"],
        "T8DirectedRevision": ["original_prompt", "creative_brief", "api_key", "provider_config"],
        "T8LongFormPlanner": ["creative_brief", "api_key", "provider_config"],
        "T8StoryboardPack": ["creative_brief", "reference_role_map", "api_key", "provider_config"],
        "T8MusicCreativeLab": ["api_key", "provider_config"],
        "T8CreativeVersionStack": ["base_version", "versions.version_0"],
        "T8MusicVideoBeatSheet": ["lyrics", "api_key", "provider_config"],
        "T8ReferenceRoleMapper": [
            "reference_images.reference_image_0", "reference_videos.reference_video_0",
            "creative_brief", "api_key", "provider_config",
        ],
        "T8CreativeDNAMixer": [],
        "T8PersonalCreativePreset": [],
        "T8CreativeContextAssembler": ["creative_brief", "reference_role_map", "creative_dna_mix", "personal_preset"],
    }
    allowed_types = set(expected_inputs)
    seen_types: set[str] = set()
    for path in workflows:
        workflow = json.loads(path.read_text(encoding="utf-8"))
        nodes = {node["id"]: node for node in workflow.get("nodes", [])}
        for node in nodes.values():
            seen_types.add(node["type"])
            if node["type"] not in allowed_types:
                raise RuntimeError(f"{path.name}: unsupported external node {node['type']}")
            actual_inputs = [item["name"] for item in node.get("inputs", [])]
            if actual_inputs != expected_inputs[node["type"]]:
                raise RuntimeError(
                    f"{path.name}: invalid {node['type']} sockets {actual_inputs}; "
                    f"expected {expected_inputs[node['type']]}"
                )
            if node["type"] in expected_counts:
                values = node.get("widgets_values", [])
                if len(values) != expected_counts[node["type"]]:
                    raise RuntimeError(f"{path.name}: invalid {node['type']} widget count {len(values)}")
                local_index = {"MiniMaxH3PromptEnhancerT8": 22, "Seedance20PromptEnhancerT8": 26, "MiniMaxMusic3PromptEnhancerT8": 31}[node["type"]]
                if values[local_index] in (None, "", "randomize"):
                    raise RuntimeError(f"{path.name}: invalid local model widget value")
                if node["type"] == "Seedance20PromptEnhancerT8":
                    if values[13] not in (SEEDANCE_API_MODE, LOCAL_API_MODE):
                        raise RuntimeError(f"{path.name}: Seedance API mode is positionally misaligned")
                    if values[14] != "gemini-3.5-flash" or not isinstance(values[15], int):
                        raise RuntimeError(f"{path.name}: Seedance custom length is positionally misaligned")
                    if values[25] not in ("fixed", "increment", "decrement", "randomize"):
                        raise RuntimeError(f"{path.name}: Seedance seed control is positionally misaligned")
        for link in workflow.get("links", []):
            if link[1] not in nodes or link[3] not in nodes:
                raise RuntimeError(f"{path.name}: dangling link {link[0]}")
            source = nodes[link[1]]
            target = nodes[link[3]]
            if link[2] >= len(source.get("outputs", [])) or link[4] >= len(target.get("inputs", [])):
                raise RuntimeError(f"{path.name}: out-of-range link slot {link[0]}")
            output = source["outputs"][link[2]]
            input_item = target["inputs"][link[4]]
            if output.get("type") != link[5] or input_item.get("type") != link[5]:
                raise RuntimeError(f"{path.name}: link type mismatch {link[0]}")
            if link[0] not in (output.get("links") or []) or input_item.get("link") != link[0]:
                raise RuntimeError(f"{path.name}: link bookkeeping mismatch {link[0]}")
        if not path.with_suffix(".jpg").is_file():
            raise RuntimeError(f"{path.name}: missing matching thumbnail")
        if not any(node["type"] == "T8ShowText" for node in nodes.values()):
            raise RuntimeError(f"{path.name}: result is not connected to T8ShowText")
        if "sk-" in path.read_text(encoding="utf-8"):
            raise RuntimeError(f"{path.name}: possible API key")
    required = {
        "MiniMaxH3PromptEnhancerT8", "Seedance20PromptEnhancerT8", "MiniMaxMusic3PromptEnhancerT8",
        "T8LLMProviderConfig", "T8PromptInspector", "T8PromptText", "T8ShowText",
        "T8CreativeDirector", "T8CreativeContextAssembler", "T8DirectedRevision",
        "T8LongFormPlanner", "T8ReferenceRoleMapper", "T8CreativeCandidateLab",
        "T8CreativeCandidateSelector", "T8StoryboardPack", "T8CreativeDNAMixer",
        "T8PersonalCreativePreset", "T8MusicCreativeLab", "T8CreativeVersionStack",
        "T8MusicVideoBeatSheet",
    }
    if not required.issubset(seen_types):
        raise RuntimeError(f"Missing node examples: {sorted(required - seen_types)}")
    for path in workflows:
        workflow = json.loads(path.read_text(encoding="utf-8"))
        for node in workflow.get("nodes", []):
            if node.get("type") == "T8LLMProviderConfig":
                values = node.get("widgets_values", [])
                if len(values) != 16 or values[:4] != ["Local Qwen", "AUTO（兼容策略）", LOCAL_MODEL, LOCAL_MMPROJ]:
                    raise RuntimeError(f"{path.name}: shared provider widget order is invalid")
            if node.get("type") == "T8PromptInspector":
                values = node.get("widgets_values", [])
                if len(values) != 6 or not isinstance(values[4], int):
                    raise RuntimeError(f"{path.name}: Prompt Inspector widget order is invalid")
        if "local_qwen" in path.stem or path.stem == "basic_workflow_multi_task_connections":
            providers = [node for node in workflow["nodes"] if node["type"] == "T8LLMProviderConfig"]
            if len(providers) != 1 or providers[0]["widgets_values"][0] != "Local Qwen":
                raise RuntimeError(f"{path.name}: local workflow has no Local Qwen provider config")
    print(json.dumps({"workflows": len(workflows), "node_types": sorted(seen_types), "passed": True}, ensure_ascii=False))


def main() -> int:
    parser = argparse.ArgumentParser(description="Build or verify bundled ComfyUI example workflows.")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        check()
    else:
        build()
        check()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
