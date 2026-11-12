"""Use packaged DOCX rasterizer with a native Word PDF on Windows without LO."""
import argparse
import importlib.util
import shutil
from pathlib import Path


def main():
    p=argparse.ArgumentParser(); p.add_argument('docx',type=Path); p.add_argument('pdf',type=Path)
    p.add_argument('renderer',type=Path); p.add_argument('output',type=Path); a=p.parse_args()
    spec=importlib.util.spec_from_file_location('packaged_docx_renderer',a.renderer)
    renderer=importlib.util.module_from_spec(spec); spec.loader.exec_module(renderer)
    def native_pdf(doc_path,user_profile,convert_tmp_dir,stem,verbose):
        target=Path(convert_tmp_dir)/f'{stem}.pdf'; shutil.copyfile(a.pdf,target)
        return str(target),'Native Microsoft Word export used; LibreOffice missing on Windows'
    renderer.convert_to_pdf=native_pdf
    pages=renderer.rasterize(str(a.docx),str(a.output),110,False,False)
    print('Pages rendered:',len(pages))


if __name__=='__main__': main()
