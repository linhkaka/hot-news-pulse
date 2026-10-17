import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def sample_analysis(spikes: int = 0, drops: int = 0) -> dict:
    return {
        "spike_notes": [f"spike note {i}" for i in range(spikes)],
        "drop_notes": [f"drop note {i}" for i in range(drops)],
        "deconstruction": {
            "packaging_analysis": {"visual_trigger": "vt", "curiosity_gap": "cg", "psychological_angle": "pa"},
            "hook_30s_breakdown": {"opening_mechanism": "om", "pacing_notes": "pn", "core_loop_opened": "cl"},
            "narrative_beats": [
                {"time_range": "00:00 - 00:45", "beat_name": "Hook", "retention_technique": "Paradox", "structural_purpose": "Mở vòng lặp"}
            ],
            "exploitable_gaps": {
                "unanswered_questions": ["Q1"],
                "viewer_complaints_or_debates": "debate",
                "superior_angle_proposal": "Góc mới",
            },
        },
        "blueprint": {
            "packaging_blueprint": {
                "titles": ["T1", "T2", "T3"],
                "thumbnail_concepts": [{"layout_description": "ld", "ai_image_prompt": "prompt --ar 16:9"}],
            },
            "production_script": [
                {
                    "scene_id": 1, "estimated_time": "00:00 - 00:07", "beat_function": "Hook",
                    "voiceover_script": "vo", "visual_direction": "vd",
                    "visual_generation_prompt": "vgp", "audio_sfx_cues": "sfx",
                }
            ],
        },
    }
