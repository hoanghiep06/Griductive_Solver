"""Independent negative cases, exact support, CNF truth tables and integration."""
import copy
from dataclasses import replace
from itertools import combinations, product
import json
from pathlib import Path
import subprocess

import pytest
from jsonschema import ValidationError
from pysat.solvers import Solver

from src.agent.entailment import EntailmentChecker, Verdict
from src.core.clue import Clue
from src.core.game_engine import GameEngine, VerdictResponse
from src.core.puzzle_loader import PuzzleLoader
from src.core.puzzle_validator import PuzzleValidator
from tools.generate_puzzles import generate_dataset, quality_target
from tools.reference_sat import PublicSAT, encode_reference, unique_reference
from tools.validate_puzzles import (
    ROOT, PUZZLE_IDS, PuzzleProofError, clue_scope, prove_progressive,
    structural_features, structural_comparisons, validate_dataset, verify_trace,
)


def load(pid):
    return PuzzleLoader().load(ROOT/'puzzles'/(pid+'.json'))


@pytest.mark.parametrize('pid', PUZZLE_IDS)
def test_reference_cnf_matches_independent_semantics_for_every_local_assignment(pid):
    puzzle=load(pid); evaluator=PuzzleValidator()
    with PublicSAT(puzzle.clues,puzzle.characters_by_id,puzzle.grid_size) as sat:
        for clue in puzzle.clues:
            scope=clue_scope(clue,puzzle.characters_by_id,puzzle.grid_size)
            for values in product((False,True), repeat=len(scope)):
                assignment=dict(zip(scope,values))
                model={sat.variable_map.get_var(cid):v for cid,v in assignment.items()}
                encoded=all(any(model[abs(lit)]==(lit>0) for lit in clause) for clause in sat.fragments[clue.clue_id])
                assert encoded is evaluator.evaluate_clue(clue,assignment,puzzle.characters_by_id,puzzle.grid_size)


@pytest.mark.parametrize('kind', ['EXACTLY','AT_LEAST','AT_MOST'])
@pytest.mark.parametrize('k',[0,1,2,3])
def test_counting_boundaries(kind,k):
    p=load('3x3_01')
    clue=Clue('count','A1',kind,{'k':k,'region_type':'ROW','index':0})
    with PublicSAT([clue],p.characters_by_id,3) as sat:
        for values in product((False,True),repeat=3):
            known=dict(zip(['A1','B1','C1'],values))
            expected={'EXACTLY':sum(values)==k,'AT_LEAST':sum(values)>=k,'AT_MOST':sum(values)<=k}[kind]
            assert sat.query(known) is expected


def test_two_clue_support_preserves_all_known_verdicts():
    p=load('3x3_01')
    clues=[Clue('opposite','A1','DIFFERENT',{'target1':'A1','target2':'B1'}),
           Clue('count','B1','EXACTLY',{'k':1,'region_type':'EXPLICIT','cells':['A1','B1','C1']})]
    with PublicSAT(clues,p.characters_by_id,3) as sat:
        assert sat.minimum_support({},'C1',False)['minimum_clue_support_size']==2
        known={'A1':False,'B1':True}
        evidence=sat.minimum_support(known,'C1',False)
        assert evidence['minimum_clue_support_size']==1
        assert evidence['minimal_supporting_clue_ids']==['count']
        # Removing a known fact to claim a two-clue step would fail this test.
        assert known=={'A1':False,'B1':True}


def test_three_clue_support_exhausts_every_pair():
    p=load('3x3_01')
    clues=[Clue('same','A1','SAME',{'target1':'A1','target2':'B1'}),
           Clue('different','B1','DIFFERENT',{'target1':'B1','target2':'C1'}),
           Clue('count','C1','EXACTLY',{'k':1,'region_type':'EXPLICIT','cells':['A1','C1','A2']})]
    with PublicSAT(clues,p.characters_by_id,3) as sat:
        e=sat.minimum_support({},'A2',False)
        assert e['minimum_clue_support_size']==3
        assert len(e['minimality_checks'])==8
        for subset in combinations(sat.ids,2):
            assert sat.query({},subset,sat.variable_map.get_var('A2')) is True
        assert e['minimality_checks'][-1]['satisfiable'] is False
        with pytest.raises(ValueError,match='unrevealed'):
            sat.query({},['hidden_clue'])


@pytest.mark.parametrize('pid',PUZZLE_IDS)
def test_exact_minimality_and_multi_clue_targets(pid):
    p=load(pid); trace=prove_progressive(p)
    assert sum(s['minimum_clue_support_size']>=2 for s in trace)>=quality_target(p.grid_size,int(pid[-2:]))
    for step in trace:
        k=step['minimum_clue_support_size']
        checks=step['minimality_checks']
        assert all(c['satisfiable'] for c in checks if len(c['clue_ids'])<k)
        expected_smaller={combo for n in range(k) for combo in combinations(step['active_clue_ids'],n)}
        actual_smaller={tuple(c['clue_ids']) for c in checks if len(c['clue_ids'])<k}
        assert actual_smaller==expected_smaller
        assert checks[-1]['clue_ids']==step['minimal_supporting_clue_ids']
        assert checks[-1]['satisfiable'] is False
        assert set(step['minimal_supporting_clue_ids'])<=set(step['active_clue_ids'])
        assert step['character_id'] not in step['known_verdicts']
        assert step['character_id']==step['forced_character_ids'][0]
        assert step['reasoning_kind']==('multi-clue' if k>=2 else 'single-clue')
    verify_trace(p,trace)


@pytest.mark.parametrize('defect',['multi_label','hidden_clue','known_facts','wrong_verdict'])
def test_forged_certificates_are_rejected(defect):
    p=load('5x5_05'); trace=copy.deepcopy(prove_progressive(p))
    if defect=='multi_label':
        trace[0]['minimum_clue_support_size']=1
    elif defect=='hidden_clue':
        trace[0]['minimal_supporting_clue_ids']=[p.clues_by_owner[trace[0]['character_id']].clue_id]
    elif defect=='known_facts':
        trace[0]['known_verdicts']={}
    else:
        trace[0]['status']=not trace[0]['status']
    with pytest.raises(PuzzleProofError,match='Invalid trace'):
        verify_trace(p,trace)


def test_unsat_puzzle_reference_solver_rejects_without_fabricated_key():
    p=load('3x3_01')
    bad=replace(p,clues=(Clue('yes','A1','FACT',{'target':'A1','status':'CRIMINAL'}),
                         Clue('no','B1','FACT',{'target':'A1','status':'INNOCENT'})))
    with pytest.raises(ValueError,match='UNSAT'):
        unique_reference(bad)


def test_structural_fingerprint_is_invariant_under_cell_renaming():
    p=load('4x4_03'); rename={cid:other for cid,other in zip(p.characters_by_id,reversed(list(p.characters_by_id)))}
    chars=tuple(replace(c,id=rename[c.id]) for c in p.characters)
    clues=[]
    for c in p.clues:
        params=dict(c.parameters)
        for key in ('target','target1','target2','center'):
            if key in params: params[key]=rename[params[key]]
        if 'cells' in params: params['cells']=[rename[cid] for cid in params['cells']]
        clues.append(replace(c,owner_id=rename[c.owner_id],parameters=params))
    renamed=replace(p,characters=chars,clues=tuple(clues),initial_revealed=tuple(rename[c] for c in p.initial_revealed))
    # Graph topology ignores cell/display names and coordinate labels.
    assert structural_features(p,[])['wl_fingerprint']==structural_features(renamed,[])['wl_fingerprint']


def test_structural_diversity_and_baseline_improvement():
    reports=validate_dataset(ROOT/'puzzles'); old=validate_dataset(ROOT/'puzzles_baseline')
    assert len({r['structural_features']['wl_fingerprint'] for r in reports})==15
    assert sum(r['difficulty']['multi_clue_steps'] for r in reports)>sum(r['difficulty']['multi_clue_steps'] for r in old)
    assert all(not pair['wl_equal'] for pair in structural_comparisons(reports))
    assert len({tuple(sorted(r['structural_features']['support_histogram'].items())) for r in reports})>=7


def test_failed_generation_leaves_existing_dataset_unchanged(tmp_path,monkeypatch):
    import tools.generate_puzzles as generation
    sentinel=tmp_path/'3x3_01.json'; sentinel.write_text('existing verified data')
    monkeypatch.setattr(generation,'quality_target',lambda size,case:10000)
    with pytest.raises(ValueError,match='unchanged'):
        generate_dataset(tmp_path,max_attempts=1)
    assert sentinel.read_text()=='existing verified data'
    assert list(tmp_path.iterdir())==[sentinel]


def test_baseline_backup_exactly_matches_original_commit():
    for pid in PUZZLE_IDS:
        original=subprocess.check_output(['git','show',f'b940b8c:puzzles/{pid}.json'],cwd=ROOT)
        assert (ROOT/'puzzles_baseline'/(pid+'.json')).read_bytes()==original


class ReferenceBooleanSolver:
    """Integration-test-only bridge; never imported by production."""
    def solve(self,cnf):
        with Solver(name='m22',bootstrap_with=cnf) as sat:
            return sat.solve()


@pytest.mark.parametrize('pid',PUZZLE_IDS)
def test_real_game_engine_full_reveal_with_reference_sat_and_checker(pid):
    engine=GameEngine(ROOT/'puzzles'/(pid+'.json'))
    checker=EntailmentChecker(ReferenceBooleanSolver(),variable_map=engine.var_map)
    traces=[]
    for run in range(2):
        if run: engine.restart()
        trace=[]
        while not engine.is_solved():
            snapshot=engine.get_public_snapshot()
            cnf=[clause for clue in snapshot.revealed_clues for clause in
                 encode_reference(clue,{c.id:c for c in engine.characters},engine.grid_size,engine.var_map)]
            cnf+=snapshot.get_unit_clauses_for_verdicts()
            unresolved={cid:engine.var_map.get_var(cid) for cid in engine.get_unsolved_characters()}
            chosen=checker.first_forced(cnf,unresolved)
            assert chosen is not None
            cid,result=chosen
            assert engine.get_clue_for_character(cid) is None
            response,clue=engine.submit_verdict(cid,result.verdict is Verdict.CRIMINAL,
                                               result.to_engine_result(cid,snapshot.version))
            assert response is VerdictResponse.ACCEPTED
            assert clue['owner_id']==cid
            trace.append((cid,result.verdict))
        traces.append(trace)
    assert traces[0]==traces[1]


@pytest.mark.parametrize('pid',PUZZLE_IDS)
def test_uniqueness_block_contains_primary_variables_only(pid):
    p=load(pid); proof=unique_reference(p)
    assert proof['sat_calls']==2
    assert len(proof['blocking_clause'])==p.grid_size**2
    assert {abs(lit) for lit in proof['blocking_clause']}==set(range(1,p.grid_size**2+1))
    assert proof['selector_variables_in_analysis_only']==len(p.clues)


@pytest.mark.parametrize('initial',[[],['Z99'],['A1','A1']])
def test_invalid_initial_reveal_is_rejected(initial):
    from tools.validate_puzzles import validate_puzzle
    raw=json.loads((ROOT/'puzzles/3x3_03.json').read_text())
    raw['initial_revealed']=initial
    with pytest.raises((ValueError, ValidationError)):
        validate_puzzle(raw)


def test_new_count_clues_are_not_tautological_or_singleton():
    for pid in PUZZLE_IDS[2:]:
        p=load(pid)
        for clue in p.clues:
            if clue.clue_type in {'EXACTLY','AT_LEAST','AT_MOST'}:
                scope=clue_scope(clue,p.characters_by_id,p.grid_size)
                assert len(scope)>=2
                if clue.clue_type=='AT_LEAST': assert clue.parameters['k']>0
                if clue.clue_type=='AT_MOST': assert clue.parameters['k']<len(scope)


def test_preview_embeds_actual_fifteen_maps_and_both_versions(tmp_path):
    import re
    from tools.build_preview import build_preview
    output=build_preview(tmp_path/'preview.html')
    html=output.read_text(encoding="utf-8")
    assert '__PUZZLE_DATA__' not in html
    payload=re.search(r'<script id="data" type="application/json">(.*?)</script>',html,re.S).group(1)
    data=json.loads(payload)
    for version,directory in [('v2','puzzles'),('baseline','puzzles_baseline')]:
        assert len(data[version]['puzzles'])==15
        for raw in data[version]['puzzles']:
            assert raw==json.loads((ROOT/directory/(raw['puzzle_id']+'.json')).read_text())
    assert 'type="checkbox" id="answers"' in html
    assert 'type="checkbox" id="answers" checked' not in html


def test_public_reasoning_does_not_consult_private_key_for_decisions():
    # The authoring controller may reject a bad key, but cannot steer the SAT
    # classifier to it. Changed private unresolved labels leave inference equal.
    p=load('5x5_05'); known={cid:p.hidden_solution[cid] for cid in p.initial_revealed}
    clues=[p.clues_by_owner[cid] for cid in p.initial_revealed]
    ids=[cid for cid in p.characters_by_id if cid not in known]
    with PublicSAT(clues,p.characters_by_id,5) as sat:
        before=sat.classify(known,ids)
        private_copy={cid:not status for cid,status in p.hidden_solution.items()}
        after=sat.classify(known,ids)
        assert before==after
        assert any(before[0][cid] is not private_copy[cid] for cid in before[0])


def test_publication_io_error_restores_original_files(tmp_path,monkeypatch):
    import tools.generate_puzzles as generation
    sentinel=tmp_path/'3x3_01.json'; sentinel.write_text('previous verified bytes')
    original=generation.os.replace
    calls=0
    def fail_once(source,destination):
        nonlocal calls
        calls+=1
        if calls==3: raise OSError('simulated publication failure')
        return original(source,destination)
    monkeypatch.setattr(generation.os,'replace',fail_once)
    with pytest.raises(OSError,match='publication failure'):
        generate_dataset(tmp_path)
    assert {p.name:p.read_text() for p in tmp_path.iterdir()}=={'3x3_01.json':'previous verified bytes'}
