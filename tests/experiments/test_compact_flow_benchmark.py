"""Synthetic cost, streaming, provenance and history-only boundary checks."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
import pytest
import yaml

from src.experiments import compact_flow_benchmark as bench
from src.flow.base import FlowResult
from src.flow.compact import build_compact_requests
from src.prediction.reference import HistoryBatch, VideoReference


def window(origin=19, track="A"):
    return dict(window_id=f"11/{track}/{origin}", video_id="11", track_id=track,
        segment_id=f"11/{track}/0", split="train", history_start=origin-19,
        origin_frame=origin, future_end=origin+10, history_length=20, forecast_horizon=10)


def requests(point=(1.25, 1.5)):
    rows = (window(), window(20), window(59))
    return build_compact_requests([HistoryBatch(np.tile(point, (3, 20, 1)).astype(np.float64), rows)], video_id="11")


class Capture:
    def __init__(self, fail_at=None, jump=False, bad_shape=False, wrong_fps=False, opened=True):
        self.reads, self.released = 0, False
        self.fail_at, self.jump, self.bad_shape, self.wrong_fps, self.opened = fail_at, jump, bad_shape, wrong_fps, opened
    def isOpened(self): return self.opened
    def getBackendName(self): return "SYNTHETIC"
    def get(self, prop):
        if prop == cv2.CAP_PROP_POS_FRAMES: return self.reads + (1 if self.jump and self.reads == 5 else 0)
        return {cv2.CAP_PROP_FRAME_COUNT:1470,cv2.CAP_PROP_FRAME_WIDTH:4,cv2.CAP_PROP_FRAME_HEIGHT:3,
                cv2.CAP_PROP_FPS:48 if self.wrong_fps else 49}[prop]
    def read(self):
        frame=self.reads; self.reads+=1
        assert frame < 60, "Future frame60 requested"
        if frame==self.fail_at: return False,None
        shape=(3,5,3) if self.bad_shape and frame==3 else (3,4,3)
        return True,np.full(shape,frame,np.uint8)
    def release(self): self.released=True


class Estimator:
    def __init__(self, **params): self.reset_called=False;self.calls=[]
    def reset(self): self.reset_called=True
    def estimate(self, a, b):
        assert self.reset_called
        self.calls.append((int(a[0,0]),int(b[0,0])))
        flow=np.ones((*a.shape,2),np.float32)
        flow[:,:,1]=.5
        return FlowResult(flow)


SPEC=dict(width=4,height=3,fps=49.,total_frames=1470,sha256="a"*64)


def stream(tmp_path,monkeypatch,capture,point=(1.25,1.5),progress=lambda:None):
    monkeypatch.setattr(bench,"REPOSITORY_ROOT",tmp_path)
    req=requests(point);estimator=Estimator()
    result,artifacts=bench.stream_prefix(tmp_path/'not_a_video.mp4',SPEC,req,tmp_path,
        params={},estimator_hash="b"*64,capture_factory=lambda p:capture,
        estimator_factory=lambda **kw:estimator,check_progress=progress)
    return req,estimator,result,artifacts


def test_exact_stream_counts_checkpoints_and_all_witnesses(tmp_path,monkeypatch):
    cap=Capture();req,est,result,artifacts=stream(tmp_path,monkeypatch,cap)
    assert cap.released and cap.reads==60
    assert est.calls==[(a,b) for s in range(59) for a,b in ([(s,s+1),(s+1,s)] if s in (0,58) else [(s,s+1)])]
    assert result['forward_fields']==59 and result['backward_fields']==2
    assert result['historical_uses']==57 and result['unique_samples']==39
    assert result['eligible_last5_windows']==3
    assert set(p.name for p in (tmp_path/'frames').iterdir())=={'000000.npy','000001.npy','000058.npy','000059.npy'}
    for ref in artifacts:
        p=tmp_path/ref['path'];assert p.stat().st_size==ref['bytes']
        assert hashlib.sha256(p.read_bytes()).hexdigest()==ref['sha256']
    with np.load(tmp_path/'witnesses.npz',allow_pickle=False) as data:
        assert data['corner_uv'].dtype==np.float32 and data['points_xy'].dtype==np.float64
        assert len(data['sample_ids'])==39
        np.testing.assert_array_equal(data['corner_uv'][:,:,0],np.ones((39,4)))
        assert json.loads(str(data['metadata']))['video_id']=='11'
    index=json.loads((tmp_path/'pair_index.json').read_text())
    assert [r['frame_from'] for r in index['pairs']]==list(range(59))
    assert [r['frame_from'] for r in index['pairs'] if 'checkpoint' in r]==[0,58]
    frameindex=json.loads((tmp_path/'frame_index.json').read_text())
    assert not frameindex['full_video_decoding_verified']
    assert len(frameindex['frames'])==60
    assert all(r['gray_sha256']==hashlib.sha256(np.full((3,4),i,np.uint8).tobytes()).hexdigest() for i,r in enumerate(frameindex['frames']))


def test_invalid_is_preserved_as_blank_and_explicit_reason(tmp_path,monkeypatch):
    _,_,result,_=stream(tmp_path,monkeypatch,Capture(),point=(-.01,1.5))
    assert result['unique_samples']==39 and result['valid_samples']==0 and result['eligible_last5_windows']==0
    with (tmp_path/'features.csv').open(newline='') as f: rows=list(csv.DictReader(f))
    assert len(rows)==39 and all(r['u']==r['v']=='' and r['valid']=='False' and r['reason']=='outside_image' for r in rows)
    with (tmp_path/'window_coverage.csv').open(newline='') as f: rows=list(csv.DictReader(f))
    assert len(rows)==3 and all(json.loads(r['invalid_reasons_last5'])=={'outside_image':5} for r in rows)


@pytest.mark.parametrize('fail_at',[0,1,19,59])
def test_incomplete_prefix_fails_and_releases_without_extra_reads(tmp_path,monkeypatch,fail_at):
    cap=Capture(fail_at=fail_at)
    with pytest.raises(ValueError,match='Incomplete prefix'):stream(tmp_path,monkeypatch,cap)
    assert cap.released and cap.reads==fail_at+1
    assert not (tmp_path/'witnesses.npz').exists()


@pytest.mark.parametrize('fault',['jump','bad_shape','wrong_fps','opened'])
def test_decoder_contract_rejects_invalid_metadata_or_position(tmp_path,monkeypatch,fault):
    cap=Capture(**{fault:False if fault=='opened' else True})
    with pytest.raises(ValueError):stream(tmp_path,monkeypatch,cap)
    assert cap.released


def test_budget_stop_releases_and_preserves_partial_files(tmp_path,monkeypatch):
    cap=Capture()
    def progress():
        if cap.reads==7:raise RuntimeError('budget')
    with pytest.raises(RuntimeError,match='budget'):stream(tmp_path,monkeypatch,cap,progress=progress)
    assert cap.reads==7 and cap.released
    assert (tmp_path/'checkpoints/000000_000001.npz').exists()
    assert not (tmp_path/'pair_index.json').exists()


def test_exclusive_output_cannot_overwrite(tmp_path,monkeypatch):
    stream(tmp_path,monkeypatch,Capture())
    digest=hashlib.sha256((tmp_path/'witnesses.npz').read_bytes()).hexdigest()
    with pytest.raises(FileExistsError):stream(tmp_path,monkeypatch,Capture())
    assert hashlib.sha256((tmp_path/'witnesses.npz').read_bytes()).hexdigest()==digest


def test_history_iterator_scans_once_never_slices_targets_and_detaches():
    actual=np.arange(100*2,dtype=np.float64).reshape(100,2)
    accesses=[]
    class OnlyHistorical:
        def __getitem__(self,k):
            assert isinstance(k,slice) and k.stop-k.start==20
            assert k.stop<=60
            accesses.append(k)
            return actual[k]
    specs=tuple(tuple(window(origin).values()) for origin in [19,20,59,60])
    ref=VideoReference('11',49.,'{}',{'11/A/0':OnlyHistorical()},{'11/A/0':0},specs)
    batches=list(ref.iter_history_batches(first_origin=19,last_origin=59,batch_size=2))
    assert [len(b.window_rows) for b in batches]==[2,1]
    assert [r['origin_frame'] for b in batches for r in b.window_rows]==[19,20,59]
    assert all(not hasattr(b,'targets') for b in batches)
    assert len(accesses)==3
    actual[:]=-999
    assert batches[0].histories[0,0,0]==0
    with pytest.raises(ValueError):batches[0].histories.setflags(write=True)


@pytest.mark.parametrize('kw',[dict(first_origin=18,last_origin=59),dict(first_origin=True,last_origin=59),
    dict(first_origin=19,last_origin=18),dict(first_origin=19,last_origin=59.,batch_size=2),dict(first_origin=19,last_origin=59,batch_size=0)])
def test_history_iterator_rejects_invalid_bounds(kw):
    ref=VideoReference('11',49.,'{}',{}, {},())
    with pytest.raises(ValueError):list(ref.iter_history_batches(**kw))


def test_history_iterator_empty_does_not_select_replacement():
    ref=VideoReference('11',49.,'{}',{}, {},())
    assert list(ref.iter_history_batches(first_origin=19,last_origin=59))==[]


def projection_fixture():
    plan=yaml.safe_load((bench.REPOSITORY_ROOT/bench.PLAN_PATH).read_text())
    videos=[dict(video_id=v,windows=10,unique_samples=28,loop_seconds=1.,table_seconds=.25,
                 checkpoint_seconds=.5,compact_bytes=1024,checkpoint_bytes=2048) for v in bench.TRAIN_IDS]
    return plan,videos


def test_projection_uses_density_window_scaling_and_fixed_overhead_once():
    plan,videos=projection_fixture();elapsed=100.
    actual=bench.projection(plan,videos,elapsed)
    fixed=elapsed-12*1.75
    scales=[(max((plan['sources'][r['video_id']]['total_frames']-1)/59,plan['sources'][r['video_id']]['full_unique_samples']/28),
             max(plan['sources'][r['video_id']]['full_windows']/10,plan['sources'][r['video_id']]['full_unique_samples']/28,
                 plan['sources'][r['video_id']]['total_frames']/60,(plan['sources'][r['video_id']]['total_frames']-1)/59)) for r in videos]
    expected=2*(fixed+sum(a+.25*b+.5 for a,b in scales))
    assert actual['projected_seconds']==pytest.approx(expected)
    assert actual['projected_artifact_bytes']==pytest.approx(2*sum(1024*b+2048 for a,b in scales)+16*1024**2)
    assert not actual['full_extraction_released'] and not actual['full_rss_certified']
    assert actual['status']=='exceeds_planning_budget'


def test_projection_scales_frame_and_pair_indices_even_with_fewer_later_cells():
    plan,rows=projection_fixture()
    for r in rows:
        r['windows']=plan['sources'][r['video_id']]['full_windows']
        r['unique_samples']=plan['sources'][r['video_id']]['full_unique_samples']
    result=bench.projection(plan,rows,100.)
    for term in result['terms']:
        frames=plan['sources'][term['video_id']]['total_frames']
        assert term['table_scale']==max(frames/60,(frames-1)/59)


@pytest.mark.parametrize('fault',['zero_windows','zero_samples','missing_video','negative_time','nonfinite_time','total_too_short'])
def test_projection_refuses_missing_cost_evidence(fault):
    plan,rows=projection_fixture();total=100.
    if fault=='zero_windows':rows[0]['windows']=0
    elif fault=='zero_samples':rows[0]['unique_samples']=0
    elif fault=='missing_video':rows.pop()
    elif fault=='negative_time':rows[0]['loop_seconds']=-1
    elif fault=='nonfinite_time':rows[0]['table_seconds']=float('nan')
    else:total=1
    with pytest.raises(ValueError):bench.projection(plan,rows,total)


@pytest.mark.parametrize('field,new', [('sample',{'last_frame':60}),('params',{'winsize':31}),('run',{'split':'test'})])
def test_mutated_plan_fails_before_other_files(tmp_path,monkeypatch,field,new):
    data=yaml.safe_load((bench.REPOSITORY_ROOT/bench.PLAN_PATH).read_text());data[field].update(new)
    path=tmp_path/bench.PLAN_PATH;path.parent.mkdir(parents=True);path.write_text(yaml.safe_dump(data))
    monkeypatch.setattr(bench,'REPOSITORY_ROOT',tmp_path)
    monkeypatch.setattr(bench,'sha256_file',lambda p:pytest.fail('altered plan reached later input'))
    with pytest.raises(ValueError,match='registered plan'):bench.load_benchmark_plan(path)
