# Document Parsing Strategy: Complexity vs Resources

**Goal:** Decide how the curriculum service (and any callers) should turn documents (PDF, DOCX, etc.) into markdown for Bedrock. Balance long-term efficiency, ops complexity, and cost.

---

## 1. Current State and Real Need

| Step | What happens today | Who does it |
|------|--------------------|------------|
| File → Markdown | docling (DocumentConverter) converts PDF/DOCX to markdown | Curriculum service (in-process) |
| Markdown → Structured data | Bedrock (instructor) extracts topics / questions / marking scheme | Curriculum service (Bedrock API) |

**Insight:** Docling and transformers are used **only** for the first step (file → markdown). All “understanding” and structure extraction is already done by **Bedrock**. So we are carrying torch/transformers/docling purely for document-to-text conversion.

**Call sites:**  
- Curriculum topic extraction (PDF/DOCX URL → markdown → Bedrock → topics).  
- Parse-document API (used by assessment “upload questions” / “upload marking scheme” and any future callers).  
- Same `parse_document_to_markdown()` is the single entry point.

---

## 2. Options Compared

| Option | Approach | Complexity | Resources (image, CI, cost) | Quality / flexibility |
|--------|----------|------------|-----------------------------|------------------------|
| **A. Keep docling** | No change; docling in curriculum service | Low (no refactor) | **Very high**: multi-GB image, long CI, “no space” risk, heavy local compute | Best for complex layouts, multi-format |
| **B. Lightweight in-process** | Replace docling with PyMuPDF4LLM (PDF→markdown) + small DOCX path (e.g. docx2txt or python-docx) in same service | Medium (one-time swap in `document_parser`) | **Low**: small deps, slim image, fast CI, no extra infra | Good for typical PDFs/DOCX; may lag docling on very complex/scanned PDFs |
| **C. Bedrock + Textract** | Upload file to S3 → Textract (OCR/structure) → text → Bedrock for structure | High (S3, IAM, Textract API, async for large docs) | **Medium**: no parsing in our image; **per-page cost** (Textract ~$0.0015/page) | Strong for scanned docs and forms; more moving parts |
| **D. Separate file-parser service** | New microservice: file → markdown (using B or C internally); curriculum calls it over HTTP | High (new service, deploy, monitor, versioning) | Depends on impl (B vs C inside); extra network and ops | Same as B or C, but adds operational surface |

---

## 3. Complexity vs Resources (Summary)

- **A** minimizes code change but **maximizes** image size, CI time, and runner issues; not efficient long term.  
- **B** gives the best **efficiency** for “typical” curriculum/assessment docs: small image, fast CI, no new services, no per-page fee. Complexity is one refactor in `document_parser` + dependency swap.  
- **C** is good if you want **zero** parsing logic in your code and are fine with AWS cost and S3/Textract integration; complexity and cost go up.  
- **D** only pays off if parsing is shared by many consumers or owned by a separate team; for a single curriculum (and assessment) consumer, it adds ops without clear benefit over B.

---

## 4. Recommendation

**Primary path: Option B (lightweight in-process)**

- **Replace docling** with:
  - **PDF:** `pymupdf4llm` (PDF → markdown, LLM-oriented, no torch).
  - **DOCX / TXT:** Keep a simple path (e.g. `docx2txt` or `python-docx` for text; plain read for `.txt`).  
- **Remove** from curriculum `requirements.txt`: `docling` (and thus the transitive torch/transformers/CUDA stack).  
- **Keep** instructor + Bedrock for all structure extraction; no change to that flow.

**Why B over the others**

- **Long-term efficiency:** Much smaller image and faster, more reliable CI; no “no space left on device” from docling.  
- **Complexity:** Single service, one module to maintain (`document_parser`), no new services or S3/Textract wiring unless we later add C.  
- **Resources:** Minimal extra cost (no Textract per page), no new infra.  
- **Risk:** If some PDFs (e.g. heavily scanned or complex layout) are worse than with docling, we can add an **optional** Textract path later (e.g. for “hard” PDFs or when a user explicitly requests it) without bringing back docling.

**When to consider C (Textract + Bedrock)**

- You need high accuracy on **scanned** or **form** PDFs and are willing to pay per page and manage S3 + IAM.  
- You prefer to own no parsing code and centralize on AWS services.

**When to consider D (separate file-parser service)**

- Multiple apps/teams need parsing with different SLAs or backends.  
- You want to scale or upgrade parsing independently from curriculum.  
For a single consumer (curriculum + assessment), B in-process is simpler.

---

## 5. Implementation (Option B) — Done

1. **Implemented** a new `document_parser` backend:
   - PDF: `pymupdf4llm.to_markdown(path)`.
   - DOCX: `docx2txt.process(path)`.
   - TXT: open and read as UTF-8.
2. **Switched** `parse_document_from_path` / `parse_document_to_markdown` to this backend; same function signatures and call sites.
3. **Removed** `docling` from `services/curriculum/requirements.txt`; added `pymupdf4llm>=0.0.14` and `docx2txt>=0.9`.
4. **Test** with representative PDFs and DOCX (syllabi, worksheets); if quality is acceptable, ship. If not, consider an optional Textract path for problematic docs.
5. The **real** curriculum image is now much smaller and faster to build (no torch/docling).

---

## 6. References

- Docling: used only in `services/curriculum/utils/document_parser.py` and called from `curriculum_service.extract_topics` and route `POST /parse-document`.
- Bedrock: already used for all structured extraction (topics, questions, marking scheme) in `curriculum_service.py`.
- PyMuPDF4LLM: [pymupdf4llm](https://pypi.org/project/pymupdf4llm/) – PDF to markdown, no torch.
- Textract: [AWS Textract](https://aws.amazon.com/textract/) – OCR/layout; [pricing](https://aws.amazon.com/textract/pricing/) (e.g. DetectDocumentText ~$0.0015/page).
