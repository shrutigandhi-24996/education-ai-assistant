"""Structured clarification options for the chat frontend."""

from __future__ import annotations

from typing import Any


def build_clarification_options(
    institution_needed: dict[str, list[dict[str, str]]] | None = None,
    course_needed: dict[str, list[dict[str, str]]] | None = None,
    web_token: str | None = None,
    web_options: list[dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    options: list[dict[str, Any]] = []
    if institution_needed:
        for term, opts in institution_needed.items():
            for i, opt in enumerate(opts, 1):
                options.append(
                    {
                        "kind": "institution",
                        "term": term,
                        "label": opt["label"],
                        "value": str(i),
                        "resolution": opt["resolution"],
                    }
                )
    if course_needed:
        for term, opts in course_needed.items():
            for i, opt in enumerate(opts, 1):
                options.append(
                    {
                        "kind": "course",
                        "term": term,
                        "label": opt["label"],
                        "value": str(i),
                        "resolution": opt["resolution"],
                    }
                )
    if web_token and web_options:
        for i, opt in enumerate(web_options, 1):
            options.append(
                {
                    "kind": "web_institution",
                    "term": web_token,
                    "label": opt["label"],
                    "value": str(i),
                    "resolution": opt["resolution"],
                }
            )
    return options
