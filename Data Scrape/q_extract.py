import re
import fitz
from pathlib import Path
import time


BASE_DIR = Path(r"D:\OPI\Data Scrape\SRT\OPI tests and situations")
OUTPUT_FILE = Path(r"D:\OPI\Data Scrape\questions.txt")


def log(tag, msg):
    print(f"[{tag}] {msg}")


def is_valid_pdf(file: Path):
    name = file.name.lower()
    return "opi" in name and "situational" not in name


# -------------------------
# CLEAN TEXT
# -------------------------

def clean_text(text: str) -> str:
    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text)

    # remove repeated headers
    text = re.sub(r"oral proficiency interview.*?test\s*-\s*\d+", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"opi test\s*-\s*\d+", " ", text, flags=re.IGNORECASE)

    # remove answer blocks completely
    text = re.sub(r"Strongly Disagree.*?Strongly Agree", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(Strongly Disagree|Disagree|Neutral|Agree|Strongly Agree)\b", " ", text, flags=re.IGNORECASE)

    # remove ads/noise
    text = re.sub(r"Earn \$5.*", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"Discover more.*", " ", text, flags=re.IGNORECASE)

    return text


# -------------------------
# EXTRACT QUESTIONS (FINAL LOGIC)
# -------------------------





import re

def extract_questions(text: str):
    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text)

    # remove headers
    text = re.sub(r"oral proficiency interview.*?test\s*-\s*\d+", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"opi test\s*-\s*\d+", " ", text, flags=re.IGNORECASE)

    # remove answer blocks (soft, not destructive)
    text = re.sub(r"Strongly Disagree.*?Strongly Agree", " ", text, flags=re.IGNORECASE)

    # remove UI noise
    text = re.sub(r"\b(Strongly Disagree|Disagree|Neutral|Agree|Strongly Agree)\b", " ", text, flags=re.IGNORECASE)

    # STEP 1: force split on question marks OR numbering OR sentence transitions
    parts = re.split(r"(?<=\?)|\d+\.\s+", text)

    questions = []
    seen = set()

    buffer = ""

    for p in parts:
        p = p.strip()
        if not p:
            continue

        # remove numbering
        p = re.sub(r"^\d+\.\s*", "", p)

        buffer += " " + p
        buffer = buffer.strip()

        # detect end of question
        if "?" in buffer:
            qs = buffer.split("?")

            for i in range(len(qs) - 1):
                q = qs[i].strip()

                if len(q) < 8:
                    continue

                q = re.sub(r"\s{2,}", " ", q)
                q = q + "?"

                # very light filtering only
                if len(q.split()) < 4:
                    continue

                low = q.lower()
                if "opi test" in low:
                    continue

                if q not in seen:
                    seen.add(q)
                    questions.append(q)

            buffer = qs[-1]

    # flush remaining buffer
    if buffer and len(buffer.split()) > 4:
        q = buffer.strip()
        if not q.endswith("?"):
            q += "?"
        if q not in seen:
            questions.append(q)

    return questions
# -------------------------
# PDF READ
# -------------------------

def extract_text(pdf_path: Path):
    log("DEBUG", f"Reading {pdf_path.name}")

    doc = fitz.open(pdf_path)

    full = []
    for i, page in enumerate(doc):
        t = page.get_text("text")
        log("DEBUG", f"Page {i+1}: {len(t)} chars")
        full.append(t)

    return " ".join(full)


# -------------------------
# MAIN
# -------------------------

def main():
    log("INFO", "START")

    pdfs = sorted(BASE_DIR.glob("*.pdf"))
    pdfs = [p for p in pdfs if is_valid_pdf(p)]

    log("INFO", f"PDFs: {len(pdfs)}")

    all_q = []
    seen_global = set()

    start = time.time()

    for i, pdf in enumerate(pdfs, 1):
        log("INFO", f"[{i}/{len(pdfs)}] {pdf.name}")

        text = extract_text(pdf)
        qs = extract_questions(text)

        log("INFO", f"Questions found: {len(qs)}")

        for q in qs:
            k = q.lower()
            if k not in seen_global:
                seen_global.add(k)
                all_q.append(q)

        log("INFO", f"Total collected: {len(all_q)}")
        print("-" * 50)

    # SAVE
    log("INFO", "Saving...")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for q in all_q:
            f.write(q + "\n")

    log("INFO", f"DONE: {len(all_q)} questions")
    log("INFO", f"Saved: {OUTPUT_FILE}")
    log("INFO", f"Time: {time.time() - start:.2f}s")


if __name__ == "__main__":
    main()