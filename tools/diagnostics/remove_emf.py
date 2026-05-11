with open("core/clipboard.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
skip = False
for i, line in enumerate(lines):
    if "If no standard image, try to extract EMF/MathType via GDI" in line:
        skip = True
    if skip and "if image is not None and not image.isNull() and self.record_image:" in line:
        skip = False
        
    if "def _get_emf_qimage" in line:
        skip = True
    if skip and "def _make_text_item" in line:
        skip = False
        
    if not skip:
        new_lines.append(line)

with open("core/clipboard.py", "w", encoding="utf-8") as f:
    f.writelines(new_lines)
