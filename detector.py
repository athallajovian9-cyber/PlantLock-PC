"""Planting detection.

Primary engine: CLIP ViT-B/32 zero-shot classification — real judgment on
whether the camera shows a person planting. Falls back to a motion+green
heuristic if the model stack is unavailable (labeled honestly in the UI).
"""
import threading
import time

PLANT_PROMPTS = [
    "a photo of a person planting a young tree or seedling into soil",
    "hands digging dirt and planting a sapling outdoors",
    "someone gardening, putting a plant into the ground",
]
NOT_PROMPTS = [
    "a person sitting indoors using a computer",
    "a person looking at a phone in a room",
    "someone watching a screen, no plants, indoors",
    "an empty room with no person",
]


class ClipEngine:
    name = "CLIP ViT-B/32 zero-shot"

    def __init__(self):
        import torch
        from transformers import CLIPModel, CLIPProcessor
        self.torch = torch
        self.model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
        self.proc = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
        self.model.eval()
        texts = PLANT_PROMPTS + NOT_PROMPTS
        inputs = self.proc(text=texts, return_tensors="pt", padding=True)
        with torch.no_grad():
            feats = self._encode(input_ids=inputs["input_ids"],
                                 attention_mask=inputs["attention_mask"])
            feats = feats / feats.norm(dim=-1, keepdim=True)
        self.text_feats = feats
        self.plant_n = len(PLANT_PROMPTS)

    def _encode(self, **kw):
        # version-proof: raw submodules (transformers 5.x changed get_*_features)
        import numpy as np
        t = self.model.text_model(**kw)
        return self.model.text_projection(t.pooler_output)

    def score(self, frame_rgb) -> float:
        import numpy as np
        from PIL import Image
        img = Image.fromarray(frame_rgb)
        inputs = self.proc(images=img, return_tensors="pt")
        with self.torch.no_grad():
            v = self.model.vision_model(pixel_values=inputs["pixel_values"])
            vf = self.model.visual_projection(v.pooler_output)
            vf = vf / vf.norm(dim=-1, keepdim=True)
            sims = (vf @ self.text_feats.T)[0] * 100.0
            probs = self.torch.softmax(sims, dim=-1).tolist()
        return float(sum(probs[: self.plant_n]))


class MotionEngine:
    """Honest fallback: motion energy + greenery presence, no false 'AI' claims."""
    name = "motion heuristic (CLIP unavailable)"

    def __init__(self):
        self.prev = None

    def score(self, frame_rgb) -> float:
        import cv2
        import numpy as np
        gray = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2GRAY)
        small = cv2.resize(gray, (160, 120))
        if self.prev is None:
            self.prev = small
            return 0.0
        motion = float(np.mean(cv2.absdiff(small, self.prev)))
        self.prev = small
        hsv = cv2.cvtColor(cv2.resize(frame_rgb, (160, 120)), cv2.COLOR_RGB2HSV)
        green = float(np.mean((hsv[:, :, 1] > 50) & (hsv[:, :, 0] >= 35) & (hsv[:, :, 0] <= 95)))
        return max(0.0, min(1.0, motion / 14.0 * 0.6 + green * 4.0 * 0.4))


class PlantingDetector:
    """Owns the camera + classification loop. Publishes verdicts thread-safely."""

    def __init__(self, use_clip: bool = True):
        self.engine = None
        self.engine_error = ""
        self.cap = None
        self.running = False
        self.latest_frame = None          # RGB ndarray
        self.verdict = {"score": 0.0, "planting": False, "t": 0.0}
        self.lock = threading.Lock()
        self._score_thread = None

        if use_clip:
            try:
                self.engine = ClipEngine()
            except Exception as e:
                self.engine_error = str(e)
        if self.engine is None:
            self.engine = MotionEngine()

    def start(self) -> bool:
        import cv2
        self.cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not self.cap.isOpened():
            self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            return False
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.running = True
        threading.Thread(target=self._capture_loop, daemon=True).start()
        self._score_thread = threading.Thread(target=self._score_loop, daemon=True)
        self._score_thread.start()
        return True

    def stop(self):
        self.running = False
        if self.cap is not None:
            self.cap.release()
            self.cap = None

    def _capture_loop(self):
        import cv2
        while self.running:
            ok, frame = self.cap.read()
            if not ok:
                time.sleep(0.05)
                continue
            with self.lock:
                self.latest_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            time.sleep(0.03)

    def _score_loop(self):
        while self.running:
            with self.lock:
                frame = None if self.latest_frame is None else self.latest_frame.copy()
            if frame is None:
                time.sleep(0.1)
                continue
            try:
                s = self.engine.score(frame)
            except Exception:
                s = 0.0
            with self.lock:
                self.verdict = {"score": s, "planting": s >= 0.62, "t": time.time()}
            time.sleep(1.0)

    def snapshot(self):
        with self.lock:
            return (None if self.latest_frame is None else self.latest_frame.copy(),
                    dict(self.verdict))
