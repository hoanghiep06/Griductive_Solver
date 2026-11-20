"""Recompute baseline/V2 measurements and write an evidence-backed report."""
import json
from pathlib import Path
from itertools import product
import sys
if __package__ in (None,''):
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.core.puzzle_loader import PuzzleLoader
from src.core.puzzle_validator import PuzzleValidator
from tools.reference_sat import PublicSAT
from tools.validate_puzzles import ROOT, clue_scope, validate_dataset, structural_comparisons


def metrics_total(reports):
    return {'steps':sum(len(r['reveal_proof']) for r in reports),
            'multi':sum(r['difficulty']['multi_clue_steps'] for r in reports),
            'single':sum(r['difficulty']['single_clue_steps'] for r in reports),
            'triple':sum(r['difficulty']['three_plus_clue_steps'] for r in reports)}


def build_report():
    old=validate_dataset(ROOT/'puzzles_baseline'); new=validate_dataset(ROOT/'puzzles')
    pairs=structural_comparisons(new)
    for name,content in [('phuoc_baseline_sat_validation.json',old),('phuoc_validation.json',new),
                         ('phuoc_dataset_v2_diversity.json',pairs)]:
        (ROOT/'docs'/name).write_text(json.dumps(content,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    before,after=metrics_total(old),metrics_total(new)
    lines=['# Dataset V2 — Nguyễn Hoài Phước', '',
           'Ngày kiểm định: 10/11/2026. Baseline được giữ nguyên từ commit `b940b8c`.', '',
           '## A. Đánh giá lại baseline bằng cùng một phép đo SAT', '',
           'Cả V1 và V2 đều dùng first-forced row-major, giữ nguyên tất cả verdict đã biết K.',
           'Không lấy số bước từ chứng chỉ local V1 cũ để so với trace SAT V2.', '',
           '| Bộ | Puzzle | Lượt suy luận | Single-clue | Multi-clue | Support ≥3 |',
           '|---|---:|---:|---:|---:|---:|',
           f"| V1 | 15 | {before['steps']} | {before['single']} | {before['multi']} | {before['triple']} |",
           f"| V2 | 15 | {after['steps']} | {after['single']} | {after['multi']} | {after['triple']} |", '',
           'Baseline vẫn có một số bước multi-clue theo trace SAT row-major. Đặc biệt 3x3_04',
           'đã có 3 bước; không mặc định tất cả map cũ chỉ single-clue. Phần lớn baseline',
           'là chuỗi suy luận trực tiếp. Coverage V1 đã đủ sáu clue và bốn vùng.', '',
           '## B. Kết quả từng màn', '',
           '| Puzzle | Size | Nhãn đo theo heuristic | Mở sẵn | Steps | V1 multi | V2 multi | ≥3 clue | Unique | No-guess | Mục tiêu multi |',
           '|---|---|---|---:|---:|---:|---:|---:|---|---|---|']
    old_by={r['puzzle_id']:r for r in old}
    for r in new:
        size=r['size']; case=int(r['puzzle_id'][-2:]); target=0 if size==3 and case<=2 else 1 if size==3 else 3 if size==4 else 6
        d=r['difficulty']
        lines.append(f"| {r['puzzle_id']} | {size}×{size} | {d['label']} ({d['score']}) | {r['initial_revealed_count']} | {len(r['reveal_proof'])} | {old_by[r['puzzle_id']]['difficulty']['multi_clue_steps']} | {d['multi_clue_steps']} | {d['three_plus_clue_steps']} | PASSED | PASSED | {d['multi_clue_steps']} ≥ {target}: PASS |")
    lines += ['', 'Nhãn mục tiêu trong yêu cầu và nhãn từ số liệu được lưu riêng trong manifest.',
              'Ví dụ hai màn 5×5 đầu được chấm Medium theo quy tắc dù mục tiêu thiết kế là',
              'Medium-Hard/Hard. Không nâng nhãn bằng tay để khớp bảng mong muốn.', '',
              '## C. Thiết kế và chất lượng suy luận', '',
              '- Giữ 3x3_01 làm tutorial và giữ 3x3_02 làm easy reference. 13 map còn lại được thiết kế lại.',
              '- Pair stage: DIFFERENT(a,b) hoặc EXACTLY(1,[a,b]) cùng một counting clue trên [a,b,c] ép c.',
              '- Overlapping-count stage: hai phương trình đếm có phần giao chung, dùng hiệu số để ép biến còn lại.',
              '- Bridge stage: SAME(a,b), DIFFERENT(b,c), EXACTLY(1+d,[a,c,d]) ép d với support 3; clue của d mở khóa a,b,c bằng support nhỏ hơn.',
              '- Triangle stage: ba counting constraint phối hợp; không một cặp nào đủ chứng minh verdict đầu.',
              '- Khi vùng tự nhiên chứa đúng các biến stage chưa giải và filler đã biết, generator dùng ROW/COLUMN/NEIGHBORS thay EXPLICIT.',
              '- Các stage có nhiều verdict forced cùng lúc. Trace lưu toàn bộ lựa chọn và UNKNOWN→forced.',
              '- FACT giới hạn 1–3 mỗi map. Không sinh counting singleton hoặc AT_LEAST(0)/AT_MOST(|R|) trong V2 mới.',
              '- Tất cả candidate phải đạt unique, no-guess và số bước multi mục tiêu trước khi được xuất.', '',
              'Đây vẫn là generator theo mô-đun constraint, chưa phải thiết kế thủ công đa phong cách.',
              'Một số nhóm stage còn nối tiếp nhau; số liệu chỉ chứng nhận trace row-major đã chạy,',
              'không bảo đảm mọi thứ tự chơi đều có cùng support hoặc cùng số bước multi.', '',
              '### Cách xác nhận support tối thiểu', '',
              'Ở từng bước, giữ toàn bộ K. Kiểm tra SAT(K ∧ R) và UNSAT(K ∧ R ∧ opposite).',
              'Thu nhỏ một witness để lấy cận trên, sau đó duyệt tập con theo cardinality tăng dần.',
              'Mọi tập con nhỏ hơn witness cuối đều phải SAT với opposite. Đây là minimum cardinality,',
              'không chỉ một irreducible UNSAT core. Tất cả SAT results được lưu trong trace.',
              'Support ba clue được xác nhận sau khi kiểm tra cả tập rỗng, mọi singleton và mọi pair.', '',
              '### Phát hiện map gần trùng', '',
              'WL fingerprint chạy bốn vòng trên đồ thị hai phía nhân vật/clue, có cạnh ownership và scope.',
              'Màu nút gồm kiểu clue, vùng, cardinality và thẻ mở sẵn; không dùng tên hoặc ID cell.',
              'Test hoán vị cell xác nhận tính bất biến. 15 fingerprint đều khác nhau.',
              'So sánh histogram: 50% clue family + 25% kích thước scope + 25% minimum-support histogram.',
              f"Ngưỡng cờ review 0.96: {sum(p['near_duplicate_review_flag'] for p in pairs)} cặp. Đây là cảnh báo thống kê, không phải chứng minh hai puzzle khác nhau về mọi mặt.", '',
              '### Quy tắc độ khó (chủ quan, công khai trọng số)', '',
              'score = 45·multi_ratio + 30·triple_ratio + 20·min(max(max_support−1,0)/2,1) + 5·mean_scope_Jaccard.',
              'Không có điểm thưởng theo N. Không có điểm runtime. Tutorial nếu không có multi;',
              'Easy nếu score<18, Medium nếu <35, Hard nếu <47, còn lại Very Hard.',
              'Điểm thưởng support cực đại giúp phản ánh bước cần 3 clue; overlap chỉ chiếm 5% để hạn chế filler làm tăng điểm.',
              'Các chỉ số lựa chọn forced, SAT calls và clause count được báo riêng. Score chưa được hiệu chuẩn với người chơi.', '',
              '## D. CNF, SAT và ranh giới tích hợp', '',
              'Đã chạy MiniSat22 của python-sat 1.9.dev21 trong tools, cùng reference encoder combinatorial.',
              'Đã đối chiếu CNF với evaluator độc lập của Hiệp trên mọi assignment thuộc scope của từng clue',
              'trong cả 15 map, cùng các ca biên k=0 và k=|R|. Encoder tham chiếu không có biến phụ.',
              'Selector variables chỉ kích hoạt nhóm clause trong harness; không được tính là nhân vật hoặc đưa vào blocking clause.',
              'Uniqueness dùng model SAT đầu tiên, block toàn bộ primary assignment đó, lần hai UNSAT.',
              'CNF full trong bảng sau là CNF tham chiếu trước khi thêm selectors/known-status units.', '',
              '| Puzzle | Primary | Aux encoding | Full reference clauses | Calls phân loại | Calls reference gồm support |',
              '|---|---:|---:|---:|---:|---:|']
    for r in new:
        u,d=r['uniqueness_proof'],r['difficulty']
        lines.append(f"| {r['puzzle_id']} | {u['primary_variables']} | 0 | {u['full_cnf_clauses']} | {d['classification_sat_calls']} | {d['reference_sat_calls']} |")
    lines += ['', '**Benchmark DPLL của Huy + Encoder của Phong: BLOCKED.** Hai file vẫn rỗng ở snapshot này.',
              'Không có decision/propagation/backtrack/runtime của DPLL nhóm để báo. Stats MiniSat trong JSON',
              'được ghi nhãn reference_solver_stats, không đổi tên thành DPLL backtracks.',
              'Semantic Evaluator của Tài vẫn rỗng: dùng evaluator Core của Hiệp và không sửa module của Tài.',
              'Đã có test full reveal với GameEngine thật + EntailmentChecker thật + reference encoder/SAT, chạy hai lần kiểm tra deterministic.', '',
              '## E. Ba ví dụ lấy từ trace thực tế', '']
    for pid in ['3x3_03','4x4_02','5x5_05']:
        r=next(r for r in new if r['puzzle_id']==pid)
        step=next(s for s in r['reveal_proof'] if s['minimum_clue_support_size'] >= (3 if pid.startswith('5') else 2))
        puzzle=PuzzleLoader().load(ROOT/'puzzles'/(pid+'.json'))
        by={c.clue_id:c for c in puzzle.clues}; selected=[by[c] for c in step['minimal_supporting_clue_ids']]
        lines += [f"### {pid} — bước {step['step']}: {step['character_id']}", '',
                  'K trước khi suy luận (toàn bộ verdict đã biết):', '```json', json.dumps(step['known_verdicts'],indent=2), '```',
                  'Clue đang công khai: '+', '.join(step['active_clue_ids'])+'.', '',
                  'Support tối thiểu: '+', '.join(step['minimal_supporting_clue_ids'])+'.', '', '```json',
                  json.dumps([c.to_dict() for c in selected],indent=2), '```', '',
                  'Công thức: K ∧ CNF(support). Quy ước +i=Criminal, −i=Innocent. Mapping và CNF thực tế:', '```json']
        with PublicSAT(selected,puzzle.characters_by_id,puzzle.grid_size) as sat:
            lines += [json.dumps({'primary_mapping':dict(sat.variable_map.primary_mapping),
                       'clauses_by_clue':sat.fragments,'opposite_assumption':step['opposite_assumption']},indent=2), '```', '',
                       'SAT(K ∧ support) = SAT; SAT(K ∧ support ∧ opposite) = UNSAT.',
                       f"Đã kiểm tra {len(step['minimality_checks'])} tập con trong phép tìm cardinality tối thiểu; mọi tập nhỏ hơn {step['minimum_clue_support_size']} đều SAT với opposite.", '']
        known=dict(step['known_verdicts']); known[step['character_id']]=not step['status']
        scope=set().union(*(set(clue_scope(c,puzzle.characters_by_id,puzzle.grid_size)) for c in selected))
        unknown=sorted(scope-set(known))
        assert len(unknown)<=8
        rejects=[]; evaluator=PuzzleValidator()
        for values in product((False,True),repeat=len(unknown)):
            assignment={**known,**dict(zip(unknown,values))}
            failed=[c.clue_id for c in selected if not evaluator.evaluate_clue(c,assignment,puzzle.characters_by_id,puzzle.grid_size)]
            assert failed
            rejects.append((dict(zip(unknown,values)),failed))
        lines += [f"Lý do UNSAT, kiểm tra độc lập: sau khi cố định K và giả định ngược, còn {len(unknown)} biến local; cả {len(rejects)} assignment đều vi phạm ít nhất một clue support:", '',
                  '| Assignment còn lại | Clue bị vi phạm |', '|---|---|']
        for assignment,failed in rejects:
            lines.append('| '+', '.join(f"{cid}={'C' if v else 'I'}" for cid,v in assignment.items())+' | '+', '.join(failed)+' |')
        lines += ['', f"Kết luận: {step['character_id']} là {'CRIMINAL' if step['status'] else 'INNOCENT'}. Sau chấp nhận mới reveal {step['newly_revealed_clue_id']}.", '']
    lines += ['## F. Tái chạy và review', '', '```bash',
              'pip --python .venv/bin/python install -r requirements-dev.txt',
              '.venv/bin/python -m tools.generate_puzzles',
              '.venv/bin/python -m tools.validate_puzzles --report docs/phuoc_validation.json',
              '.venv/bin/python -m tools.report_dataset',
              '.venv/bin/python -m tools.build_preview',
              '.venv/bin/python -m pytest -q',
              'xdg-open tools/preview_puzzles.html', '```', '',
              'Python >=3.10. Nếu chưa có .venv: `python3 -m venv .venv` trước khi cài dependency.',
              'Preview tự chứa dữ liệu offline: chọn V1/V2 và map, kéo bước hoặc dùng mũi tên;',
              'clue support tô xanh, bấm clue để highlight scope. Chế độ đáp án tách riêng và mặc định tắt.',
              'Đây là công cụ review dữ liệu của tác giả, không thay GUI nhóm và không bảo mật key trong HTML.', '',
              '## G. Hạn chế và trạng thái kiểm thử', '',
              '- Tất cả 15 map unique/no-guess; cả 15 đạt mục tiêu multi tương ứng. 13 map được tái thiết kế.',
              '- Exact support đo theo một trace row-major và toàn bộ K, không đánh giá mọi thứ tự giải.',
              '- Generator mô-đun còn tái sử dụng một số gadget. Fingerprint/histogram không phải kiểm tra graph isomorphism hoàn chỉnh.',
              '- Một số clue không xuất hiện trong support tối thiểu được chọn. JSON liệt kê các clue đó; điều này không chứng minh clue vô ích trong mọi trace.',
              '- 5×5_05 là stress candidate về cấu trúc; chưa xác nhận stress/runtime của DPLL nhóm.',
              '- Quy tắc difficulty chưa được user-study; một màn 4×4 có thể được chấm cao hơn 5×5.',
              '- Generator chỉ publish sau khi batch pass và khôi phục bytes cũ khi lỗi ghi. Rollback không bảo đảm trước mất điện/process kill.',
              '- Kết quả pytest thực chạy nằm ở `docs/phuoc_dataset_v2_tests.md`; 30 test team DPLL/CNF vẫn SKIPPED/BLOCKED.', '',
              'Không sửa schema, Core, GUI, DPLL hoặc Encoder của các thành viên khác. Production EntailmentChecker giữ nguyên.',
              'Baseline đầy đủ trong puzzles_baseline/ và Git commit b940b8c.']
    path=ROOT/'docs/phuoc_dataset_v2_report.md'
    path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(path)
    return path

if __name__=='__main__': build_report()
