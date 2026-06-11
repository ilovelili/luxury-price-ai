from __future__ import annotations

import re

from luxury_price_ai.models import ExtractedTokens


TOKEN_DICTIONARY = {
    "models": [
        "マトラッセ",
        "ココハンドル",
        "ボーイシャネル",
        "ボーイ",
        "チェーンウォレット",
        "シャネル22",
        "CHANEL22",
        "GST",
        "バニティ",
        "ミニマトラッセ",
    ],
    "materials": [
        "キャビアスキン",
        "ラムスキン",
        "リザード",
        "ジャージ",
        "エナメル",
        "ツイード",
        "カーフ",
        "レザー",
        "ナイロン",
        "キャンバス",
    ],
    "colors": [
        "黒",
        "ブラック",
        "白",
        "ホワイト",
        "赤",
        "レッド",
        "ネイビー",
        "ベージュ",
        "ピンク",
        "ブラウン",
        "茶",
        "グレー",
        "グリーン",
        "青",
        "ブルー",
    ],
    "hardware": [
        "ゴールド金具",
        "シルバー金具",
        "ソーブラック",
        "アンティーク金具",
        "金具",
    ],
    "accessories": [
        "ギャランティカード",
        "シリアルシール",
        "シリアルプレート",
        "ICプレート",
        "箱",
        "保存袋",
        "カード",
        "シール",
    ],
}

WORD_RE = re.compile(r"[A-Za-z0-9]+|[\u3040-\u30ff\u3400-\u9fff]{2,}")


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    return value.strip().upper().replace("　", " ")


def extract_tokens(title: str | None) -> ExtractedTokens:
    text = normalize_text(title)
    found: dict[str, list[str]] = {}

    for group, tokens in TOKEN_DICTIONARY.items():
        matches = []
        for token in tokens:
            if normalize_text(token) in text:
                matches.append(token)
        found[group] = dedupe(matches)

    words = [
        word
        for word in WORD_RE.findall(text)
        if len(word) >= 2 and word not in {"CHANEL", "シャネル", "バッグ"}
    ]

    return ExtractedTokens(
        models=found["models"],
        materials=found["materials"],
        colors=found["colors"],
        hardware=found["hardware"],
        accessories=found["accessories"],
        words=dedupe(words)[:30],
    )


def token_set(tokens: ExtractedTokens) -> set[str]:
    values: set[str] = set()
    for group in (
        tokens.models,
        tokens.materials,
        tokens.colors,
        tokens.hardware,
        tokens.accessories,
    ):
        values.update(normalize_text(token) for token in group)
    return values


def dedupe(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        key = normalize_text(value)
        if key and key not in seen:
            seen.add(key)
            result.append(value)
    return result
