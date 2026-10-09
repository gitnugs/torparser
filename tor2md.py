from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

import config as C
from ekstraksi import (LIST_RE, MARKER_RE, Table, doc_vocab, norm_label, parse_document,
                       resolve_breaks, strip_masks)

SEC = C.SECTIONS
HDR = {k: (judul, ck) for k, judul, ck, _ in C.HEADER_FIELDS}
_HYPHEN_END = re.compile(r"[A-Za-z]-$")


def _cell(s):
    return ("" if s is None else str(s)).replace("|", "\\|").replace("\n", " ")


def _md_table(header, rows):
    return (["| " + " | ".join(_cell(h) or " " for h in header) + " |", "|" + "---|" * len(header)]
            + ["| " + " | ".join(_cell(c) for c in r) + " |" for r in rows])


def _render_table(t: Table):
    return ([t.caption, ""] if t.caption else []) + _md_table(t.header, t.rows)


def _paragraphs(blocks):


    out, cur, n = [], None, 0
    for b in blocks:
        if isinstance(b, Table):
            if cur:
                out.append(cur)
                cur = None
            out.append(b)
            continue
        t = b.text
        hyphen = cur is not None and bool(_HYPHEN_END.search(cur)) and t[:1].islower()
        if hyphen:                                        # 'dasar-' + 'dasar...' selalu disambung
            cur, n = cur + t, n + 1
            continue
        short_title = cur is not None and n == 1 and len(cur) <= 50 and not cur.endswith((",", ";"))
        short_label = len(t) <= 50 and t.endswith(":")
        if cur is None or LIST_RE.match(t) or cur.endswith(":") or short_title or short_label:
            if cur:
                out.append(cur)
            cur, n = t, 1
        else:
            cur, n = cur + " " + t, n + 1
    return out + ([cur] if cur else [])


def _header_title(f):
    return HDR[f["key"]][0] if f["key"] in HDR else f["label"]


def _header_lines(f):
    parts = [p for p in re.split(r"\s(?=\d{1,2}\.\s)", f["value"]) if p]
    if len(parts) > 1:
        return [f"{f['label']}:", ""] + parts + [""]
    return [f"{f['label']}: {f['value']}", ""]


def _section_lines(s):
    out = [f"**{strip_masks(s.raw)}**", ""] if s.raw else []
    for u in _paragraphs(s.blocks):
        out += (_render_table(u) if isinstance(u, Table) else [u]) + [""]
    return out


def _ttd_status(doc):
    """Bukti tanda tangan: TTE, gambar tanda tangan/QR, token [MASKED:TTD], atau None."""
    sg = doc["sig"]
    if doc["tte"]:
        return "TTE"
    if sg and sg["gambar"]:
        return "gambar tanda tangan/QR"
    if sg and sg.get("ttd_masked"):
        return "dimasking"
    return None


def _signature_lines(doc):
    sg, out = doc["sig"], []
    if sg:
        out += [sg[k] for k in ("tempat_tanggal", "jabatan", "nama", "nip") if sg.get(k)]
        if sg["gambar"]:
            out.append("[gambar tanda tangan/QR]")
        if sg.get("ttd_masked") and not any("[MASKED:TTD]" in x for x in out):
            out.append("[MASKED:TTD]")
    out += [t for _, t in doc["tte"]]
    return [x for line in out for x in (line, "")] or ["_(tidak ditemukan)_", ""]


def to_markdown(doc) -> str:
    ro = next((f["value"] for f in doc["header"] if f["key"] == "RO" and f["value"]), Path(doc["path"]).stem)
    L = [f"# KAK/TOR — {ro}", ""]
    for t in doc["titles"]:
        L += [t, ""]
    for f in doc["header"]:
        L += [f"## {_header_title(f)}", ""] + _header_lines(f)
    for s in doc["sections"]:
        judul = SEC[s.key]["judul"] if s.key in SEC else "Teks Pembuka"
        L += [f"{'##' if s.level == 1 else '###'} {judul}", ""] + _section_lines(s)
    L += ["## Pengesahan", ""] + _signature_lines(doc)
    return "\n".join(L).rstrip() + "\n"


def to_indeks(doc) -> str:
    sg, ttd = doc["sig"], _ttd_status(doc)
    L = [f"# Indeks — {Path(doc['path']).name}", "",
         f"- Sumber: {Path(doc['path']).name}", f"- Jumlah halaman: {doc['n_pages']}", "",
         "## Pemetaan Ceklis", ""]
    rows = []
    for cid, kode, nama, tpl in C.CHECKLIST:
        loc = [f"{_header_title(f)} (header «{f['label']}», hal. {f['page']})"
               for f in doc["header"] if cid in HDR.get(f["key"], ("", []))[1]]
        for s in doc["sections"]:
            d = SEC.get(s.key, {})
            asli = f"«{strip_masks(s.raw)}», hal. {s.page}"
            if cid in d.get("ceklis", []):
                loc.append(f"{d['judul']} ({asli})")
            elif cid in d.get("terkait", []):
                loc.append(f"{d['judul']} — terkait ({asli})")
        if cid == 23 and (sg or doc["tte"]):
            page = sg["page"] if sg else doc["tte"][0][0]
            nama_ok = "ada" if sg and (sg["nama"] or sg["jabatan"]) else "tidak ada"
            loc.insert(0, f"Pengesahan (hal. {page}) — nama/jabatan: {nama_ok}; "
                          f"tanda tangan: {ttd or 'TIDAK TERDETEKSI'}")
        if cid == 24 and sg and sg["nip"]:
            loc.append(f"Pengesahan (hal. {sg['page']})")
        rows.append([f"C{cid:02d}", kode, nama, tpl, "<br>".join(loc) or "–"])
    L += _md_table(["No", "Kode", "Komponen", "Template", "Heading di Markdown (sumber asli)"], rows)

    notes = []
    if not sg and not doc["tte"]:
        notes.append("Blok pengesahan tidak terdeteksi.")
    elif not ttd:
        notes.append("Tanda tangan penanggung jawab tidak terdeteksi (tidak ada TTE, gambar, atau token [MASKED:TTD]).")
    if not (sg and sg["nip"]):
        notes.append("NIP penanggung jawab tidak ditemukan di blok pengesahan.")
    notes += [f"Label header tidak dikenali: «{f['label']}» (hal. {f['page']})"
              for f in doc["header"] if f["key"] == "LAIN"]
    for s in doc["sections"]:
        name = strip_masks(s.raw) or "Teks Pembuka"
        for b in s.blocks:
            if isinstance(b, Table) and len(b.pages) > 1:
                notes.append(f"Tabel di «{name}» bersambung hal. {', '.join(map(str, b.pages))} (sudah digabung).")
            if isinstance(b, Table) and b.gantt and not b.fills_found:
                notes.append(f"Tabel Gantt di «{name}»: tidak ada sel berwarna yang terbaca.")
    notes += [f"Kandidat heading tidak dikenal: «{t}» (hal. {p})" for p, t in doc.get("kandidat", [])]
    L += ["", "## Catatan Parser", ""] + ([f"- {x}" for x in notes] or ["- Tidak ada."])
    return "\n".join(L) + "\n"


def write_rekap(docs, path: Path):

    agg = {}
    for doc in docs:
        fname = Path(doc["path"]).name
        for page, text in doc.get("kandidat", []):
            m = MARKER_RE.match(text)
            key = norm_label(text[m.end():] if m else text)
            a = agg.setdefault(key, {"n": 0, "files": set(), "contoh": text, "file": fname, "hal": page})
            a["n"] += 1
            a["files"].add(fname)
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["kandidat", "frekuensi", "jumlah_file", "contoh_asli", "contoh_file", "halaman"])
        for key, a in sorted(agg.items(), key=lambda kv: (-len(kv[1]["files"]), -kv[1]["n"], kv[0])):
            w.writerow([key, a["n"], len(a["files"]), a["contoh"], a["file"], a["hal"]])


def _load_extra_vocab():
    p = getattr(C, "KOSAKATA_TAMBAHAN", None)
    if not p:
        return set()
    try:
        return {w.strip().lower() for w in Path(p).read_text(encoding="utf-8").splitlines() if w.strip()}
    except OSError as e:
        print(f"[PERINGATAN] kosakata tambahan tidak terbaca: {e}", file=sys.stderr)
        return set()


def main():
    ap = argparse.ArgumentParser(description="KAK/ToR PDF -> Markdown")
    ap.add_argument("input", help="file PDF atau folder")
    ap.add_argument("-o", "--output", default="hasil_md")
    ap.add_argument("--kecuali", default="template", help="lewati file yang namanya memuat kata ini")
    ap.add_argument("--rekap", action="store_true", help="tulis kandidat_heading.csv di folder output")
    args = ap.parse_args()

    src = Path(args.input)
    pdfs = sorted(src.glob("*.pdf")) if src.is_dir() else [src]
    pdfs = [p for p in pdfs if args.kecuali.lower() not in p.name.lower()]
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)


    docs = []
    for p in pdfs:
        try:
            docs.append((p, parse_document(str(p), resolve=False)))
        except Exception as e:
            print(f"[GAGAL] {p.name}: {e}", file=sys.stderr)

    vocab = _load_extra_vocab()
    for _, doc in docs:
        vocab |= doc_vocab(doc)


    for p, doc in docs:
        try:
            resolve_breaks(doc, vocab)
            (out / f"{p.stem}.md").write_text(to_markdown(doc), encoding="utf-8")
            (out / f"{p.stem}.indeks.md").write_text(to_indeks(doc), encoding="utf-8")
            print(f"[OK] {p.name}")
        except Exception as e:
            print(f"[GAGAL] {p.name}: {e}", file=sys.stderr)

    if args.rekap:
        write_rekap([d for _, d in docs], out / "kandidat_heading.csv")
        print(f"[REKAP] {out / 'kandidat_heading.csv'}")


if __name__ == "__main__":
    main()