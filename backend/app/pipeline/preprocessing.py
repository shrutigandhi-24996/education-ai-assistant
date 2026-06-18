import re


def preprocess(text: str) -> str:
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\.{2,}", ".", text)
    return text
