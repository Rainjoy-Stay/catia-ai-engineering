"""Evidence gates for interference review, separate from engineering verdicts."""

def assess(triage, review=None, invalid_objects=()):
    pair = triage['pair']
    details = (review or {}).get('details', {})
    invalid = [obj for obj in pair if obj in invalid_objects]
    input_valid = details.get('input_valid')
    result = {'pair': pair, 'shape_category': triage['category'],
              'status': 'PENDING_REVIEW', 'excluded': False,
              'conversion_confirmed': False, 'real_interference_confirmed': False,
              'evidence': triage.get('evidence', {}), 'invalid_objects': invalid,
              'priority': 2, 'next_action': '核对原始来源及局部几何，未确认前保留待复核'}
    if invalid or (isinstance(input_valid, list) and False in input_valid):
        result.update(status='INVALID_INPUT_GEOMETRY', priority=0,
                      next_action='先定位自交／不可定向等输入异常，比较原始 STEP 与导出 BREP；不可凭公共体积确认干涉')
    elif (review or {}).get('status') in ('TIMEOUT', 'ERROR'):
        result.update(status='REVIEW_INCOMPLETE', priority=1,
                      next_action='复核未完成；不得将超时或错误归为真实／伪干涉')
    elif details.get('common_valid') is False:
        result.update(status='INVALID_COMMON_GEOMETRY', priority=0,
                      next_action='交集几何无效，先检查布尔结果及输入拓扑')
    elif input_valid == [True, True] and details.get('common_valid') is True:
        result.update(status='GEOMETRY_REPRODUCED', priority=1,
                      next_action='缓存几何复算一致性尚需核对数值；复算本身不能证明源模型真实干涉或转换伪干涉')
        result['review_evidence'] = details
    return result
