from __future__ import annotations

import re
import statistics
import unicodedata
from dataclasses import dataclass, field

import pdfplumber

import config as C

BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
         "Agustus", "September", "Oktober", "November", "Desember"]
BULAN_SINGKAT = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
_MONTH_KEYS = {"jan": 1, "feb": 2, "peb": 2, "mar": 3, "apr": 4, "mei": 5, "may": 5, "jun": 6, "jul": 7,
               "agu": 8, "ags": 8, "agt": 8, "aug": 8, "sep": 9, "okt": 10, "oct": 10, "nov": 11,
               "nop": 11, "des": 12, "dec": 12}

BR = "\ue000"


_BULLETS = ["\u20ac", "\u2219", "\uf0b7", "\u25cf", "\u25aa", "\u2022", "\u25cb", "\u25e6", "\u25a0",
            "\u25a1", "\u2023", "\u2043", "\u27a2", "\u27a4", "\u25ba", "\u25b6", "\uf0a7", "\uf076",
            "\uf0d8", "\uf0fc"]
_CHAR_MAP = {"\u00ad": "-", "\u00a0": " ", "\u201c": '"', "\u201d": '"', **{b: "•" for b in _BULLETS}}
_MASK_RE = re.compile(r"\[\s*MASKED[\s_\-]*(DATA|PIC|SATKER)?(?:[\s_\-]*(PEJABAT|NIP|TTD)[\w.\-]*)?\s*\]", re.I)
_MASK_COLLIDE_RE = re.compile(r"\[\s*MASKED\s*D(?:ATA?)?(?=[A-Za-z])")
MASK_TOKEN_RE = re.compile(r"\[MASKED:[A-Z]+\]")
MARKER_RE = re.compile(r"^\s*(?:(?:[A-Z]|[IVX]{2,4}|\d{1,2}|[a-z])\s*[.)]|\(\s*(?:\d{1,2}|[a-z])\s*\)|•)\s*")
TOP_MARKER_RE = re.compile(r"^\s*(?:[A-Z]|[IVX]{1,4})\s*[.)]\s*\S")     # penanda bagian utama: A. / II.
LIST_RE = re.compile(r"^\s*(?:(?:[A-Za-z]|\d{1,2})\s*[.)]\s|\(\s*(?:\d{1,2}|[a-z])\s*\)\s|[•\-–]\s?)")
DATE_RE = re.compile(r"^\s*[A-Za-z][A-Za-z.\s]{2,40}?\s*,\s*(?:\d{1,2}\s+)?(?:" + "|".join(BULAN) + r")\s+\d{4}", re.I)
NIP_RE = re.compile(r"\bNIP\b\.?\s*:?\s*\d[\d\s]{16,22}|\b\d{8}\s?\d{6}\s?\d\s?\d{3}\b")
SIG_TOKEN_RE = re.compile(r"\[MASKED:(PEJABAT|NIP|TTD)\]")
JAB_RE = re.compile(C.JABATAN_TTD, re.I)


def clean_text(s: str | None) -> str:
    if not s:
        return ""
    for a, b in _CHAR_MAP.items():
        s = s.replace(a, b)
    s = unicodedata.normalize("NFKC", s)
    s = _MASK_RE.sub(lambda m: f"[MASKED:{(m.group(2) or m.group(1) or 'DATA').upper()}]", s)
    s = _MASK_COLLIDE_RE.sub("[MASKED:DATA] ", s)
    s = re.sub(r"(\[MASKED:[A-Z]+\])\s*[A-Za-z]{0,4}\]", r"\1", s)
    return re.sub(r"\s+", " ", s).strip()


def strip_masks(s: str) -> str:
    return re.sub(r"^(?:\s*\[MASKED:[A-Z]+\]\s*)+", "", s or "").strip()


def norm_label(s: str) -> str:
    s = MASK_TOKEN_RE.sub(" ", (s or "").replace(BR, " ")).lower()
    return re.sub(r"\s+", " ", s).strip(" :;.,-–\t")


def month_of(c) -> int | None:
    c = (c or "").replace(BR, " ").strip().lower().rstrip(".")
    if c.isdigit():
        return int(c) if 1 <= int(c) <= 12 else None
    return _MONTH_KEYS.get(c[:3]) if c[:3].isalpha() and len(c) <= 9 else None


@dataclass
class Line:
    page: int
    top: float
    text: str
    bold: bool
    words: list = field(repr=False)


@dataclass
class Table:
    page: int
    top: float
    header: list               # judul kolom (sudah digabung bila header multi-baris)
    rows: list                 # baris data, list[list[str]]
    gantt: bool = False
    caption: str = ""          # mis. "Tahun 2025" pada tabel Gantt
    fills_found: bool = False  # Gantt: ada sel berwarna yang terbaca
    pages: list = field(default_factory=list)


@dataclass
class Section:
    key: str
    raw: str
    level: int
    page: int
    blocks: list = field(default_factory=list, repr=False)


def _is_bullet(w) -> bool:
    return clean_text(w["text"]) == "•"


def _mid(o) -> float:
    return (o["top"] + o["bottom"]) / 2


def _group_lines(words, page_no) -> list[Line]:


    bullets = [w for w in words if _is_bullet(w)]
    groups = []
    for w in sorted((w for w in words if not _is_bullet(w)), key=lambda w: (w["top"], w["x0"])):
        cy = _mid(w)
        for g in reversed(groups[-3:]):
            if g["top"] - 1 <= cy <= g["bottom"] + 1:
                g["words"].append(w)
                break
        else:
            groups.append({"top": w["top"], "bottom": w["bottom"], "words": [w]})

    for b in sorted(bullets, key=lambda w: w["top"]):
        cy, h = _mid(b), b["bottom"] - b["top"]
        cands = [g for g in groups
                 if min(w["x0"] for w in g["words"]) >= b["x1"] - 1
                 and abs(_mid(g) - cy) <= 1.2 * max(h, g["bottom"] - g["top"])]
        if cands:
            g = min(cands, key=lambda g: abs(_mid(g) - cy))
            g["words"].append(b)
            g["top"] = min(g["top"], b["top"])
        else:
            groups.append({"top": b["top"], "bottom": b["bottom"], "words": [b]})
    groups.sort(key=lambda g: g["top"])

    lines = []
    for g in groups:
        ws = sorted(g["words"], key=lambda w: w["x0"])
        text = clean_text(" ".join(w["text"] for w in ws))
        if text:
            bold = sum("bold" in (w.get("fontname") or "").lower() for w in ws) >= len(ws) / 2
            lines.append(Line(page_no, g["top"], text, bold, ws))
    return lines


def _is_colored(color) -> bool:

    if color is None:
        return False
    if isinstance(color, (int, float)):
        return color < 0.85
    try:
        c = [float(v) for v in color]
    except (TypeError, ValueError):
        return False
    if len(c) == 1:
        return c[0] < 0.85
    if len(c) == 3:
        return max(c) - min(c) > 0.15 or sum(c) / 3 < 0.85
    if len(c) == 4:  # CMYK
        return max(c[:3]) > 0.15 or c[3] > 0.15
    return False


def _covers(f, box) -> bool:
    x0, y0, x1, y1 = box
    ox = min(x1, f["x1"]) - max(x0, f["x0"])
    oy = min(y1, f["bottom"]) - max(y0, f["top"])
    return ox > 0.5 * (x1 - x0) and oy > 0.5 * (y1 - y0)


def _header_len(raw) -> int:
    """Baris header = baris 0 + baris lanjutan yang kolom pertamanya kosong (maks 3)."""
    n = 1
    while n < min(len(raw) - 1, 3) and not (raw[n][0] or "").strip():
        n += 1
    return n


def _logical_table(cells, hl):

    base = max(cells[:hl], key=len)
    if len(base) < 2:
        base = max(cells, key=len)
    cols = sorted((c["bbox"] for c in base), key=lambda b: b[0])
    if len(cols) < 2:
        return None

    def col_at(x):
        for i, c in enumerate(cols):
            if c[0] - 1 <= x <= c[2] + 1:
                return i
        return min(range(len(cols)), key=lambda i: abs((cols[i][0] + cols[i][2]) / 2 - x))

    def col_of(b):
        i = col_at((b[0] + b[2]) / 2)
        if (b[2] - b[0]) > 1.5 * (cols[i][2] - cols[i][0]):   # sel membentang (mis. "Bootcamp")
            i = col_at(b[0] + 2)                               # -> taruh di kolom paling kiri
        return i

    def to_row(cs):
        r = [""] * len(cols)
        for c in cs:
            if c["text"]:
                i = col_of(c["bbox"])
                r[i] = (r[i] + " " + c["text"]).strip()
        return r

    hrows = [to_row(cs) for cs in cells[:hl]]
    header = [" ".join(h[i] for h in hrows if h[i]) for i in range(len(cols))]
    rows = [r for r in (to_row(cs) for cs in cells[hl:]) if any(r)]
    keep = [i for i in range(len(cols)) if header[i] or any(r[i] for r in rows)]
    return [header[i] for i in keep], [[r[i] for i in keep] for r in rows]


def _month_ranges(ms) -> str:
    """{2,3,4,9} -> 'Feb–Apr, Sep'"""
    spans = []
    for m in sorted(ms):
        if spans and m == spans[-1][1] + 1:
            spans[-1][1] = m
        else:
            spans.append([m, m])
    return ", ".join(BULAN_SINGKAT[a - 1] if a == b else f"{BULAN_SINGKAT[a - 1]}–{BULAN_SINGKAT[b - 1]}"
                     for a, b in spans)


def _gantt_table(cells, ybox, fills):


    hdr = next((i for i, cs in enumerate(cells) if len({month_of(c["text"]) for c in cs} - {None}) >= 10), None)
    if hdr is None:
        return None
    months = {}
    for c in cells[hdr]:
        m = month_of(c["text"])
        if m and m not in months:
            months[m] = c["bbox"]
    mx0 = min(b[0] for b in months.values())
    mx1 = max(b[2] for b in months.values())

    side = []                                            # kolom non-bulan (kiri/kanan)
    for cs in cells[:hdr + 1]:
        for c in cs:
            b = c["bbox"]
            if (b[2] <= mx0 + 1 or b[0] >= mx1 - 1) and not any(
                    abs(b[0] - s[0]) < 2 and abs(b[2] - s[2]) < 2 for s in side):
                side.append(b)
    side.sort(key=lambda b: b[0])
    names = [" ".join(c["text"] for cs in cells[:hdr + 1] for c in cs if c["text"]
                      and abs(c["bbox"][0] - b[0]) < 2 and abs(c["bbox"][2] - b[2]) < 2) for b in side]
    left = [k for k, b in enumerate(side) if b[2] <= mx0 + 1]
    right = [k for k in range(len(side)) if k not in left]
    main = max(left, key=lambda k: side[k][2] - side[k][0]) if left else None
    caption = next((c["text"] for cs in cells[:hdr] for c in cs if re.search(r"20\d{2}", c["text"])), "")


    header_bottom = max([side[k][3] for k in left] + [b[3] for b in months.values()])

    data = []
    for cs, (_, y0, _, y1) in zip(cells[hdr + 1:], ybox[hdr + 1:]):
        if y1 <= header_bottom + 1:                       # potongan baris header (abu-abu) -> lewati
            continue
        lab, present = [""] * len(side), set()
        for c in cs:
            cx = (c["bbox"][0] + c["bbox"][2]) / 2
            for k, b in enumerate(side):
                if b[0] - 1 <= cx <= b[2] + 1:
                    present.add(k)
                    if c["text"]:
                        lab[k] = (lab[k] + " " + c["text"]).strip()
        act = {m for m, b in months.items() if any(_covers(f, (b[0], y0, b[2], y1)) for f in fills)}
        if not any(lab) and not data:                     # sisa baris header sebelum data pertama
            continue
        if main is not None and main not in present and data:
            prev_lab, prev_act = data[-1]                 # sub-baris dari sel merge
            for k, v in enumerate(lab):
                if v and v not in prev_lab[k]:
                    prev_lab[k] = (prev_lab[k] + "; " + v).strip("; ")
            prev_act |= act
        elif any(lab) or act:
            data.append([lab, set(act)])

    left = [k for k in left if any(lab[k] for lab, _ in data)]
    right = [k for k in right if any(lab[k] for lab, _ in data)]

    header = [names[k] for k in left]
    if C.GANTT_MATRIKS:
        header += BULAN_SINGKAT
    if C.GANTT_RINGKAS:
        header.append("Bulan Pelaksanaan")
    header += [names[k] for k in right]

    rows = []
    for lab, act in data:
        r = [lab[k] for k in left]
        if C.GANTT_MATRIKS:
            r += [C.GANTT_TANDA if m in act else "" for m in range(1, 13)]
        if C.GANTT_RINGKAS:
            r.append(_month_ranges(act))
        rows.append(r + [lab[k] for k in right])
    return header, rows, caption, any(act for _, act in data)


def _extract_tables(page, page_no):
    fills = [o for o in page.rects + page.curves if o.get("fill") and _is_colored(o.get("non_stroking_color"))]
    out = []
    for t in page.find_tables():
        raw = t.extract()
        start = next((i for i, r in enumerate(raw) if any((c or "").strip() for c in r)), len(raw))
        raw, trows = raw[start:], t.rows[start:]            # buang baris grid kosong di atas header
        if len(raw) < 2 or max(len(r) for r in raw) < 2:
            continue

        cells = [[{"bbox": bb, "text": clean_text((tx or "").replace("\n", BR))}
                  for bb, tx in zip(row.cells, txts) if bb is not None]
                 for row, txts in zip(trows, raw)]
        g = _gantt_table(cells, [row.bbox for row in trows], fills)
        if g:
            header, rows, caption, found = g
            tab = Table(page_no, t.bbox[1], header, rows, True, caption, found, [page_no])
        else:
            lt = _logical_table(cells, _header_len(raw))
            if not lt or len(lt[0]) < 2:
                continue                                  # bukan tabel sungguhan -> biarkan sebagai teks
            tab = Table(page_no, t.bbox[1], lt[0], lt[1], pages=[page_no])
        out.append((tab, t.bbox))
    return out


def _header_rest(full, pre):

    f = " ".join(full.replace(BR, " ").split())
    p = " ".join(pre.replace(BR, " ").split())
    return f[len(p):].strip() if f.lower().startswith(p.lower()) else None


def _is_continuation(r) -> bool:

    return not r[0].strip() or (len(r) > 2 and sum(1 for c in r if c.strip()) <= 1)


def _merge_tables(blocks):
    """Gabungkan tabel yang terpotong antarhalaman (header diulang / baris lanjutan)."""
    out = []
    for b in blocks:
        prev = out[-1] if out else None
        if (isinstance(b, Table) and isinstance(prev, Table) and not (prev.gantt or b.gantt)
                and prev.pages[-1] == b.page - 1 and not any(x.page == b.page for x in out)
                and len(b.header) == len(prev.header)):
            rows = [list(r) for r in b.rows]
            rest = [_header_rest(h, p) for h, p in zip(b.header, prev.header)]
            if all(r is not None for r in rest):          # header diulang di halaman lanjutan
                if any(rest):                             # ada teks lanjutan yang ikut terbaca sbg header
                    rows = [rest] + rows
            else:                                         # halaman lanjutan tanpa header ulang
                rows = [list(b.header)] + rows
            if rows and prev.rows and _is_continuation(rows[0]):
                last, cont = prev.rows[-1], rows.pop(0)
                for i, c in enumerate(cont):
                    if c and i < len(last):
                        last[i] = (last[i] + BR + c).strip()   # potongan sel lintas halaman
            prev.rows.extend(rows)
            prev.pages.append(b.page)
            continue
        out.append(b)
    return out


def load_pdf(path):
    drop = [re.compile(p, re.I) for p in C.FOOTER_DROP]
    tte = re.compile(C.FOOTER_TTE, re.I)
    blocks, images, tte_notes = [], {}, []
    with pdfplumber.open(path) as pdf:
        n_pages = len(pdf.pages)
        for pno, page in enumerate(pdf.pages, 1):
            try:
                page = page.dedupe_chars()
            except Exception:
                pass
            tabs = _extract_tables(page, pno)
            words = page.extract_words(x_tolerance=3, y_tolerance=3, extra_attrs=["fontname", "size"])
            words = [w for w in words if not any(
                bb[0] <= (w["x0"] + w["x1"]) / 2 <= bb[2] and bb[1] <= (w["top"] + w["bottom"]) / 2 <= bb[3]
                for _, bb in tabs)]
            lines = []
            for ln in _group_lines(words, pno):
                if tte.search(ln.text):
                    note = ln.text.lstrip("- ")
                    if note not in (t for _, t in tte_notes):   # footer TTE di tiap halaman -> cukup sekali
                        tte_notes.append((pno, note))
                elif not any(r.search(ln.text) for r in drop):
                    lines.append(ln)
            images[pno] = [im["top"] for im in page.images]
            blocks += sorted(lines + [t for t, _ in tabs], key=lambda b: b.top)
    return _merge_tables(blocks), n_pages, images, tte_notes


SECDEFS = [{"key": k, "level": d.get("level", 1), "induk": set(d.get("induk", [])),
            "kecuali": set(d.get("kecuali_dalam", [])),
            "pola": [re.compile(p + C.HEADING_SUFFIX, re.I) for p in d["pola"]]}
           for k, d in C.SECTIONS.items()]
HDEFS = [(k, [re.compile(p, re.I) for p in ps]) for k, _, _, ps in C.HEADER_FIELDS]


def classify_heading(line: Line, top_key):
    raw = strip_masks(line.text)
    if not raw or len(raw) > 120 or raw.lstrip().startswith(("•", "-", "–")):
        return None                                       # butir daftar bukan heading
    m = MARKER_RE.match(raw)
    rem = raw[m.end():] if m else raw
    norm = norm_label(rem)
    if not norm or len(norm.split()) > C.SETTINGS["maks_kata_heading"] or rem.rstrip().endswith("."):
        return None
    best, best_cov = None, 0.0
    for sd in SECDEFS:
        if top_key in sd["kecuali"]:
            continue
        for p in sd["pola"]:
            mm = p.match(norm)
            if mm:
                cov = len(mm.group(0)) / len(norm)
                if cov >= C.SETTINGS["rasio_cakupan"] and cov > best_cov:
                    best, best_cov = sd, cov
    if best is None:
        return None
    if best["level"] > 1 and top_key not in best["induk"]:
        if TOP_MARKER_RE.match(raw):                      # "B. Dasar Hukum" -> berdiri sebagai bagian utama
            return {**best, "level": 1}
        if not (m and line.bold):
            return None
    return best


def _heading_candidate(line: Line) -> bool:
    """Baris yang bentuknya seperti heading tetapi tidak cocok dengan pola mana pun."""
    raw = strip_masks(line.text)
    if not raw or raw.lstrip().startswith(("•", "-", "–")) or raw.rstrip().endswith((".", ",", ";")):
        return False
    m = MARKER_RE.match(raw)
    norm = norm_label(raw[m.end():] if m else raw)
    n = len(norm.split())
    if not norm or n > C.SETTINGS["maks_kata_heading"] or not re.search(r"[a-z]", norm) or DATE_RE.match(raw):
        return False
    return bool(TOP_MARKER_RE.match(raw)) or (line.bold and n <= C.SETTINGS["maks_kata_kandidat"])


def _colon_x(line: Line, near=None):
    for w in line.words:
        t = w["text"].strip()
        x = ((w["x0"] + w["x1"]) / 2 if t == ":" else w["x1"] if t.endswith(":")
             else w["x0"] if t.startswith(":") else None)
        if x is not None and (near is None or abs(x - near) <= C.SETTINGS["toleransi_titik_dua"]):
            return x
    return None


def _join(ws):
    return clean_text(" ".join(w["text"] for w in ws)).strip(" :")


def parse_header(lines, tables):
    """Label di kiri kolom ':' dan nilai di kanan; label/nilai multi-baris digabung."""
    raw, titles = [], []
    xs = [x for x in (_colon_x(l) for l in lines) if x is not None]
    if xs:
        med, cur = statistics.median(xs), None
        for l in lines:
            cx = _colon_x(l, med)
            if cx is not None:
                left = [w for w in l.words if w["x1"] <= cx + 0.5]
                right = [w for w in l.words if w["x0"] >= cx - 0.5 and w not in left]
                cur = {"label": _join(left), "value": _join(right), "page": l.page}
                raw.append(cur)
            elif cur is None:
                titles.append(l.text)
            else:
                left = [w for w in l.words if w["x1"] <= med - 2]
                right = [w for w in l.words if w["x0"] >= med - 2]
                cur["label"] = (cur["label"] + " " + _join(left)).strip()
                cur["value"] = (cur["value"] + " " + _join(right)).strip()
    else:
        titles = [l.text for l in lines]
    for t in tables:                                      # header yang dibuat sebagai tabel
        for r in [t.header] + t.rows:
            cells = [c for c in r if c and c.strip(" :")]
            if len(cells) >= 2:
                raw.append({"label": cells[0], "value": " ".join(cells[1:]).lstrip(": "), "page": t.page})
    fields = []
    for d in raw:
        n = norm_label(d["label"])
        key = next((k for k, ps in HDEFS if any(p.search(n) for p in ps)), "LAIN")
        fields.append({"key": key, "label": clean_text(d["label"]),
                       "value": clean_text(d["value"]), "page": d["page"]})
    return titles, fields


def parse_signature(blocks, images, n_pages):


    def cand(i):
        return blocks[i].page >= n_pages - 1 and isinstance(blocks[i], Line)

    idx = next((i for i in range(len(blocks) - 1, -1, -1)
                if cand(i) and DATE_RE.match(strip_masks(blocks[i].text))), None)
    has_date = idx is not None
    if idx is None:
        end = next((i for i in range(len(blocks) - 1, -1, -1) if cand(i)
                    and (SIG_TOKEN_RE.search(blocks[i].text) or NIP_RE.search(blocks[i].text))), None)
        if end is None:
            return blocks, None
        idx = end
        for j in range(end - 1, max(end - 5, -1), -1):
            b = blocks[j]
            if not isinstance(b, Line) or b.page != blocks[end].page:
                break
            if JAB_RE.match(strip_masks(b.text)):
                idx = j
                break

    tail = blocks[idx:]
    lines = [b for b in tail if isinstance(b, Line)]
    body = blocks[:idx] + [b for b in tail if isinstance(b, Table)]
    first = lines[0]
    rest = lines[1:] if has_date else lines

    def has(l, tok):
        return f"[MASKED:{tok}]" in l.text

    nip_i = next((i for i, l in enumerate(rest) if NIP_RE.search(l.text) or has(l, "NIP")), None)
    name_i = next((i for i, l in enumerate(rest) if has(l, "PEJABAT")), None)
    if name_i is None:
        if nip_i is not None and nip_i > 0:
            name_i = nip_i - 1
        elif nip_i is None and rest:
            name_i = len(rest) - 1
    ttd_i = {i for i, l in enumerate(rest) if has(l, "TTD") and i not in (name_i, nip_i)}
    sig = {"tempat_tanggal": first.text if has_date else "", "page": first.page,
           "nama": rest[name_i].text if name_i is not None else "",
           "nip": rest[nip_i].text if nip_i is not None else "",
           "jabatan": " ".join(l.text for i, l in enumerate(rest) if i not in (name_i, nip_i) and i not in ttd_i),
           "ttd_masked": any(has(l, "TTD") for l in rest),
           "gambar": any(top >= first.top - 5 for top in images.get(first.page, []))}
    return body, sig


def segment_sections(blocks):
    """Bagi badan dokumen per heading. Mengembalikan (sections, kandidat_heading)."""
    pra = Section("PRA", "", 1, blocks[0].page if blocks else 1)
    sections, cur, top_key, kandidat = [pra], pra, None, []
    for b in blocks:
        if isinstance(b, Line):
            sd = classify_heading(b, top_key)
            if sd and sd["key"] != cur.key:               # heading berulang berturut-turut = isi
                cur = Section(sd["key"], b.text, sd["level"], b.page)
                sections.append(cur)
                top_key = sd["key"] if sd["level"] == 1 else top_key
                continue
            if not sd and _heading_candidate(b):
                kandidat.append((b.page, strip_masks(b.text)))
        cur.blocks.append(b)                              # teks tak dikenali ikut section sebelumnya
    return [s for s in sections if s is not pra or s.blocks], kandidat


_WORD_RE = re.compile(r"[A-Za-z]{3,}")
_FRAG_RE = re.compile(rf"[A-Za-z]*\s*{BR}\s*[A-Za-z]*")
_BREAK_RE = re.compile(rf"([A-Za-z]+-?)\s*{BR}\s*([a-z]+)")


def _doc_texts(doc):
    yield from doc["titles"]
    for f in doc["header"]:
        yield f["label"]
        yield f["value"]
    for s in doc["sections"]:
        for b in s.blocks:
            if isinstance(b, Table):
                yield b.caption
                yield from b.header
                for r in b.rows:
                    yield from r
            else:
                yield b.text


def doc_vocab(doc) -> set:

    v = set()
    for t in _doc_texts(doc):
        v.update(w.lower() for w in _WORD_RE.findall(_FRAG_RE.sub(" ", t or "")))
    return v


def join_breaks(s: str, vocab: set) -> str:

    if not s or BR not in s:
        return s

    def fix(m):
        a, b = m.group(1), m.group(2)
        nxt = m.string[m.end():m.end() + 1]
        if a.endswith("-"):
            return a + b
        if len(b) == 1 and nxt not in ".)":
            return a + b
        w = (a + b).lower()
        if w in vocab and (a.lower() not in vocab or b.lower() not in vocab):
            return a + b
        return a + " " + b

    for _ in range(4):                                   # beberapa putaran untuk pemenggalan berantai
        new = _BREAK_RE.sub(fix, s)
        if new == s:
            break
        s = new
    return re.sub(r"\s+", " ", s.replace(BR, " ")).strip()


def resolve_breaks(doc, vocab: set):
    for f in doc["header"]:
        f["label"], f["value"] = join_breaks(f["label"], vocab), join_breaks(f["value"], vocab)
    for s in doc["sections"]:
        for b in s.blocks:
            if isinstance(b, Table):
                b.caption = join_breaks(b.caption, vocab)
                b.header = [join_breaks(h, vocab) for h in b.header]
                b.rows = [[join_breaks(c, vocab) for c in r] for r in b.rows]
    return doc


def parse_document(path, resolve=True, vocab=None) -> dict:


    blocks, n_pages, images, tte_notes = load_pdf(path)
    body, sig = parse_signature(blocks, images, n_pages)
    first = next((i for i, b in enumerate(body) if isinstance(b, Line)
                  and (sd := classify_heading(b, None)) and sd["level"] == 1), None)
    if first is None:
        first = next((i for i, b in enumerate(body) if b.page > 1), len(body))
    head = body[:first]
    titles, header = parse_header([b for b in head if isinstance(b, Line)],
                                  [b for b in head if isinstance(b, Table)])
    sections, kandidat = segment_sections(body[first:])
    doc = {"path": path, "n_pages": n_pages, "titles": titles, "header": header,
           "sections": sections, "sig": sig, "tte": tte_notes, "kandidat": kandidat}
    if resolve:
        resolve_breaks(doc, doc_vocab(doc) | set(vocab or ()))
    return doc