import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree

TEXT_ENCODINGS = ("utf-8-sig", "utf-8", "gb18030")

def read_text_with_fallback(path: Path) -> str:
    for encoding in TEXT_ENCODINGS:
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")

def read_docx(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        xml_bytes = archive.read("word/document.xml")
    root = ElementTree.fromstring(xml_bytes)
    texts: list[str] = []
    for node in root.iter():
        if node.tag.endswith("}t") and node.text:
            texts.append(node.text)
        elif node.tag.endswith("}p"):
            texts.append("\n")
    normalized = "".join(texts)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()

def read_source(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return read_docx(path)
    if suffix in {".md", ".markdown", ".txt", ".json", ".yaml", ".yml"}:
        return read_text_with_fallback(path)
    raise ValueError(f"暂不支持的源文件类型: {path.suffix or '<none>'}")
