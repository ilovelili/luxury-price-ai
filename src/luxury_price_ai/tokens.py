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
        "CHANEL 22",
        "CHANEL22",
        "シャネル19",
        "CHANEL 19",
        "CHANEL19",
        "クラシックフラップ",
        "CLASSIC FLAP",
        "CLASSIC DOUBLE FLAP",
        "DOUBLE FLAP",
        "ダブルフラップ",
        "シングルフラップ",
        "BOY",
        "COCO HANDLE",
        "GST",
        "バニティ",
        "ミニマトラッセ",
        "ネヴァーフル",
        "NEVERFULL",
        "アルマ",
        "スピーディ",
        "オンザゴー",
        "キーポル",
        "バーキン",
        "ケリー",
        "コンスタンス",
        "ピコタン",
        "エヴリン",
    ],
    "materials": [
        "キャビアスキン",
        "CAVIAR LEATHER",
        "CAVIAR SKIN",
        "CAVIAR",
        "ラムスキン",
        "LAMBSKIN",
        "LAMB SKIN",
        "グレインドカーフ",
        "カーフスキン",
        "リザード",
        "ジャージ",
        "エナメル",
        "ツイード",
        "カーフ",
        "レザー",
        "ナイロン",
        "キャンバス",
        "モノグラム",
        "ダミエ",
        "エピ",
        "タイガ",
        "ヴェルニ",
        "トゴ",
        "エプソン",
        "トリヨンクレマンス",
        "ボックスカーフ",
    ],
    "colors": [
        "黒",
        "ブラック",
        "BLACK",
        "白",
        "ホワイト",
        "WHITE",
        "赤",
        "レッド",
        "RED",
        "ネイビー",
        "NAVY",
        "ベージュ",
        "BEIGE",
        "ピンク",
        "PINK",
        "ブラウン",
        "茶",
        "BROWN",
        "グレー",
        "GRAY",
        "GREY",
        "グリーン",
        "GREEN",
        "青",
        "ブルー",
        "BLUE",
        "エトゥープ",
        "ナチュラル",
        "アイボリー",
    ],
    "hardware": [
        "ゴールド金具",
        "GOLD HARDWARE",
        "シルバー金具",
        "SILVER HARDWARE",
        "ソーブラック",
        "アンティーク金具",
        "金具",
        "GP",
        "SV",
        "パラジウム金具",
        "シャンパンゴールド金具",
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
        "ストラップ",
        "クロシェット",
        "カデナ",
    ],
    "sizes": [
        "ミニ",
        "スモール",
        "ミディアム",
        "ラージ",
        "PM",
        "MM",
        "GM",
        "25",
        "28",
        "30",
        "32",
        "35",
        "40",
    ],
}

WORD_RE = re.compile(r"[A-Za-z0-9]+|[\u3040-\u30ff\u3400-\u9fff]{2,}")


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    return value.strip().upper().replace("　", " ")


def canonical_token(value: str | None) -> str:
    text = normalize_text(value)
    aliases = {
        "BLACK": "黒",
        "ブラック": "黒",
        "WHITE": "白",
        "ホワイト": "白",
        "RED": "赤",
        "レッド": "赤",
        "BLUE": "青",
        "ブルー": "青",
        "GREEN": "グリーン",
        "ゴールド": "ゴールド金具",
        "GOLD HARDWARE": "ゴールド金具",
        "GP": "ゴールド金具",
        "シルバー": "シルバー金具",
        "SILVER HARDWARE": "シルバー金具",
        "SV": "シルバー金具",
        "CHANEL22": "シャネル22",
        "CHANEL 22": "シャネル22",
        "CHANEL19": "シャネル19",
        "CHANEL 19": "シャネル19",
        "NEVERFULL": "ネヴァーフル",
        "CLASSIC FLAP": "マトラッセ",
        "CLASSIC DOUBLE FLAP": "ダブルフラップ",
        "DOUBLE FLAP": "ダブルフラップ",
        "BOY": "ボーイ",
        "BOY CHANEL": "ボーイ",
        "COCO HANDLE": "ココハンドル",
        "CAVIAR LEATHER": "キャビアスキン",
        "CAVIAR SKIN": "キャビアスキン",
        "CAVIAR": "キャビアスキン",
        "LAMBSKIN": "ラムスキン",
        "LAMB SKIN": "ラムスキン",
    }
    return aliases.get(text, text)


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
        words=dedupe([*found["sizes"], *words])[:30],
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
        values.update(canonical_token(token) for token in group)
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
