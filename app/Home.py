"""Home page for Streamlit app."""
import streamlit as st
from pathlib import Path
import time
import sys
import requests
import logging, re, unicodedata, warnings
from datetime import datetime
import camelot, pdfplumber
import tempfile, os
# import pandas as pd
import shutil
from src.data_scraping.data_scraping import download_pdf
from src.data_extraction.extract_pdfs import (
    load_blueprint,
    tidy,
    fill_blueprint
)
from src.data_extraction.extract_latest_id import get_latest_id

# from src.config_parameters import params
# from src.utils_app import (
#     add_about,
#     add_logo,
#     set_home_page_style,
#     toggle_menu_button,
# )


# # Page title
# st.title("ERM table extraction tool")

# Sidebar
# st.sidebar.title("Navigation")
# section = st.sidebar.selectbox("Go to", ["File selection", "Extract and export tables"])

# File selection
# if section == "File selection":

st.title("ERM table extraction tool")

st.markdown(
    """This tool allows users to extract data from ERM reports. These reports can be uploaded manually or obtained directly from DRC EHTools page (https://ehtools.org/document-register). In the second case, users can indicate document IDs based on EHT."
    """
)

st.header("Select the range of files to be processed")

ROOT      = Path(__file__).resolve().parent
# RAW_DIR   = ROOT / "ehtools_data_raw"
# MID_DIR   = ROOT / "data_mid"
# LOG_DIR   = ROOT / "logs"
BLUE_XLSX = ROOT / "blueprint.xlsx"
BLUE_CSV  = ROOT / "blueprint.csv"
DWL_DIR   = Path("ehtools_download")
MID_DIR   = Path("data_mid")
LOG_DIR   = Path("logs")
# BLUE_XLSX = Path("blueprint.xlsx")
# BLUE_CSV  = Path("blueprint.csv")

# os.makedirs(DWL_DIR, exist_ok=True)
# os.makedirs(MID_DIR, exist_ok=True)
# os.makedirs(LOG_DIR, exist_ok=True)
DWL_DIR.mkdir(exist_ok=True)
MID_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "extraction.log"
# LOG_FILE = LOG_DIR + "/extraction.log"

BASE_URL   = "https://ehtools.org"
PDF_URL   = BASE_URL + ("/document-register")

left, right = st.columns(2)

with left:
    st.subheader("Choose ID range to download")
    st.markdown(
        """
        Please enter the IDs of the reports that you would like to download for 
        automatic extraction of tables.\n
        Pdf files are downloaded into a folder called "ehtools_data_raw". If the folder does not exist, it will be created.\n
        Pdf files that are already present in the folder will be skipped.
        """
    )

    with st.spinner("Fetching the latest maximum ID for pdfs from https://ehtools.org ..."):
        max_id = get_latest_id(PDF_URL)
        # if max_id is None:
            # TODO add error catching here

    st.markdown(
        f"""
        The minimum ID value is 1. The maximum ID value is {max_id}.
        """
    )

    # Initialize session state
    if "start_id" not in st.session_state:
        st.session_state.start_id = 1
    if "end_id" not in st.session_state:
        st.session_state.end_id = 1

    st.session_state.start_id = st.number_input("Start ID", min_value=1, max_value=max_id, value=st.session_state.start_id, step=1, width=150)
    st.session_state.end_id = st.number_input("End ID", min_value=st.session_state.start_id, max_value=max_id, value=max(st.session_state.start_id, st.session_state.end_id), step=1, width=150)

    # Extra safeguard
    if st.session_state.end_id < st.session_state.start_id:
        st.error("End ID must be greater than or equal to Start ID.")

    # START_ID   = 1265
    # END_ID     = 1269          # inclusive
    # END_ID     = 1399          # inclusive
    # PDF_FOLDER = Path("ehtools_data_raw")
    # PDF_FOLDER.mkdir(exist_ok=True)
    PDF_FOLDER = DWL_DIR

    HTTP_TIMEOUT   = 60        # seconds
    POLITENESS_SEC = 0.5       # delay between requests
    USER_AGENT     = "Mozilla/5.0 (Automated PDF grabber for ehtools)"

    SESSION = requests.Session()
    SESSION.headers.update({"User-Agent": USER_AGENT})

    if st.button("Start file download"):
        # file = st.file_uploader("Choose CSV", type="csv")
        for doc_id in range(st.session_state.start_id, st.session_state.end_id + 1):
            try:
                download_pdf(doc_id, PDF_FOLDER, BASE_URL, SESSION, HTTP_TIMEOUT)
                time.sleep(POLITENESS_SEC)  # respect the server
            except Exception as exc:
                print(f"[{doc_id}] error: {exc}", file=sys.stderr)

### FILE UPLOAD OPTION
with right:
    st.subheader("Upload a pdf file")
    uploaded_files = st.file_uploader("Browse for file", type="pdf", accept_multiple_files=True)









########
### # Table extraction and export
# elif section == "Extract and export tables":
st.header("Extract tables and export them into an excel file")
st.markdown(
    """
    Please click, if you wish to extract tables and export them into an excel file.
    Tables for all downloaded pdfs are extracted, if they exist.
    """
)
if st.button("Start table extraction"):
    warnings.filterwarnings("ignore", category=UserWarning, module="pypdf")
    logging.getLogger("camelot").setLevel(logging.ERROR)

    # # ROOT      = Path(__file__).resolve().parent
    # ROOT      = Path(__file__).resolve()
    # RAW_DIR   = ROOT / "ehtools_data_raw"
    # MID_DIR   = ROOT / "data_mid"
    # LOG_DIR   = ROOT / "logs"
    # BLUE_XLSX = ROOT / "blueprint.xlsx"
    # BLUE_CSV  = ROOT / "blueprint.csv"

    # MID_DIR.mkdir(exist_ok=True)
    # LOG_DIR.mkdir(exist_ok=True)
    # LOG_FILE = LOG_DIR / "missing_tables.txt"

    TITLE_RX = re.compile(r"Tableau de scores de s[eé]v[ée]rit[ée]\s+ERM", re.I)
    HEAD_RX  = re.compile(r"Secteur.*Crit[eè]re", re.I)
    EXPECTED  = ["Secteur", "Critère", "1", "2", "3", "4", "5"]

    BP_TEMPLATE = load_blueprint(BLUE_XLSX, BLUE_CSV)

    PARAMS = [
        dict(flavor="lattice", process_background=True, line_scale=40, copy_text=["h"]),
        dict(flavor="lattice", process_background=True, line_scale=30),
        dict(flavor="stream", strip_text=" \n"),
        dict(flavor="stream", strip_text=" \n", edge_tol=500),
    ]

    missing = []

    #TODO - should this have an option to extract tables for individual files? 
    # for pdf in sorted(RAW_DIR.glob("*.pdf")):

    #log file
    with open(LOG_FILE, "a", encoding="utf-8") as fh:
        fh.writelines(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    if uploaded_files:
        pdf_range = uploaded_files
        st.write("Uploaded file(s)")
    else:
        pdf_range = [f"{i}.pdf" for i in range(st.session_state.start_id, st.session_state.end_id + 1)]
        st.write("Downloaded files")
    for id in pdf_range:
        if uploaded_files:
            pdf = id
            pdf_name = id.name
        if not uploaded_files:
            file_name = id
            pdf = DWL_DIR / file_name
            pdf_name = file_name
        # TODO - add spinner???
        with st.status("Checking pdf file...", state="running", expanded=True) as status:
            st.write(f"File: {pdf_name}")
            found = False
            with pdfplumber.open(pdf) as doc:
                pgs = {i + 1 for i, p in enumerate(doc.pages) if TITLE_RX.search(p.extract_text() or "") or HEAD_RX.search(p.extract_text() or "")}
                if not pgs:
                    pgs = range(1, len(doc.pages) + 1)
            # save as temporary file so that camelot.read_pdf can work with it
            ## camelot does not work with ByteIO-type objects
            ## streamlit.file_uploader returns ByteIO-type objects
            if uploaded_files:
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
                tmp.write(pdf.read())
                tmp.flush()
                tmp.close()
                pdf_path = tmp.name
            else:
                pdf_path = pdf.name
            for p in pgs:
                for ps in PARAMS:
                    try:
                        pdf_path = pdf
                        tables = camelot.read_pdf(pdf_path, pages=str(p), **ps)
                    except Exception:
                        continue
                    for tbl in tables:
                        try:
                            df = tidy(tbl.df)
                        except Exception:
                            continue
                        if list(df.columns) != EXPECTED:
                            continue
                        filled = fill_blueprint(df)
                        if uploaded_files:
                            out_name = os.path.splitext(os.path.basename(id.name))[0] + "_severity_table.xlsx"
                        else:
                            out_name = os.path.splitext(os.path.basename(id))[0] + "_severity_table.xlsx"
                        out = MID_DIR / out_name
                        # out = MID_DIR / f"{pdf.stem}_severity_table.xlsx"
                        filled.to_excel(out, index=False)
                        st.write(f"Table extracted as: {out.name}")
                        with open(LOG_FILE, "a", encoding="utf-8") as fh:
                            # TODO - correct output message, so that pdf.name and out.name appear
                            fh.writelines(pdf.name + f":\n Table extracted: {out.name}\n")
                        found = True
                        break
                    if found:
                        break
                if found:
                    break
            if not found:
                # print("table NOT found")
                # st.write("Table NOT found!")
                missing.append(pdf.name)
                # status.update(
                #     label="Download complete!", state="complete", expanded=False
                # )
        
    if missing:
        with open(LOG_FILE, "a", encoding="utf-8") as fh:
            fh.writelines(f"{m}\n" for m in missing)
        print(f"\nLogged {len(missing)} missing reports: {LOG_FILE}")
    
    with st.status("Zipping extracted tables ...", state="running", expanded=True) as status:
        zip_path = Path("table_csvs.zip")
        shutil.make_archive(zip_path.stem, 'zip', MID_DIR)

    # print("\nDone.")

    st.download_button(
        label = "Download csv files with extracted table",
        data = zip_path.read_bytes(),
        file_name = zip_path.name,
        mime = "application/zip"
    )



