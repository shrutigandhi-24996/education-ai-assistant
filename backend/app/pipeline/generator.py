"""Optional grounded response generator (FLAN-T5).

The generator is **strictly grounded**: it is only ever given retrieved context
and instructed to answer from that context alone. If the context does not
contain the answer it must say so. This is the anti-hallucination guardrail for
the generative stage of the hybrid pipeline. Disabled by default
(``settings.use_generator``) because it requires the transformers model weights.
"""
from __future__ import annotations

from backend.app.config import settings

_NO_ANSWER = "NOT_IN_CONTEXT"

_PROMPT = (
    "You are SRKI College's assistant. Answer the question using ONLY the context "
    "below. Do not invent facts, numbers, dates, fees, or names. If the answer is "
    "not in the context, reply exactly with '{no_answer}'.\n\n"
    "Context:\n{context}\n\nQuestion: {question}\nAnswer:"
)


class GroundedGenerator:
    def __init__(self) -> None:
        self.model = None
        self.tokenizer = None
        self.device = "cpu"
        if settings.use_generator:
            self._load()

    def _load(self) -> None:
        try:
            import torch
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        except ImportError:
            return
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(settings.generator_model)
            self.model = AutoModelForSeq2SeqLM.from_pretrained(settings.generator_model)
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            self.model.to(self.device)
            self.model.eval()
        except Exception:
            self.model = None
            self.tokenizer = None

    @property
    def ready(self) -> bool:
        return self.model is not None and self.tokenizer is not None

    def generate(self, question: str, context: str) -> str | None:
        """Return a grounded answer, or None if the model can't answer from context."""
        if not self.ready or not context.strip():
            return None
        import torch

        context = context[: settings.generator_max_input_chars]
        prompt = _PROMPT.format(no_answer=_NO_ANSWER, context=context, question=question)
        enc = self.tokenizer(
            prompt, return_tensors="pt", truncation=True, max_length=1024
        ).to(self.device)
        with torch.no_grad():
            out = self.model.generate(
                **enc,
                max_new_tokens=settings.generator_max_new_tokens,
                num_beams=4,
                no_repeat_ngram_size=3,
            )
        answer = self.tokenizer.decode(out[0], skip_special_tokens=True).strip()
        if not answer or _NO_ANSWER in answer:
            return None
        return answer
