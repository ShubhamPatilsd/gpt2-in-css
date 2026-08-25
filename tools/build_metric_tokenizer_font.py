#!/usr/bin/env python3
"""Build OpenType embedding fonts for CSS-only GPT-2 tokenization.

The font applies the real GPT-2 BPE merges needed by the configured corpus,
keeps one resulting token by position with contextual GSUB, and encodes either
one embedding coordinate or the token ID itself as the only non-zero glyph
advance. CSS recovers the value from rendered width using 1px text at 64
units/em.

The default build is a small feasibility corpus; ``--full`` includes GPT-2's
complete merge table and the token IDs accepted by the existing CSS demo.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

from build_pretrained_gpt2 import (
    CHECKPOINT_DIR,
    Gpt2Tokenizer,
    load_torch_legacy,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "experiments"
UNITS_PER_EM = 64
EMBEDDING_OFFSET = 0.1
EMBEDDING_SCALE = 160_000
TOKEN_ID_BASE = 32_767
DEFAULT_CORPUS = (
    "Hello world!",
    "Hello",
    "The dog",
    "CSS is computing",
)


def trace_merges(tokenizer: Gpt2Tokenizer, text: str) -> set[tuple[int, str, str, str]]:
    traced: set[tuple[int, str, str, str]] = set()
    for match in tokenizer.pattern.findall(text):
        encoded = "".join(
            tokenizer.byte_encoder[byte] for byte in match.encode("utf-8")
        )
        pieces = list(encoded)
        while len(pieces) > 1:
            candidates = [
                (tokenizer.merge_ranks.get((pieces[index], pieces[index + 1])), index)
                for index in range(len(pieces) - 1)
            ]
            valid = [(rank, index) for rank, index in candidates if rank is not None]
            if not valid:
                break
            rank, best = min(valid)
            left, right = pieces[best], pieces[best + 1]
            merged = left + right
            traced.add((rank, left, right, merged))
            pieces = pieces[:best] + [merged] + pieces[best + 2 :]
    return traced


def corpus_token_ids(tokenizer: Gpt2Tokenizer, corpus: tuple[str, ...]) -> list[int]:
    return sorted({token for text in corpus for token in tokenizer.encode(text)})


def glyph_name(token_id: int) -> str:
    return f"g{token_id}"


def independent_merge_batches(
    merges: list[tuple[int, str, str, str]],
) -> list[list[tuple[int, str, str, str]]]:
    """Batch consecutive rules whose input/output glyph sets are disjoint.

    Such rules cannot compete for a glyph or consume another rule's output, so
    applying them in one left-to-right GSUB lookup is equivalent to applying
    their rank-ordered lookups separately.
    """
    batches: list[list[tuple[int, str, str, str]]] = []
    batch: list[tuple[int, str, str, str]] = []
    used: set[str] = set()
    for merge in merges:
        glyphs = set(merge[1:])
        if used & glyphs:
            batches.append(batch)
            batch = []
            used = set()
        batch.append(merge)
        used.update(glyphs)
    if batch:
        batches.append(batch)
    return batches


def empty_glyph():
    return TTGlyphPen(None).glyph()


def build_font(
    tokenizer: Gpt2Tokenizer,
    embeddings,
    corpus: tuple[str, ...],
    positions: int,
    dimension: int | None,
    destination: Path,
    full: bool = False,
    token_ids: bool = False,
    token_id_part: int = 0,
) -> None:
    if full:
        merges = sorted(
            (rank, left, right, left + right)
            for (left, right), rank in tokenizer.merge_ranks.items()
        )
        all_token_ids = sorted(tokenizer.inverse_vocab)
    else:
        merges = sorted(
            {merge for text in corpus for merge in trace_merges(tokenizer, text)}
        )
        all_token_ids = corpus_token_ids(tokenizer, corpus)

    participating_ids = set(all_token_ids)
    for _, left, right, merged in merges:
        participating_ids.update(
            (tokenizer.vocab[left], tokenizer.vocab[right], tokenizer.vocab[merged])
        )

    cmap: dict[int, str] = {}
    input_characters = (
        [chr(codepoint) for codepoint in range(32, 127)] + ["\t", "\n", "\r"]
        if full
        else list("".join(corpus))
    )
    for character in input_characters:
        raw = character.encode("utf-8")
        if len(raw) != 1:
            raise ValueError("prototype corpus currently supports single-byte characters")
        encoded = tokenizer.byte_encoder[raw[0]]
        token_id = tokenizer.vocab[encoded]
        participating_ids.add(token_id)
        cmap[ord(character)] = glyph_name(token_id)

    ordered_ids = sorted(participating_ids)
    glyph_order = [".notdef", "zero"]
    glyph_order.extend(glyph_name(token_id) for token_id in ordered_ids)

    widths = {name: 0 for name in glyph_order}
    for token_id in ordered_ids:
        if token_ids:
            # HarfBuzz exposes advances above 32,767 as signed values. Two
            # base-32,767 digits keep every measurement positive and exact.
            digit = (token_id // (TOKEN_ID_BASE**token_id_part)) % TOKEN_ID_BASE
            # The +1 keeps a zero digit distinguishable from a missing token.
            widths[glyph_name(token_id)] = digit + 1
        else:
            assert dimension is not None
            widths[glyph_name(token_id)] = round(
                (float(embeddings[token_id, dimension]) + EMBEDDING_OFFSET)
                * EMBEDDING_SCALE
            ) + 1

    font = FontBuilder(UNITS_PER_EM, isTTF=True)
    font.setupGlyphOrder(glyph_order)
    font.setupCharacterMap(cmap)
    font.setupGlyf({name: empty_glyph() for name in glyph_order})
    font.setupHorizontalMetrics({name: (width, 0) for name, width in widths.items()})
    font.setupHorizontalHeader(ascent=UNITS_PER_EM, descent=0)
    font.setupNameTable(
        {
            "familyName": (
                f"GPT2TokenID{token_id_part}"
                if token_ids
                else f"GPT2Embedding{dimension}"
            ),
            "styleName": "Regular",
            "uniqueFontIdentifier": (
                f"gpt2-css-token-id-{token_id_part}"
                if token_ids
                else f"gpt2-css-embedding-{dimension}"
            ),
            "fullName": (
                f"GPT2 Token ID part {token_id_part}"
                if token_ids
                else f"GPT2 Embedding Coordinate {dimension}"
            ),
            "psName": (
                f"GPT2TokenID{token_id_part}"
                if token_ids
                else f"GPT2Embedding{dimension}"
            ),
        }
    )
    font.setupOS2(
        sTypoAscender=UNITS_PER_EM,
        sTypoDescender=0,
        usWinAscent=UNITS_PER_EM,
        usWinDescent=0,
    )
    font.setupPost()
    font.setupMaxp()

    all_token_class = " ".join(glyph_name(token_id) for token_id in all_token_ids)
    token_chunks = [
        all_token_ids[start : start + 1024]
        for start in range(0, len(all_token_ids), 1024)
    ]
    token_chunk_classes = "\n".join(
        f"@TOKENS{index} = ["
        + " ".join(glyph_name(token_id) for token_id in chunk)
        + "];"
        for index, chunk in enumerate(token_chunks)
    )
    merge_batches = independent_merge_batches(merges)
    merge_rules = "\n".join(
        f"  lookup mergeBatch{batch_index} useExtension {{\n"
        + "\n".join(
            f"    sub {glyph_name(tokenizer.vocab[left])} "
            f"{glyph_name(tokenizer.vocab[right])} by "
            f"{glyph_name(tokenizer.vocab[merged])};"
            for _, left, right, merged in batch
        )
        + f"\n  }} mergeBatch{batch_index};"
        for batch_index, batch in enumerate(merge_batches)
    )
    position_lookups: list[str] = []
    feature_blocks: list[str] = []
    for position in range(positions):
        tag = f"p{position:03d}"
        references: list[str] = []
        if position:
            preceding = " ".join("@SEEN" for _ in range(position))
            for index in range(len(token_chunks)):
                lookup = f"eraseBefore{position}c{index}"
                position_lookups.append(
                    f"lookup {lookup} useExtension {{\n"
                    f"  ignore sub {preceding} @TOKENS{index}';\n"
                    f"  sub @TOKENS{index}' by zero;\n"
                    f"}} {lookup};"
                )
                references.append(f"  lookup {lookup};")
        following_context = " ".join("@SEEN" for _ in range(position + 1))
        for index in range(len(token_chunks)):
            lookup = f"eraseAfter{position}c{index}"
            position_lookups.append(
                f"lookup {lookup} useExtension {{\n"
                f"  sub {following_context} @TOKENS{index}' by zero;\n"
                f"}} {lookup};"
            )
            references.append(f"  lookup {lookup};")
        feature_blocks.append(
            f"feature {tag} {{\n" + "\n".join(references) + f"\n}} {tag};"
        )
    feature_rules = "\n".join(feature_blocks)
    features = f"""
languagesystem DFLT dflt;
languagesystem latn dflt;
@ALLTOKENS = [{all_token_class}];
{token_chunk_classes}
@SEEN = [{all_token_class} zero];
feature rlig {{
{merge_rules}
}} rlig;
{"\n".join(position_lookups)}
{feature_rules}
"""
    addOpenTypeFeaturesFromString(font.font, features)
    destination.parent.mkdir(parents=True, exist_ok=True)
    font.save(destination)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--positions", type=int, default=4)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--full", action="store_true")
    parser.add_argument(
        "--token-ids",
        action="store_true",
        help="encode token_id + 1 instead of an embedding coordinate",
    )
    parser.add_argument(
        "--token-id-part",
        type=int,
        choices=(0, 1),
        action="append",
        help="base-32767 token-ID digit to build; defaults to both digits",
    )
    parser.add_argument("--dimension", type=int, choices=(0, 1), action="append")
    args = parser.parse_args()

    tokenizer = Gpt2Tokenizer(
        CHECKPOINT_DIR / "vocab.json", CHECKPOINT_DIR / "merges.txt"
    )
    suffix = ""
    state = None
    if not args.token_ids:
        state = load_torch_legacy(CHECKPOINT_DIR / "pytorch_model.bin")
    if args.full:
        suffix = "-full"
    if args.token_ids:
        for part in args.token_id_part or range(2):
            destination = args.output / f"gpt2-token-id-{part}{suffix}.ttf"
            build_font(
                tokenizer,
                None,
                DEFAULT_CORPUS,
                args.positions,
                None,
                destination,
                full=args.full,
                token_ids=True,
                token_id_part=part,
            )
            print(destination)
        return
    assert state is not None
    for dimension in args.dimension or range(2):
        destination = args.output / f"gpt2-embedding-{dimension}{suffix}.ttf"
        build_font(
            tokenizer,
            state["transformer.wte.weight"],
            DEFAULT_CORPUS,
            args.positions,
            dimension,
            destination,
            full=args.full,
        )
        print(destination)


if __name__ == "__main__":
    main()
