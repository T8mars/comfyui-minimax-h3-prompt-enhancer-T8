"""Reference-duration regressions: real CPU decoding, isolated provider responses."""

import base64
import json
import unittest
from unittest.mock import patch

import numpy as np
import requests

from test_local_qwen import (
    FakeLocalProvider,
    NativeVideo,
    encoded_video_bytes,
    media,
    nodes,
    seedance20,
)
from test_nodes import FakeSession, FakeVideo, reference_output


class ReferenceVideoDurationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Tiny but genuine 32-second MP4, rather than fake duration metadata.
        cls.video_bytes = encoded_video_bytes(frame_count=32, fps=1)

    def setUp(self):
        # No regression may accidentally use a paid endpoint or load a GGUF.
        network = patch.object(
            requests.sessions.Session,
            "request",
            side_effect=AssertionError("Unexpected real network request"),
        )
        network.start()
        self.addCleanup(network.stop)
        instances = patch.object(FakeLocalProvider, "instances", [])
        instances.start()
        self.addCleanup(instances.stop)

    def enhance(self, module, videos, *, session=None, **kwargs):
        values = {
            "prompt": "Follow the reference movement through the complete timeline.",
            "duration_seconds": 30,
            "output_language": "English",
            "reference_images": {"reference_image_0": np.zeros((1, 16, 16, 3), dtype=np.float32)},
            "reference_videos": {f"reference_video_{i}": video for i, video in enumerate(videos)},
            "api_key": "placeholder-not-a-live-secret",
            "session": session,
            "local_video_sample_fps": 0.25,
            "local_max_tokens": 4096,
        }
        values.update(kwargs)
        if module is nodes:
            values.setdefault("task_type", "Ref2VA")
            return nodes.enhance_prompt(**values)
        values.setdefault("task_intent", "MultiRef")
        return seedance20.enhance_seedance20_prompt(**values)

    def completion(self, module):
        return reference_output() if module is nodes else "Shot 1: The performer follows the supplied motion."

    def test_short_long_and_combined_durations_reach_cloud_unchanged(self):
        durations = ((0.25,), (1.9,), (16,), (30,), (3600,), (8, 8), (20, 30, 60))
        for module in (nodes, seedance20):
            for values in durations:
                with self.subTest(node=module.__name__, durations=values):
                    videos = [FakeVideo(duration=value, data=f"complete-video-{i}".encode())
                              for i, value in enumerate(values)]
                    session = FakeSession(self.completion(module))
                    result = self.enhance(module, videos, session=session)
                    self.assertEqual(result, self.completion(module))
                    self.assertEqual(len(session.chat_requests), 1)
                    video_uploads = [upload[1] for upload in session.uploads if upload[2] == "video/mp4"]
                    self.assertEqual(video_uploads, [video.data for video in videos])

    def test_real_long_videos_reach_all_four_provider_paths(self):
        for module in (nodes, seedance20):
            for api_mode in nodes.API_MODES:
                with self.subTest(node=module.__name__, provider=api_mode):
                    videos = [NativeVideo(self.video_bytes, 32.0) for _ in range(2)]
                    response = self.completion(module)
                    session = FakeSession(response)
                    with (
                        patch.object(module, "LocalQwenProvider", FakeLocalProvider),
                        patch.object(FakeLocalProvider, "response", response),
                    ):
                        result = self.enhance(
                            module, videos, session=session, api_mode=api_mode,
                            api_key="" if api_mode == nodes.LOCAL_QWEN_API_MODE else "placeholder-not-a-live-secret",
                            openai_base_url="http://127.0.0.1:9000/v1",
                            custom_model="vision-test-model",
                        )
                    self.assertEqual(result, response)
                    if api_mode == nodes.LOCAL_QWEN_API_MODE:
                        instance = FakeLocalProvider.instances[-1]
                        self.assertEqual(len(instance.calls), 1)
                        self.assertEqual(instance.closed, [False])
                        content = instance.messages[0][-1]["content"]
                        self.assertEqual(json.dumps(content).count("covering 32.000 seconds"), 2)
                        self.assertEqual(session.chat_requests, [])
                        self.assertEqual(session.uploads, [])
                    else:
                        self.assertEqual(len(session.chat_requests), 1)
                        content = session.chat_requests[0]["json"]["messages"][-1]["content"]
                        if api_mode == nodes.SEEDANCE_API_MODE:
                            uploads = [upload[1] for upload in session.uploads if upload[2] == "video/mp4"]
                            self.assertEqual(uploads, [self.video_bytes, self.video_bytes])
                        elif api_mode == nodes.AI_WORKSHOP_API_MODE:
                            urls = [part["image_url"]["url"] for part in content
                                    if part.get("type") == "image_url"
                                    and part["image_url"]["url"].startswith("data:video/mp4;base64,")]
                            self.assertEqual([base64.b64decode(url.split(",", 1)[1]) for url in urls],
                                             [self.video_bytes, self.video_bytes])
                            self.assertEqual(session.uploads, [])
                        else:
                            text = json.dumps(content)
                            self.assertEqual(text.count("covering 32.000s"), 2)
                            self.assertEqual(text.count("at 28.000s."), 2)
                            self.assertEqual(session.uploads, [])

    def test_invalid_duration_still_fails_before_every_provider(self):
        for module in (nodes, seedance20):
            for api_mode in nodes.API_MODES:
                for duration in (0, -1, float("nan"), float("inf"), -float("inf"), "invalid"):
                    with self.subTest(node=module.__name__, provider=api_mode, duration=duration):
                        session = FakeSession(self.completion(module))
                        with patch.object(module, "LocalQwenProvider") as local:
                            with self.assertRaisesRegex(nodes.PromptEnhancerError, "duration metadata"):
                                self.enhance(module, [FakeVideo(duration=duration)], session=session, api_mode=api_mode)
                            local.assert_not_called()
                        self.assertEqual(session.uploads, [])
                        self.assertEqual(session.chat_requests, [])

    def test_seedance_video_edit_extend_and_track_modes_accept_long_references(self):
        for task, count in (("VideoEdit", 1), ("VideoExtend", 1), ("TrackFill", 2), ("Combined", 2)):
            with self.subTest(task=task):
                session = FakeSession(self.completion(seedance20))
                self.enhance(seedance20, [FakeVideo(duration=30) for _ in range(count)],
                             session=session, task_intent=task)
                self.assertEqual(len(session.chat_requests), 1)
                self.assertEqual(sum(upload[2] == "video/mp4" for upload in session.uploads), count)

    def test_real_sampling_covers_timeline_after_fifteen_seconds(self):
        video = NativeVideo(self.video_bytes, 32.0)
        pairs, duration = media.sample_video_as_data_urls(video, frames_per_second=0.25)
        self.assertEqual(duration, 32.0)
        timestamps = [timestamp for timestamp, _url in pairs]
        self.assertEqual(timestamps, list(range(0, 32, 4)))
        self.assertTrue(all(url.startswith("data:image/jpeg;base64,") for _timestamp, url in pairs))

    def test_long_local_trim_is_honored_but_not_uploaded_untrimmed(self):
        for module in (nodes, seedance20):
            with self.subTest(node=module.__name__):
                video = NativeVideo(self.video_bytes, 32.0, trim=(4.0, 20.0))
                response = self.completion(module)
                with (
                    patch.object(module, "LocalQwenProvider", FakeLocalProvider),
                    patch.object(FakeLocalProvider, "response", response),
                ):
                    result = self.enhance(module, [video], api_mode=nodes.LOCAL_QWEN_API_MODE, api_key="")
                self.assertEqual(result, response)
                text = json.dumps(FakeLocalProvider.instances[-1].messages)
                self.assertIn("covering 20.000 seconds", text)
                self.assertEqual(FakeLocalProvider.instances[-1].closed, [False])
                pairs, duration = media.sample_video_as_data_urls(video, frames_per_second=0.25)
                self.assertEqual(duration, 20.0)
                self.assertEqual(pairs[-1][0], 16.0)
                for api_mode in nodes.API_MODES[:-1]:
                    session = FakeSession(response)
                    with self.assertRaisesRegex(nodes.PromptEnhancerError, "Trimmed VIDEO inputs cannot be uploaded safely"):
                        self.enhance(module, [video], session=session, api_mode=api_mode)
                    self.assertEqual(session.uploads, [])
                    self.assertEqual(session.chat_requests, [])


if __name__ == "__main__":
    unittest.main()
