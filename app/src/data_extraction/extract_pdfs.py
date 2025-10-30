import logging, re, unicodedata, warnings
from pathlib import Path
from difflib import SequenceMatcher

# import camelot, pdfplumber
import pandas as pd

warnings.filterwarnings("ignore", category=UserWarning, module="pypdf")
logging.getLogger("camelot").setLevel(logging.ERROR)

ROOT      = Path(__file__).resolve().parent.parent.parent
RAW_DIR   = ROOT / "ehtools_data_raw"
MID_DIR   = ROOT / "data_mid"
LOG_DIR   = ROOT / "logs"
BLUE_XLSX = ROOT / "blueprint.xlsx"
BLUE_CSV  = ROOT / "blueprint.csv"

MID_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "missing_tables.txt"

TITLE_RX = re.compile(r"Tableau de scores de s[eé]v[ée]rit[ée]\s+ERM", re.I)
HEAD_RX  = re.compile(r"Secteur.*Crit[eè]re", re.I)
EXPECTED  = ["Secteur", "Critère", "1", "2", "3", "4", "5"]

def slug(t: str) -> str:
    t = unicodedata.normalize("NFD", str(t))
    t = t.encode("ascii", "ignore").decode("ascii").lower()
    t = re.sub(r"\s+", "", t)
    return re.sub(r"[^a-z0-9]", "", t)

def load_blueprint(xlsx: Path, csv: Path) -> pd.DataFrame:
    raw = pd.read_excel(xlsx, header=None) if xlsx.exists() else pd.read_csv(csv, header=None)
    hdr = raw[0].astype(str).str.contains(r"(?i)^secteur$").idxmax()
    sev = raw.loc[hdr + 1, 2:6].apply(lambda v: str(int(float(v))) if isinstance(v, (int, float)) else str(v).strip()) # type: ignore
    cols = ["Secteur", "Critère"] + sev.tolist()
    df = raw.loc[hdr + 2 :, 0:6].copy() # type: ignore
    df.columns = cols
    return df.reset_index(drop=True)

BP_TEMPLATE = load_blueprint(BLUE_XLSX, BLUE_CSV)

def collapse_wrapped(df: pd.DataFrame) -> pd.DataFrame:
    out, buf = [], None
    for _, r in df.iterrows():
        has_val = r[["1", "2", "3", "4", "5"]].notna().any()
        if has_val:
            if buf is not None:
                out.append(buf)
            buf = r.copy()
        else:
            if buf is not None:
                buf["Critère"] = re.sub(r"\s+", " ", f"{buf['Critère']} {r['Critère']}".strip())
    if buf is not None:
        out.append(buf)
    df = pd.DataFrame(out).reset_index(drop=True)
    return rescue_embedded(df)

def rescue_embedded(df: pd.DataFrame) -> pd.DataFrame:
    for idx, row in df.iterrows():
        if row[["1", "2", "3", "4", "5"]].notna().any():
            continue
        txt = str(row["Critère"])
        parts = txt.split()
        if len(parts) < 6:
            continue
        cand = parts[-5:]
        if any(re.fullmatch(r"-|\d+%?|\d+", c) for c in cand):
            df.loc[idx, ["1", "2", "3", "4", "5"]] = cand # type: ignore
            df.loc[idx, "Critère"] = " ".join(parts[:-5]).strip() # type: ignore
    return df

def detect_header(df: pd.DataFrame):
    for i in range(min(5, len(df))):
        if re.search(r"(?i)secteur", str(df.iat[i, 0])) and re.search(r"(?i)crit", str(df.iat[i, 1])):
            return i
    raise ValueError

def tidy(tbl_df: pd.DataFrame) -> pd.DataFrame:
    df = (
        tbl_df.replace("\n", " ", regex=True)
        .apply(lambda c: c.str.strip() if c.dtype == "object" else c)
        .replace("", pd.NA)
        .dropna(axis=1, how="all")
        .dropna(axis=0, how="all")
        .reset_index(drop=True)
    )
    hdr = detect_header(df)
    sev_vals = df.iloc[hdr + 1, 2:7].tolist()
    df = df.iloc[hdr + 2 :, :7]
    df.columns = ["Secteur", "Critère"] + sev_vals
    df.columns = EXPECTED
    return collapse_wrapped(df)

def best_match(cands: pd.Series, target: str):
    ratios = cands.apply(lambda s: SequenceMatcher(None, s, target).ratio())
    i = ratios.idxmax()
    return i, ratios.loc[i]

def fill_blueprint(extracted: pd.DataFrame) -> pd.DataFrame:
    bp = BP_TEMPLATE.copy()
    bp["__s"] = bp["Secteur"].ffill().apply(slug)
    bp["__c"] = bp["Critère"].apply(slug)
    ex = extracted.copy()
    ex["__s"] = ex["Secteur"].ffill().apply(slug)
    ex["__c"] = ex["Critère"].apply(slug)
    for _, row in ex.iterrows():
        sec, crit = row["__s"], row["__c"]
        sub = bp[bp["__s"] == sec]
        if sub.empty:
            continue
        idx, score = best_match(sub["__c"], crit)
        if score >= 0.8:
            bp.loc[idx, ["1", "2", "3", "4", "5"]] = row[["1", "2", "3", "4", "5"]].values
    return bp.drop(columns=["__s", "__c"])[EXPECTED]
