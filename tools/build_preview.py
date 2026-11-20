"""Build offline HTML review of actual baseline/V2 data and SAT traces."""
import argparse
import json
from pathlib import Path
import sys
if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.validate_puzzles import ROOT, PUZZLE_IDS, validate_dataset


def build_preview(output=ROOT/'tools/preview_puzzles.html'):
    data = {}
    for name, directory in [('v2', ROOT/'puzzles'), ('baseline', ROOT/'puzzles_baseline')]:
        reports = validate_dataset(directory)
        data[name] = {'puzzles': [json.loads((directory/(pid+'.json')).read_text()) for pid in PUZZLE_IDS],
                      'reports': reports}
    template = (ROOT/'tools/preview_template.html').read_text(encoding='utf-8')
    # JSON is data in a non-executable script element. Escape HTML terminators.
    payload = json.dumps(data, ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    output=Path(output)
    output.write_text(template.replace('__PUZZLE_DATA__',payload), encoding='utf-8')
    return output


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'tools/preview_puzzles.html')
    args=parser.parse_args()
    print(build_preview(args.output))
if __name__=='__main__':
    main()
