"""Audit official component metadata without decoding or re-encoding media."""
from fractions import Fraction
import unittest
from unittest.mock import patch

from test_strata_media import VideoComponents, VideoFromComponents, media, sp, torch
import speech_reference as speech
from strata_vendor import video as adapter


class VideoComponentCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.run = sp.StrataRun()
        self.token = sp._RUN.set(self.run)
        self.addCleanup(lambda: sp._RUN.reset(self.token))
        self.addCleanup(self.run.close)

    def component(self, *, chroma=None, audio=None):
        images = torch.zeros((4, 16, 16, 3))
        images[-1, :, :, 0] = 1
        alpha = torch.zeros((4, 16, 16))
        alpha[-1] = 1
        video = VideoFromComponents(VideoComponents(
            images=images, frame_rate=Fraction(4), alpha=alpha, audio=audio))
        # Exact ComfyUI 17ff1dc layout, also exercised on the minimum host.
        vars(video).update(_VideoFromComponents__bit_depth=8,
                           _VideoFromComponents__color_space="sRGB",
                           _VideoFromComponents__chroma_subsampling=chroma)
        return video

    def test_current_encoding_metadata_preserves_frames_alpha_and_clock(self):
        for chroma in (None, "4:2:0", "4:2:2", "4:4:4"):
            with self.subTest(chroma=chroma):
                video = self.component(chroma=chroma, audio={"unread": True})
                self.run.video_cache.clear()
                with patch.object(VideoFromComponents, "get_components", side_effect=AssertionError("materialized")), \
                     patch.object(VideoFromComponents, "get_color_space", return_value="sRGB", create=True):
                    result = media.sample_asset(video)
                self.assertEqual(result.frames[0].image.getpixel((0, 0)), (255, 255, 255))
                self.assertEqual(result.frames[-1].image.getpixel((0, 0)), (255, 0, 0))
                self.assertEqual([f.timestamp_s for f in result.frames], [0., .75])

    def test_current_encoding_metadata_keeps_existing_audio_and_offline_no_track(self):
        audio = {"waveform": torch.zeros((1, 1, 16000)), "sample_rate": 16000}
        for chroma in (None, "4:2:0", "4:2:2", "4:4:4"):
            with self.subTest(chroma=chroma), \
                 patch.object(VideoFromComponents, "get_components", side_effect=AssertionError("materialized")), \
                 patch.object(speech, "SpeechASRClient", side_effect=AssertionError("transport")):
                self.assertIsNone(speech._video_payload(self.component(chroma=chroma), 0., 0.))
                route, *payload = speech._video_payload(self.component(chroma=chroma, audio=audio), .25, .5)
                self.assertEqual(route, "/v1/audio/transcribe")
                self.assertEqual(tuple(payload), speech._audio_payload(audio, .25, .5))

    def test_unknown_layout_still_fails_before_media_or_service_access(self):
        for mutation in ("extra", "incomplete"):
            video = self.component()
            if mutation == "extra":
                vars(video)["_VideoFromComponents__future_transform"] = object()
            else:
                del vars(video)["_VideoFromComponents__color_space"]
            for reader, error in ((media.video_info, sp.StrataProviderError),
                                  (adapter.sample_input, sp.StrataProviderError),
                                  (lambda value: speech._video_payload(value, 0., 0.), speech.SpeechReferenceError)):
                with self.subTest(mutation=mutation, reader=reader), self.assertRaises(error):
                    reader(video)

    def test_hdr_components_still_require_color_conversion(self):
        video = self.component(chroma="4:4:4")
        vars(video)["_VideoFromComponents__color_space"] = "HDR PQ"
        with patch.object(VideoFromComponents, "get_color_space", return_value="HDR PQ", create=True), \
             patch.object(adapter, "sample_tensor", side_effect=AssertionError("HDR sampled as sRGB")), \
             self.assertRaisesRegex(sp.StrataProviderError, "color space"):
            media.sample_asset(video)


if __name__ == "__main__":
    unittest.main()
