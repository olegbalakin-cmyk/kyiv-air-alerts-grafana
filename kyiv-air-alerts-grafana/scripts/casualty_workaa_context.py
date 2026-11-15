"""Work AA reviewed sentence/context helpers; extracted without Work Z authorization code.
Only process transient source text in memory. Never persist full HTML/text.
All output is privacy-screened, bounded and unverified.
"""
import hashlib
import re

def sha_data(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def withhold_unsafe_excerpts(card):
    """Conservative evidence-output filter; Work J remains the only extractor."""
    original = list(card.get("excerpts", []))
    safe = []
    for excerpt in original:
        snippet = excerpt.get("text", "") if isinstance(excerpt, dict) else ""
        if not isinstance(snippet, str) or not snippet or len(snippet) > 170:
            continue
        # Work J already redacts email/phone. Drop entire quote when other
        # personal details or unreviewed proper names could remain.
        tail = " ".join(snippet.split()[1:])
        if (re.search(r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}", snippet)
                or re.search(r"\+?\d[\d ()-]{9,}\d", snippet)
                or re.search(r"\b(?:вулиця|вул\.?|будинок|буд\.?|квартира|кв\.?|"
                             r"паспорт|адреса|телефон|прізвище|ім'я|по батькові)\b", snippet, re.I)
                or re.search(r"\b[А-ЯЄІЇҐ][а-яєіїґ'’-]{2,}\b", tail)):
            continue
        safe.append(excerpt)
    card["excerpts"] = safe
    if len(safe) != len(original):
        card["reasons"] = sorted(set(card.get("reasons", []) + [
            "PRIVACY_REVIEW_EXCERPT_WITHHELD"]))
    return card



def _review_sentences(text: str) -> list[str]:
    """Never split a legal abbreviation such as '(ч. 2 ст. 438)' into a quote."""
    parts = re.split(r"(?<=[.!?])\s+", " ".join(text.split()))
    result, pending = [], ""
    for part in parts:
        pending = (pending + " " + part).strip() if pending else part
        if (pending.count("(") > pending.count(")")
                or re.search(r"\b(?:ч|ст|р|ім|п|вул)\.$", pending, re.I)):
            continue
        result.append(pending)
        pending = ""
    if pending:
        result.append(pending)
    return result


def retain_incident_review_clues(text: str) -> dict:
    """Select bounded, complete, redacted context; never verify event identity.

    Segments are article-reading hints, not proven incident links. Long sentences
    retain only a hash and CONTEXT_INCOMPLETE, never a misleading partial quote.
    """
    result = {
        "status": "INSUFFICIENT_EVIDENCE",
        "attack_identity_verified": False, "attack_date_verified": None,
        "attack_time_verified": None, "locality_verified": None,
        "struck_object_verified": None, "direct_two_to_three_update_proven": False,
        "independent_police_link_proven": False,
        "chronology_is_source_sentence_order_only": True,
        "evidence_mentions": [],
    }
    if not isinstance(text, str) or not text.strip():
        return result
    patterns = (
        ("DATE_MENTION_NOT_ATTACK_DATE", r"\b(?:[12]?\d|3[01])\s+(?:січня|лютого|березня|квітня|травня|червня|липня|серпня|вересня|жовтня|листопада|грудня)\b|\b\d{1,2}[./]\d{1,2}[./]\d{2,4}\b"),
        ("PLACE_MENTION_NOT_LOCALITY_PROOF", r"\b(?:у|в|на)\s+запоріжжі\b|\bзапоріжжя\b|\bзапорізьк\w*\s+област\w*\b"),
        ("TIME_MENTION_NOT_ATTACK_TIME", r"\b(?:о|близько|приблизно)\s+\d{1,2}[:.]\d{2}\b|\b(?:вночі|вранці|вдень|увечері|надвечір|під ранок)\b"),
        ("ATTACK_METHOD_OR_IMPACT_MENTION", r"\b(?:ракет\w*|дрон\w*|безпілот\w*|бпла|авіаудар\w*|авіабомб\w*|артилер\w*|обстріл\w*|удар\w*|влучан\w*|атак\w*)\b"),
        ("STRUCK_OBJECT_MENTION", r"\b(?:приватн\w*|житлов\w*)\s+будин\w*|\b(?:багатоповерхів\w*|підприємств\w*|інфраструктур\w*|автомобіл\w*|школ\w*|лікарн\w*)\b"),
        ("FATALITY_MENTION_NOT_A_CONFIRMED_TOTAL", r"\b(?:загин\w*|загиб\w*|помер\w*|смерт\w*|жертв\w*)\b"),
        ("REPORT_SEQUENCE_MENTION_NOT_LINK", r"\b(?:пізніше|згодом|спочатку|раніше|перед тим|додатково|уточнил\w*|також|ще\s+одн\w*|зросл\w*)\b"),
        ("OFFICIAL_REFERENCE_MENTION", r"\b(?:поліці\w*|дснс|ова|військов\w*\s+адміністраці\w*)\b"),
    )
    score_weight = {
        "DATE_MENTION_NOT_ATTACK_DATE": 2, "PLACE_MENTION_NOT_LOCALITY_PROOF": 2,
        "TIME_MENTION_NOT_ATTACK_TIME": 1, "ATTACK_METHOD_OR_IMPACT_MENTION": 3,
        "STRUCK_OBJECT_MENTION": 3, "FATALITY_MENTION_NOT_A_CONFIRMED_TOTAL": 5,
        "REPORT_SEQUENCE_MENTION_NOT_LINK": 4, "OFFICIAL_REFERENCE_MENTION": 1,
    }
    candidates, segment, seen_attack = [], 1, False
    for order, sentence in enumerate(_review_sentences(text), 1):
        if len(sentence) < 12:
            continue
        lower = sentence.casefold()
        kinds = [name for name, pattern in patterns if re.search(pattern, lower)]
        if not kinds:
            continue
        # Explicit new-impact language starts a distinct *unverified* text
        # segment. Updates ("згодом", "пізніше") do NOT start a new event.
        new_attack = bool(re.search(
            r"^\s*(?:окремо|інша атака|під час іншого|інший обстріл|"
            r"(?:увечері|вночі|вранці|вдень)\s+того\s+ж\s+дня)",
            lower))
        if new_attack and seen_attack and "ATTACK_METHOD_OR_IMPACT_MENTION" in kinds:
            segment += 1
        if "ATTACK_METHOD_OR_IMPACT_MENTION" in kinds:
            seen_attack = True
        quote = re.sub(r"\bзапоріж(?:жя|жі|жю)\b|\bзапорізьк\w*\b",
                       "[ГЕО]", sentence, flags=re.I)
        quote = re.sub(r"\bбудин\w*\b", "[ОБ'ЄКТ]", quote, flags=re.I)
        if re.search(r"[<>№]|https?://|\b(?:вулиц\w*|вул\.?|провул\w*|проспект\w*|"
                     r"квартир\w*|паспорт\w*|адрес\w*|будинок\s*\d+)\b", quote, re.I):
            continue
        incomplete = len(quote) > 170
        if not incomplete:
            holder = {"excerpts": [{"text": quote}], "reasons": []}
            withhold_unsafe_excerpts(holder)
            if not holder["excerpts"]:
                continue
        tags = set(kinds)
        score = sum(score_weight[k] for k in kinds)
        if {"FATALITY_MENTION_NOT_A_CONFIRMED_TOTAL",
            "ATTACK_METHOD_OR_IMPACT_MENTION"} <= tags:
            score += 5
        if {"FATALITY_MENTION_NOT_A_CONFIRMED_TOTAL",
            "REPORT_SEQUENCE_MENTION_NOT_LINK"} <= tags:
            score += 5
        if {"STRUCK_OBJECT_MENTION", "ATTACK_METHOD_OR_IMPACT_MENTION"} <= tags:
            score += 3
        candidates.append({
            "article_sentence_order": order, "article_segment_hint": segment,
            "unverified_segment_only": True, "tags": kinds, "_score": score,
            "context_status": "CONTEXT_INCOMPLETE" if incomplete else "COMPLETE",
            "sentence_sha256": sha_data(quote.encode("utf-8")),
            "excerpt": None if incomplete else quote,
        })
    budget = min(650, max(170, len(text) // 4))
    selected, covered, used = [], set(), 0
    while candidates and len(selected) < 8:
        eligible = [x for x in candidates if used + len(x["excerpt"] or "") <= budget]
        if not eligible:
            break
        chosen = min(eligible, key=lambda x: (
            -x["_score"], -len(set(x["tags"]) - covered),
            x["article_sentence_order"]))
        candidates.remove(chosen)
        quote = chosen.pop("excerpt")
        chosen.pop("_score")
        if quote is not None:
            chosen["excerpt"] = quote
            chosen["excerpt_sha256"] = sha_data(quote.encode("utf-8"))
            used += len(quote)
        else:
            chosen["decision_reason"] = "CONTEXT_INCOMPLETE"
        chosen["decision"] = "NEEDS_REVIEW"
        selected.append(chosen)
        covered.update(chosen["tags"])
    result["evidence_mentions"] = sorted(
        selected, key=lambda x: x["article_sentence_order"])
    result["article_segments_unverified"] = len(set(
        x["article_segment_hint"] for x in selected))
    return result


