"""Actual CPU decoder and official Comfy VIDEO contracts, no inference."""
import base64
from fractions import Fraction
import importlib
import inspect
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parents[1]))
sys.path.insert(0, str(ROOT))
import comfy.cli_args
comfy.cli_args.args.cpu = True
import av
import numpy as np
import torch
from PIL import Image
from comfy_api.latest._input_impl import video_types as video_impl
VideoFromFile, VideoFromComponents = video_impl.VideoFromFile, video_impl.VideoFromComponents
VideoFromList = getattr(video_impl,"VideoFromList",None)
from comfy_api.latest._util.video_types import VideoComponents
import strata_provider as sp
import strata_media as media
from strata_vendor import video_shared as shared
from test_strata_provider import http_fixture

def encoded_video(count=24, fps=4, pts=None):
    stream_buffer = io.BytesIO()
    with av.open(stream_buffer, mode="w", format="mp4") as container:
        stream = container.add_stream("libx264", rate=fps)
        stream.width, stream.height, stream.pix_fmt = 64, 48, "yuv420p"
        stream.options = {"crf": "1", "preset": "ultrafast"}
        if pts is not None: stream.time_base = Fraction(1, 1000)
        for index in range(count):
            image = np.zeros((48, 64, 3), dtype=np.uint8)
            image[..., 0] = round(index * 255 / max(1,count-1))
            frame = av.VideoFrame.from_ndarray(image, format="rgb24")
            if pts is not None: frame.pts, frame.time_base = pts[index], Fraction(1,1000)
            for packet in stream.encode(frame): container.mux(packet)
        for packet in stream.encode(): container.mux(packet)
    return stream_buffer.getvalue()

class StrataMediaTests(unittest.TestCase):
    def setUp(self):
        self.run=sp.StrataRun()
        self.token=sp._RUN.set(self.run)
        self.addCleanup(lambda: sp._RUN.reset(self.token))
        self.addCleanup(self.run.close)

    def test_real_cfr_first_last_valid_and_bounded_samples(self):
        result=media.sample_asset(VideoFromFile(io.BytesIO(encoded_video())))
        stamps=[f.timestamp_s for f in result.frames]
        self.assertEqual(stamps[0],0.)
        self.assertAlmostEqual(stamps[-1],5.75)
        self.assertLessEqual(len(stamps),8)
        self.assertTrue(all(a<b for a,b in zip(stamps,stamps[1:])))
        self.assertLess(np.asarray(result.frames[0].image)[...,0].mean(),10)
        self.assertGreater(np.asarray(result.frames[-1].image)[...,0].mean(),240)

    def test_real_trim_crop_and_clip_clock(self):
        has_crop="crop" in inspect.signature(VideoFromFile).parameters
        video=VideoFromFile(io.BytesIO(encoded_video()),start_time=-3,duration=2,**({"crop":(8,6,32,24)} if has_crop else {}))
        result=media.sample_asset(video)
        self.assertEqual(result.frames[0].timestamp_s,0.)
        self.assertAlmostEqual(result.frames[0].source_timestamp_s,3.)
        self.assertAlmostEqual(result.frames[-1].timestamp_s,1.75)
        self.assertEqual(result.frames[0].image.size,(32,24) if has_crop else (64,48))
        parts=media.build_strata_media_parts([{"kind":"video","label":"<Video 1>","value":video}])
        self.assertEqual(parts[1]["metadata"]["duration_s"],2.)
        self.assertEqual(parts[1]["metadata"]["time_origin_s"],3.)

    def test_real_vfr_pts_not_assumed_fps(self):
        times=[0,100,250,550,1000,1800]
        video=VideoFromFile(io.BytesIO(encoded_video(count=6,fps=20,pts=times)))
        result=media.sample_asset(video)
        self.assertAlmostEqual(result.frames[-1].source_timestamp_s,1.8)
        self.assertTrue(all(f.timestamp_kind=="pts" for f in result.frames))

    def test_real_nonzero_container_origin_is_separate_from_trim_clock(self):
        video=VideoFromFile(io.BytesIO(encoded_video(count=12,fps=4,pts=[5000+i*250 for i in range(12)])),start_time=1,duration=1)
        result=media.sample_asset(video)
        self.assertAlmostEqual(result.frames[0].timestamp_s,0.)
        self.assertAlmostEqual(result.frames[0].source_timestamp_s,6.)
        self.assertAlmostEqual(result.frames[-1].source_timestamp_s,6.75)
        parts=media.build_strata_media_parts([{"kind":"video","label":"origin","value":video}])
        self.assertEqual(parts[1]["metadata"]["time_origin_s"],6.)

    @unittest.skipUnless("color_space" in inspect.signature(VideoFromComponents).parameters,"This Comfy version has no HDR component constructor")
    def test_hdr_component_is_rejected_not_mislabeled_as_srgb(self):
        video=VideoFromComponents(VideoComponents(images=torch.zeros((4,16,16,3)),frame_rate=Fraction(4)),color_space="HDR PQ")
        with self.assertRaises(sp.StrataProviderError):media.sample_asset(video)

    def test_one_frame_is_not_duplicated_for_endpoint_policy(self):
        result=media.sample_asset(VideoFromFile(io.BytesIO(encoded_video(count=1))))
        self.assertEqual(len(result.frames),1)

    def test_components_alpha_and_no_audio_access(self):
        images=torch.zeros((12,16,16,3))
        images[-1,:,:,0]=1
        alpha=torch.zeros((12,16,16)); alpha[-1]=1
        video=VideoFromComponents(VideoComponents(images=images,frame_rate=Fraction(4),alpha=alpha,audio={"unread":"sentinel"}))
        with patch.object(VideoFromComponents,"get_stream_source",side_effect=AssertionError("must not materialize"),create=True), \
             patch.object(VideoFromComponents,"get_components",side_effect=AssertionError("v0.33 getter drops alpha")):
            result=media.sample_asset(video)
        self.assertEqual(result.frames[0].image.getpixel((0,0)),(255,255,255))
        self.assertEqual(result.frames[-1].image.getpixel((0,0)),(255,0,0))
        self.assertAlmostEqual(result.frames[-1].timestamp_s,2.75)

    @unittest.skipUnless(VideoFromList is not None,"This Comfy version has no accumulated VIDEO class")
    def test_list_uses_composite_clock_without_whole_materialization(self):
        video=VideoFromList([VideoFromFile(io.BytesIO(encoded_video(count=8))) for _ in range(3)],complete_audio={"unread":True})
        with patch.object(VideoFromList,"get_stream_source",side_effect=AssertionError("whole list prohibited")), \
             patch.object(VideoFromList,"get_components",side_effect=AssertionError("whole list prohibited")):
            result=media.sample_asset(video)
        self.assertAlmostEqual(result.frames[0].timestamp_s,0.)
        self.assertAlmostEqual(result.frames[-1].timestamp_s,5.75)
        self.assertEqual(result.manifest["source"]["kind"],"video_list")
        self.assertEqual(result.manifest["frames"][-1]["component_index"],2)
        self.assertLessEqual(len(result.frames),8)

    def test_v033_exact_file_and_component_state_are_supported(self):
        video=VideoFromFile(io.BytesIO(encoded_video(count=12)),start_time=1,duration=1)
        vars(video).pop("_VideoFromFile__crop",None)
        self.assertAlmostEqual(media.sample_asset(video).frames[-1].timestamp_s,.75)
        component=VideoFromComponents(VideoComponents(images=torch.zeros((4,16,16,3)),frame_rate=Fraction(4)))
        vars(component).pop("_VideoFromComponents__color_space",None)
        self.assertAlmostEqual(media.sample_asset(component).frames[-1].timestamp_s,.75)

    def test_source_roles_report_and_run_cache(self):
        image=torch.ones((1,16,16,3))
        video=VideoFromFile(io.BytesIO(encoded_video()))
        plan=[{"kind":"image","label":"<Picture 1>","role":"last_frame","value":image},
              {"kind":"video","label":"<Video 1>","role":"reference_video","value":video}]
        first=media.build_strata_media_parts(plan)
        self.assertIs(first,media.build_strata_media_parts(plan))
        self.assertEqual([part["type"] for part in first],["text","image_url","text","strata_video"])
        self.assertIn("<Picture 1>",first[0]["text"])
        self.assertIn("No audio was decoded",first[2]["text"])
        report=self.run.media_reports[0]
        self.assertFalse(report["audio_analyzed"]); self.assertFalse(report["continuous_observation"])
        self.assertGreater(report["max_sample_gap_s"],0.)
        self.run.close(); self.assertFalse(self.run.video_cache);self.assertFalse(self.run.media_cache)

    def test_unknown_video_rejected_without_generic_getters(self):
        class Unknown:
            def get_stream_source(self): raise AssertionError("unknown source getter")
        with self.assertRaises(sp.StrataProviderError): media.video_info(Unknown())

    def test_cancellation_and_invalid_pixels_do_not_become_samples(self):
        with self.assertRaises(shared.VideoCancelled):
            shared.sample_video(io.BytesIO(encoded_video()),cancel=lambda:True)
        with self.assertRaises(sp.StrataProviderError): media._image(np.full((1,16,16,3),float("nan")))

    def test_oversized_or_invalid_tensor_is_rejected_before_cpu_transfer(self):
        class InvalidTensor:
            def __init__(self, shape): self.shape = shape
            def detach(self): raise AssertionError("Known-invalid tensor must not be transferred or converted")
        for shape in ((1,8192,8192,3), (2,16,16,3), (1,16,16,2), (1,0,16,3)):
            with self.subTest(shape=shape), self.assertRaises(sp.StrataProviderError):
                media._image(InvalidTensor(shape))

    def test_video_contract_aggregate_guard_prevents_post(self):
        self.run.close(); sp._RUN.reset(self.token)
        with http_fixture() as (url,seen):
            self.run=sp.StrataRun({"url":url,"video_max_frames":64})
            self.token=sp._RUN.set(self.run)
            video=VideoFromFile(io.BytesIO(encoded_video(count=40,fps=2)))
            parts=media.build_strata_media_parts([{"kind":"video","label":str(i),"value":video} for i in range(4)])
            with self.assertRaisesRegex(sp.StrataProviderError,"Too many"):
                self.run.complete([{"role":"user","content":parts}],temperature=.5)
            self.assertFalse(any(item[0]=="POST" for item in seen))

if __name__=="__main__": unittest.main()
