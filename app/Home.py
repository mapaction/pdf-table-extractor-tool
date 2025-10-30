"""Home page for Streamlit app."""
import streamlit as st
from pathlib import Path
import time
import sys
import requests
import logging, re, unicodedata, warnings
from datetime import datetime
import camelot, pdfplumber
import pandas as pd
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
st.title("Select the range of files to be processed")

# ROOT      = Path(__file__).resolve().parent
ROOT      = Path(__file__).resolve().parent
RAW_DIR   = ROOT / "ehtools_data_raw"
MID_DIR   = ROOT / "data_mid"
LOG_DIR   = ROOT / "logs"
BLUE_XLSX = ROOT / "blueprint.xlsx"
BLUE_CSV  = ROOT / "blueprint.csv"

MID_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)
# LOG_FILE = LOG_DIR / "missing_tables.txt"
LOG_FILE = LOG_DIR / "extraction.log"

BASE_URL   = "https://ehtools.org"
PDF_URL   = BASE_URL + ("/document-register")

left, right = st.columns(2)

with left:
    st.header("Choose ID range to download")
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
    PDF_FOLDER = Path("ehtools_data_raw")
    PDF_FOLDER.mkdir(exist_ok=True)

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
    st.header("Upload a pdf file")
    uploaded_file = st.file_uploader("Browse for file", type="pdf")
    if uploaded_file:
        #TODO - ADD file name here
        st.write(f"File ADDFILENAMEHERE successfully uploaded!")
    #     st.write(f"{type(uploaded_file)}")









########
### # Table extraction and export
# elif section == "Extract and export tables":
st.title("Extract tables and export them into an excel file")
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

    if uploaded_file:
        pdf_range = list(uploaded_file)
    else:
        pdf_range = list(range(st.session_state.start_id, st.session_state.end_id + 1))
    for id in pdf_range:
    # for id in range(st.session_state.start_id, st.session_state.end_id + 1):
        if type(id) == "streamlit.runtime.uploaded_file_manager.UploadedFile":
            st.write("Uploaded file ")
        if type(id) != "streamlit.runtime.uploaded_file_manager.UploadedFile":
            file_name = f"{id}.pdf"
        file_name = f"{id}.pdf"
        pdf = RAW_DIR / file_name
        # TODO - add spinner???
        with st.status("Checking pdf file...", state="running", expanded=True) as status:
            st.write(f"Pdf file {pdf.name}")
            found = False
            with pdfplumber.open(pdf) as doc:
                pgs = {i + 1 for i, p in enumerate(doc.pages) if TITLE_RX.search(p.extract_text() or "") or HEAD_RX.search(p.extract_text() or "")}
                if not pgs:
                    pgs = range(1, len(doc.pages) + 1)
            for p in pgs:                
                # st.write(f"Searching for the table ...")
                for ps in PARAMS:
                    try:
                        tables = camelot.read_pdf(str(pdf), pages=str(p), **ps) # type: ignore
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
                        out = MID_DIR / f"{pdf.stem}_severity_table.xlsx"
                        filled.to_excel(out, index=False)
                        # print(f"table extracted ({ps['flavor']}): {out.name}")
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

    print("\nDone.")

# # title
# st.markdown("# Home")

# # First section
# st.markdown("## Introduction")
# st.markdown(
#     """
#     This web app allows you to download ERM reports from ehtools.org and extract indicator tables.
# """
# )

# # Second section
# st.markdown("## How to use the tool")



