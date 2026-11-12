"""Replay stored exact evidence without opening or modifying the supplier model."""
import argparse
import copy
import json
from pathlib import Path
from standalone.step_interference_filter import filter_result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.source.resolve() == args.output.resolve():
        parser.error('Use a separate output file to preserve the original evidence')
    original = json.loads(args.source.read_text(encoding='utf-8'))
    result = filter_result(copy.deepcopy(original))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    audit = result['audit']['step_interference_filter']
    summary = {'original_counts': original['counts'], 'filtered_counts': result['counts'],
               'categories': audit['categories'], 'transitions': audit['transitions'],
               'former_failures': [{'issue_id': f['issue_id'],
                                   'classification': f['metadata']['step_interference_filter']}
                                  for f in result['findings']
                                  if f.get('metadata', {}).get('pre_filter_status') == 'FAIL'],
               'full_model_acceptance': False, 'source_modified': False}
    args.output.with_suffix('.summary.json').write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in summary.items() if k != 'former_failures'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
