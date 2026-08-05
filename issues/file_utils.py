import PyPDF2
import docx

def extract_text_from_file(file):
    filename = file.name.lower()

    if filename.endswith(".pdf"):
        reader = PyPDF2.PdfReader(file)
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        return text

    elif filename.endswith(".docx"):
        doc = docx.Document(file)
        return "\n".join([para.text for para in doc.paragraphs])

    elif filename.endswith(".txt"):
        return file.read().decode("utf-8")

    else:
        return None
