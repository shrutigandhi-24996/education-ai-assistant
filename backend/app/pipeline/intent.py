import json
import re
from pathlib import Path

from backend.app.config import settings

INTENTS: list[str] = [
    "admission_query",
    "contact_info",
    "course_info",
    "event_info",
    "exam_schedule",
    "faculty_info",
    "fee_structure",
    "general_greeting",
    "infrastructure_info",
    "placement_info",
    "result_query",
]

# Keyword signals per intent (used for multi-intent detection and as a fallback).
INTENT_SIGNALS: dict[str, list[str]] = {
    "general_greeting": ["hello", "hi", "hey", "good morning", "good afternoon"],
    "fee_structure": ["fee", "fees", "tuition", "cost", "payment"],
    "admission_query": ["admission", "apply", "eligibility", "enroll", "merit", "application"],
    "course_info": ["course", "courses", "semester", "sem-", "syllabus", "program", "subject", "curriculum"],
    "exam_schedule": ["exam", "timetable", "midterm", "practical exam", "examination", "question paper"],
    "result_query": ["result", "marks", "grade", "cgpa", "score"],
    "placement_info": ["placement", "recruiter", "company", "package", "career", "internship", "job"],
    "faculty_info": ["faculty", "professor", "teacher", "hod", "head of department"],
    "event_info": ["event", "fest", "workshop", "seminar", "notice", "celebration"],
    "infrastructure_info": ["lab", "laboratory", "library", "hostel", "campus", "facility", "canteen", "playground"],
    "contact_info": ["contact", "phone", "email", "address", "whatsapp", "call us"],
}

_CONJUNCTIONS = re.compile(r"\b(and|also|plus|as well as)\b|[,;]|\?\s*\w")


class IntentClassifier:
    def __init__(self) -> None:
        self.model = None
        self.tokenizer = None
        self.labels: list[str] = INTENTS
        self._load()

    def _load(self) -> None:
        model_dir = settings.intent_model_dir
        if not (model_dir / "config.json").exists():
            return
        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except ImportError:
            return
        self.tokenizer = AutoTokenizer.from_pretrained(model_dir)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_dir)
        labels_path = model_dir / "label_map.json"
        if labels_path.exists():
            with open(labels_path, encoding="utf-8") as f:
                self.labels = json.load(f)["labels"]
        self.model.eval()
        device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model.to(device)
        self.device = device

    @property
    def ready(self) -> bool:
        return self.model is not None and self.tokenizer is not None

    def predict(self, text: str) -> tuple[str, float]:
        if not self.ready:
            return self._keyword_fallback(text), self._keyword_confidence(text)
        import torch

        enc = self.tokenizer(
            text,
            truncation=True,
            padding=True,
            max_length=settings.max_seq_length,
            return_tensors="pt",
        )
        enc = {k: v.to(self.device) for k, v in enc.items()}
        with torch.no_grad():
            logits = self.model(**enc).logits
            probs = torch.softmax(logits, dim=-1)[0]
            idx = int(torch.argmax(probs).item())
            return self.labels[idx], float(probs[idx].item())

    def predict_multi(self, text: str) -> list[tuple[str, float]]:
        """Return one or more intents present in the query (multi-intent).

        Combines keyword signals (to find co-occurring intents) with the model's
        top prediction. Conservative: only reports >1 intent when there is both a
        conjunction/multiple-question signal and 2+ distinct intent groups.
        """
        keyword_intents = self._detect_keyword_intents(text)
        primary, confidence = self.predict(text)

        ordered: list[tuple[str, float]] = []
        seen: set[str] = set()

        has_split = bool(_CONJUNCTIONS.search(text.lower())) or text.count("?") > 1
        if settings.multi_intent_enabled and has_split and len(keyword_intents) >= 2:
            for name in keyword_intents:
                if name not in seen and name != "general_greeting":
                    ordered.append((name, 0.75))
                    seen.add(name)

        if not ordered:
            ordered.append((primary, confidence))
            seen.add(primary)

        return ordered[: settings.multi_intent_max]

    def _detect_keyword_intents(self, text: str) -> list[str]:
        t = text.lower()
        found: list[str] = []
        for intent, signals in INTENT_SIGNALS.items():
            if intent == "general_greeting":
                continue
            for kw in signals:
                if kw in t:
                    found.append(intent)
                    break
        return found

    def _keyword_confidence(self, text: str) -> float:
        """Heuristic confidence used when the trained model is unavailable.

        Low value signals a possible unseen / out-of-scope query so the
        orchestrator can route to web search instead of guessing.
        """
        matches = self._detect_keyword_intents(text)
        if self._is_greeting_text(text):
            return 0.9
        if not matches:
            return 0.2
        return 0.6 if len(matches) == 1 else 0.55

    @staticmethod
    def _is_greeting_text(text: str) -> bool:
        t = text.lower().strip(" .!?")
        return t in {"hello", "hi", "hey", "hello..", "good morning", "good afternoon"}

    def _keyword_fallback(self, text: str) -> str:
        if self._is_greeting_text(text):
            return "general_greeting"
        # Priority order so more specific intents win over generic ones.
        priority = [
            "fee_structure",
            "admission_query",
            "exam_schedule",
            "result_query",
            "placement_info",
            "faculty_info",
            "event_info",
            "infrastructure_info",
            "contact_info",
            "course_info",
        ]
        matched = set(self._detect_keyword_intents(text))
        for intent in priority:
            if intent in matched:
                return intent
        # No known signal -> unseen / out-of-scope intent.
        return "unknown"
