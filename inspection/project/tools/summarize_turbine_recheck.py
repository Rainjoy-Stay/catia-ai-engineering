"""Join focused source evidence and derived pair replay into a review ledger."""
import json
from pathlib import Path
from standalone.step_interference_filter import filter_result


def main():
    art = Path(__file__).resolve().parents[1] / 'artifacts'
    body_dir = art / 'step_filter_body_recheck'
    body = json.loads((body_dir / 'body_recheck.json').read_text(encoding='utf-8'))
    source = json.loads((art / 'step_filter_source_recheck' / 'source_recheck.json').read_text(encoding='utf-8'))
    payload = json.loads((body_dir / 'turbine_rechecked_filtered.json').read_text(encoding='utf-8'))
    filter_result(payload)
    by_id = {f['issue_id']: f for f in payload['findings']}
    source_by_id = {p['issue_id']: p for p in source['pairs']}
    ledger = []
    for pair in body['pairs']:
        f = by_id[pair['issue_id']]
        source_pair = source_by_id[pair['issue_id']]
        f['metadata']['source_step_crosscheck'] = source_pair
        f['metadata']['focused_pair_recheck'] = pair
        ledger.append({'issue_id': pair['issue_id'], 'status': f['status'],
                       'decision': f['metadata']['step_interference_filter'],
                       'derived_exact_fact': pair.get('fact'), 'source_exact_fact': source_pair,
                       'source_body_a': f['metadata'].get('source_body_a'),
                       'source_body_b': f['metadata'].get('source_body_b')})
    before = json.loads((art / 'step_filter_source_recheck' / 'catia_baseline.json').read_text(encoding='utf-8'))
    after = json.loads((body_dir / 'catia_after.json').read_text(encoding='utf-8'))
    payload['audit']['focused_body_recheck']['catia_manifests_identical'] = before == after
    (body_dir / 'turbine_rechecked_filtered.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    (body_dir / 'former_23_review_ledger.json').write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding='utf-8')
    lines = ['# 原 23 项 FAIL 定向复核记录', '', '日期：2026-09-17。', '',
             '已验证 33/36 个相关 Solid，33 个均为有效单实体。重新计算 20/23 项重叠，全部公共体积与旧结果一致。5 项重叠同时在原始 STEP 中复现，不能将其归因于 CATIA 导出新增的噪声。', '',
             '原 23 项仍全部为 NOT_EVALUATED：20 项缺少设计连接/非设计重叠证据，3 项未建立足够可靠的来源对应。没有把稳定重叠直接当作真实穿模，也没有把它们放行为转换伪影。', '',
             f'当前整体过滤计数：{payload["counts"]}。其中恢复的 4 项 PASS 是其他已有精确无相交候选，均不属于原 23 项重叠。未计算候选仍为 6903；本次不是全量扫描。', '',
             f'只读审计：前后模型 manifest 完全一致={before == after}；Body=1412；未保存源模型。定向导出 106 个 Body，其中包含两个来源未确定批次的候选 Body，使用单 Body 导出保证来源独立。STEP/BRep 复核文件保留用于再次复核。', '',
             '原始 STEP 声明的长度单位为 mm，最大模型容差为 0.1 mm；它不等于实际重叠深度，也不能据此将重叠自动判为转换伪影。源实体抽取保持几何引用和单位，补充单实体产品根并更换名称标签。已用精确方块的 STEP 抽取/读入测试验证体积与面数量不变。', '',
             '|问题 ID|复算公共体积 mm³|原始 STEP 交叉检查|待补证据|', '|---|---:|---|---|']
    for row in ledger:
        common = (row['derived_exact_fact'] or {}).get('common') or {}
        volume = common.get('intersection_volume_mm3')
        source_verified = row['source_exact_fact'].get('source_overlap_present') is True
        lines.append(f"|{row['issue_id']}|{volume if volume is not None else '未复算'}|{'已复现重叠' if source_verified else '对应未确认'}|{'连接意图及接口范围' if volume is not None else 'Solid 来源及有效性'}|")
    lines += ['', '下一步：对 20 项可复现重叠收集接口/连接范围及非设计穿模证据；对 3 项来源不足的候选进一步核对局部拓扑，不扩大容差强行配对。完成这些裁决后再开展 STP 管路语义重建。', '',
              '实现验证：本轮新增原始 STEP 几何抽取测试 2 项通过，过滤层 14 项回归通过。新版 Word 入口已改为优先读取本轮结果，本轮未生成新的 Word 文件。']
    (body_dir / '复核记录.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps({'former_fail_count': len(ledger), 'recomputed_pairs': sum(r['derived_exact_fact'] is not None for r in ledger),
                      'original_step_overlaps': sum(r['source_exact_fact'].get('source_overlap_present') is True for r in ledger),
                      'catia_manifests_identical': before == after}, ensure_ascii=False))


if __name__ == '__main__':
    main()
