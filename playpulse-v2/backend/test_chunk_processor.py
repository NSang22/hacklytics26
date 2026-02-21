"""Quick smoke test for chunk_processor.py in MOCK_MODE."""
import sys, asyncio
sys.path.insert(0, '.')

from models import DFAConfig, DFAState
from chunk_processor import process_all_chunks, stitch_chunk_results

dfa = DFAConfig(states=[
    DFAState(name='tutorial',  intended_emotion='calm',       acceptable_range=(0.0,  0.35), expected_duration_sec=30),
    DFAState(name='pit',       intended_emotion='tense',      acceptable_range=(0.45, 0.75), expected_duration_sec=10),
    DFAState(name='boss',      intended_emotion='frustrated', acceptable_range=(0.5,  0.9),  expected_duration_sec=20),
])

# 6 fake chunks = 60 seconds of gameplay
fake_chunks = [b'fakevideobytes'] * 6

async def run():
    results = await process_all_chunks(
        chunk_data_list=fake_chunks,
        dfa_config=dfa,
        session_id='test-session-001',
    )
    print(f"Processed {len(results)} chunks")
    for r in results:
        print(f"  chunk {r.chunk_index:02d}  end_state={r.end_state:<12}  deaths={r.cumulative_deaths}  events={len(r.events)}")

    stitched = stitch_chunk_results(results)
    print(f"\nTimeline entries : {len(stitched['timeline'])}")
    print(f"Transitions      : {len(stitched['transitions'])}")
    print(f"Total deaths     : {stitched['total_deaths']}")

    # Verify structure
    assert len(results) == 6, "Expected 6 chunk results"
    for r in results:
        assert r.time_range_sec[0] < r.time_range_sec[1], "Invalid time range"
        assert len(r.states_observed) >= 1, "Expected at least one state observation"
        for obs in r.states_observed:
            assert obs.state_name in ['tutorial', 'pit', 'boss'], f"Unknown state: {obs.state_name}"

    print("\nchunk_processor.py PASSED ✓")

asyncio.run(run())
