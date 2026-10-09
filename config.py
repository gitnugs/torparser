SETTINGS = {
    "maks_kata_heading": 10,     # baris lebih panjang dari ini tidak dianggap heading
    "rasio_cakupan": 0.7,
    "toleransi_titik_dua": 25,   # pt, untuk membaca header berbasis kolom ':'
    "maks_kata_kandidat": 6,
}


HEADING_SUFFIX = r"(\s+(kegiatan|program|pelatihan|pelaksanaan|keluaran|\(?\s*output\s*\)?))*"


KOSAKATA_TAMBAHAN = None

FOOTER_DROP = [r"^catatan\s*:?\s*$", r"uu\s*ite\s*no",
               r"informasi elektronik dan/atau dokumen elektronik", r"^-\s*\d{1,3}\s*-$"]
FOOTER_TTE = r"ditandatangani secara elektronik"       # dipindah ke bagian Pengesahan
JABATAN_TTD = r"^(kepala|sekretaris|direktur|ketua|plt\.?|plh\.?|deputi|inspektur|kuasa\s+pengguna|pejabat\s+pembuat)"


# URUTAN PENTING: yang spesifik di atas.
HEADER_FIELDS = [
    ("IKP",              "Indikator Kinerja Program",   [5],      [r"indikator\s+kinerja\s+program", r"^ikp$"]),
    ("TARGET_IKK",       "Target Indikator Kinerja Kegiatan", [8], [r"(volume|target).*\bikk\b"]),
    ("IKK",              "Indikator Kinerja Kegiatan",  [8],      [r"indikator\s+kinerja\s+kegiatan", r"^ikk$"]),
    ("INDIKATOR_KRO",    "Indikator Klasifikasi Rincian Output", [9],
                                                                  [r"indikator\s+(kro|klasifikasi\s+rincian\s+output)"]),
    ("KRO",              "Klasifikasi Rincian Output",  [9],      [r"klasifikasi\s+rincian\s+output", r"^kro$"]),
    ("RO",               "Rincian Output",              [10],     [r"rincian\s+output", r"^ro$", r"jenis\s+keluaran",
                                                                   r"^keluaran\b", r"^output$"]),
    ("SASARAN_PROGRAM",  "Sasaran Program",             [4],      [r"sasaran\s+program", r"^hasil\b", r"^outcome$"]),
    ("SASARAN_KEGIATAN", "Sasaran Kegiatan",            [7],      [r"sasaran\s+kegiatan"]),
    ("ESELON_II",        "Unit Eselon II",              [2],      [r"eselon\s*ii", r"satker", r"\bupt\b", r"unit\s+kerja"]),
    ("ESELON_I",         "Unit Eselon I",               [2],      [r"eselon\s*i\b", r"unit\s+organisasi"]),
    ("KL",               "Kementerian/Lembaga",         [1],      [r"kementerian(\s+negara)?\s*/\s*lembaga", r"^k\s*/\s*l$",
                                                                   r"^kementerian$"]),
    ("PROGRAM",          "Program",                     [3],      [r"^(nama\s+)?program\b"]),
    ("KEGIATAN",         "Kegiatan",                    [6],      [r"^(nama\s+)?kegiatan\b"]),
    ("VOLUME_SATUAN",    "Volume dan Satuan",           [11, 12], [r"volume.*satuan"]),
    ("VOLUME",           "Volume",                      [11],     [r"volume", r"^target$"]),
    ("SATUAN",           "Satuan",                      [12],     [r"satuan"]),
]


SECTIONS = {
    "LATAR_BELAKANG":   {"judul": "Latar Belakang", "ceklis": [13],
                         "pola": [r"latar\s+belakang"]},
    "DASAR_HUKUM":      {"judul": "Dasar Hukum", "level": 2, "induk": ["LATAR_BELAKANG"], "ceklis": [14],
                         "pola": [r"dasar\s+hukum(\s+tugas\s+fungsi)?(\s*/\s*kebijakan)?",
                                  r"landasan\s+hukum", r"acuan\s+hukum", r"dasar\s+pelaksanaan"]},
    "GAMBARAN_UMUM":    {"judul": "Gambaran Umum", "level": 2, "induk": ["LATAR_BELAKANG"], "ceklis": [15],
                         "pola": [r"gambaran\s+umum", r"uraian\s+(singkat\s+)?kegiatan", r"deskripsi\s+kegiatan"]},
    "MAKSUD_TUJUAN":    {"judul": "Maksud dan Tujuan", "level": 2, "induk": ["LATAR_BELAKANG"], "terkait": [15],
                         "pola": [r"maksud\s+dan\s+tujuan", r"tujuan(\s+dan\s+sasaran)?", r"maksud"]},
    "PENERIMA_MANFAAT": {"judul": "Penerima Manfaat", "ceklis": [16],
                         "pola": [r"penerima\s+manfaat(\s*/\s*beneficiar(y|ies))?", r"beneficiar(y|ies)",
                                  r"target\s+peserta", r"kelompok\s+sasaran"]},
    "RUANG_LINGKUP":    {"judul": "Ruang Lingkup", "terkait": [15, 16],
                         "pola": [r"ruang\s+lingkup(\s*/\s*coverage)?",
                                  r"(target\s+sasaran\s*)?\(?\s*coverage\s*\)?"]},
    "STRATEGI":         {"judul": "Strategi Pencapaian Keluaran", "ceklis": [17],
                         "pola": [r"strategi\s+pe\w*capaian\s+keluaran(\s*\(\s*output\s*\))?",
                                  r"strategi\s+pe\w*capaian(\s+output)?", r"strategi\s+pelaksanaan"]},
    "METODE":           {"judul": "Metode Pelaksanaan", "level": 2, "induk": ["STRATEGI"], "ceklis": [18],
                         "pola": [r"metode\s+pelaksanaan", r"mekanisme\s+pelaksanaan",
                                  r"cara\s+pelaksanaan", r"pola\s+pelaksanaan"]},
    "TAHAPAN":          {"judul": "Tahapan dan Waktu Pelaksanaan", "level": 2, "induk": ["STRATEGI"], "ceklis": [19],
                         "pola": [r"tahapan(\s+(kegiatan|pelaksanaan))?(\s+dan\s+waktu(\s+pelaksanaan)?)?"]},
    "KURUN_WAKTU":      {"judul": "Kurun Waktu Pencapaian Keluaran", "ceklis": [20],
                         "pola": [r"kurun\s+waktu(\s+(pelaksanaan|pencapaian))?(\s+keluaran)?(\s*\(\s*output\s*\))?",
                                  r"waktu\s+pencapaian(\s+keluaran)?(\s*\(\s*output\s*\))?",
                                  r"jangka\s+waktu(\s+pelaksanaan)?", r"waktu\s+pelaksanaan"]},
    "BIAYA":            {"judul": "Biaya yang Diperlukan", "ceklis": [21],
                         "pola": [r"biaya(\s+(dan\s+sumber\s+anggaran|yang\s+diperlukan))?",
                                  r"rencana\s+anggaran(\s+biaya)?", r"rab", r"sumber\s+(dana|anggaran)",
                                  r"anggaran(\s+yang\s+diperlukan)?"]},
    "CBA":              {"judul": "Cost Benefit Analysis", "terkait": [21],
                         "pola": [r"cost\s*(&|and|dan|-)?\s*benefit(\s+analysis)?", r"analisis\s+(biaya\s+)?manfaat"]},
    "MANFAAT":          {"judul": "Manfaat", "terkait": [16, 21], "kecuali_dalam": ["CBA"],
                         "pola": [r"benefit", r"manfaat"]},
    "TIMELINE":         {"judul": "Timeline", "ceklis": [19], "terkait": [20],
                         "pola": [r"timeline", r"jadwal(\s+(pelaksanaan|kegiatan))?", r"time\s*table"]},
    "PIC":              {"judul": "Penanggung Jawab Kegiatan (PIC)", "terkait": [23],
                         "pola": [r"pic", r"penanggung\s*jawab(\s*/\s*person\s+in\s+charge)?",
                                  r"person\s+in\s+charge", r"tugas\s+dan\s+tanggung\s*jawab"]},
    "KPI":              {"judul": "Key Performance Indicator", "terkait": [11, 20],
                         "pola": [r"kpi(\s*\(\s*key\s+performance\s+indicators?\s*\))?",
                                  r"key\s+performance\s+indicators?(\s*\(\s*kpi\s*\))?"]},
    "RISIKO":           {"judul": "Manajemen Risiko", "ceklis": [22],
                         "pola": [r"(manajemen|analisis|mitigasi|identifikasi|pengendalian|pengelolaan)\s+r[ei]siko",
                                  r"r[ei]siko(\s+dan\s+mitigasi(nya)?)?"]},
    "PENUTUP":          {"judul": "Penutup",
                         "pola": [r"penutup"]},
}


CHECKLIST = [
    (1, "I.A", "Kementerian/Lembaga", "(1)"),
    (2, "I.B", "Unit Eselon I/II", "(2), (5)"),
    (3, "I.C", "Program", "(3)"),
    (4, "I.D", "Sasaran Program", "(4) Hasil"),
    (5, "I.E", "Indikator Kinerja Program", "–"),
    (6, "I.F", "Kegiatan", "(6)"),
    (7, "I.G", "Sasaran Kegiatan", "–"),
    (8, "I.H", "Indikator Kinerja Kegiatan", "(7)"),
    (9, "I.I", "Klasifikasi Rincian Output", "(8)"),
    (10, "I.J", "Rincian Output", "(8)"),
    (11, "I.K", "Volume RO", "(9)"),
    (12, "I.L", "Satuan RO", "(8)"),
    (13, "I.M", "Latar Belakang", "A"),
    (14, "I.M.1", "Dasar Hukum", "(10)"),
    (15, "I.M.2", "Gambaran Umum", "(11)"),
    (16, "I.N", "Penerima Manfaat", "(12)"),
    (17, "I.O", "Strategi Pencapaian Keluaran", "C"),
    (18, "I.O.1", "Metode Pelaksanaan", "(13)"),
    (19, "I.O.2", "Tahapan dan Waktu Pelaksanaan", "(14)"),
    (20, "I.P", "Kurun Waktu Pencapaian Keluaran", "(15) D"),
    (21, "I.Q", "Biaya yang Diperlukan", "(16) E"),
    (22, "I.R", "Manajemen Risiko", "–"),
    (23, "I.S", "Nama Penanggung Jawab + Tanda Tangan", "(17)"),
    (24, "I.T", "NIP Penanggung Jawab", "(18)"),
]

# Tabel Gantt/Timeline
GANTT_TANDA = "Y"
GANTT_MATRIKS = True     # tampilkan kolom Jan–Des
GANTT_RINGKAS = True     # tambah kolom "Bulan Pelaksanaan", mis. "Feb–Sep"