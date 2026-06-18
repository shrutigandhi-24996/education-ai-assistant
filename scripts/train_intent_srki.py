"""Train DistilBERT intent classifier on SRKI data (GPU if available)."""
import json
import sys
from pathlib import Path

import numpy as np
import torch
from datasets import Dataset
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    Trainer,
    TrainingArguments,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.config import settings  # noqa: E402

PROCESSED = ROOT / "data" / "processed"


def load_split(name: str) -> list[dict]:
    path = PROCESSED / f"srki_{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Run prepare_srki_data.py first. Missing {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    return {
        "accuracy": accuracy_score(labels, preds),
        "precision": precision_score(labels, preds, average="weighted", zero_division=0),
        "recall": recall_score(labels, preds, average="weighted", zero_division=0),
        "f1": f1_score(labels, preds, average="weighted", zero_division=0),
    }


def main() -> None:
    train_rows = load_split("train")
    val_rows = load_split("val")

    with open(PROCESSED / "label_map.json", encoding="utf-8") as f:
        labels = json.load(f)["labels"]
    label2id = {l: i for i, l in enumerate(labels)}

    def to_dataset(rows: list[dict]) -> Dataset:
        return Dataset.from_dict(
            {
                "text": [r["text"] for r in rows],
                "label": [label2id[r["intent"]] for r in rows],
            }
        )

    train_ds = to_dataset(train_rows)
    val_ds = to_dataset(val_rows)

    tokenizer = AutoTokenizer.from_pretrained(settings.intent_base_model)
    model = AutoModelForSequenceClassification.from_pretrained(
        settings.intent_base_model,
        num_labels=len(labels),
        id2label={i: l for i, l in enumerate(labels)},
        label2id=label2id,
    )

    def tokenize(batch):
        return tokenizer(
            batch["text"],
            truncation=True,
            padding="max_length",
            max_length=settings.max_seq_length,
        )

    train_ds = train_ds.map(tokenize, batched=True)
    val_ds = val_ds.map(tokenize, batched=True)

    use_cuda = torch.cuda.is_available()
    batch_size = 16 if use_cuda else 4
    print(f"Device: {'cuda' if use_cuda else 'cpu'}, batch_size={batch_size}")

    out_dir = settings.intent_model_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    args = TrainingArguments(
        output_dir=str(out_dir / "checkpoints"),
        num_train_epochs=3,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size,
        learning_rate=2e-5,
        weight_decay=0.01,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1",
        logging_steps=100,
        fp16=use_cuda,
        report_to="none",
    )

    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        tokenizer=tokenizer,
        compute_metrics=compute_metrics,
    )
    trainer.train()
    trainer.save_model(str(out_dir))
    tokenizer.save_pretrained(str(out_dir))
    with open(out_dir / "label_map.json", "w", encoding="utf-8") as f:
        json.dump({"labels": labels}, f, indent=2)
    print(f"Saved intent model to {out_dir}")


if __name__ == "__main__":
    main()
