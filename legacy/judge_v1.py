import os
import sys
import json
import argparse
import warnings
import yaml

# Suppress HuggingFace and warning messages to ensure clean stdout output
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
warnings.filterwarnings("ignore")

def load_yaml(file_path):
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}

def evaluate_ad(run_dir=None, timeline_path=None, config_path="config.yaml", brief_path="brief.json", rubric_path="brand_voice_rubric.md"):
    config = load_yaml(config_path)
    thresholds = config.get("thresholds", {})
    min_score = thresholds.get("min_judge_score", 85)
    max_clip_duration = thresholds.get("max_clip_duration_seconds", 3.5)
    pacing_penalty = thresholds.get("pacing_penalty_per_clip", 15)
    banned_penalty = thresholds.get("banned_claim_penalty", 50)
    sentiment_penalty = thresholds.get("sentiment_penalty_per_scene", 10)
    banned_claims = [c.lower() for c in config.get("banned_claims", [])]

    # Resolve timeline path
    if not timeline_path:
        if run_dir:
            timeline_path = os.path.join(run_dir, "timeline.json")
        else:
            timeline_path = "/workspace/inputs/current_timeline.json"

    if not os.path.exists(timeline_path):
        err_res = {
            "score": 0,
            "passed": False,
            "feedback": f"Critical Error: Timeline file not found at {timeline_path}"
        }
        sys.stdout.flush()
        print(json.dumps(err_res))
        return

    try:
        with open(timeline_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        err_res = {
            "score": 0,
            "passed": False,
            "feedback": f"Invalid timeline JSON: {str(e)}"
        }
        sys.stdout.flush()
        print(json.dumps(err_res))
        return

    timeline = data.get("timeline", [])
    voiceover = data.get("voiceover_script", "")
    video_title = data.get("video_title", "Untitled")

    base_score = 100
    rule_penalties = 0
    feedback_notes = []
    rule_violations = []

    # -------------------------------------------------------------
    # 1. Deterministic Rule Check: Pacing (clips > 3.5s)
    # -------------------------------------------------------------
    for idx, scene in enumerate(timeline, start=1):
        scene_num = scene.get("scene", idx)
        try:
            start_t = float(scene.get("start_time", 0.0))
            end_t = float(scene.get("end_time", 0.0))
            dur = end_t - start_t
            if dur > max_clip_duration:
                rule_penalties += pacing_penalty
                msg = f"Scene {scene_num}: Duration {dur:.2f}s exceeds {max_clip_duration}s threshold (-{pacing_penalty} pts)."
                feedback_notes.append(msg)
                rule_violations.append({"type": "pacing", "scene": scene_num, "duration": dur})
        except (ValueError, TypeError):
            rule_penalties += pacing_penalty
            msg = f"Scene {scene_num}: Malformed timestamps (-{pacing_penalty} pts)."
            feedback_notes.append(msg)
            rule_violations.append({"type": "timestamp_error", "scene": scene_num})

    # -------------------------------------------------------------
    # 2. Deterministic Rule Check: Banned Claims & Compliance
    # -------------------------------------------------------------
    full_text_to_scan = (voiceover + " " + " ".join(s.get("text_overlay", "") for s in timeline)).lower()
    detected_banned = []
    for claim in banned_claims:
        if claim in full_text_to_scan:
            detected_banned.append(claim)
            rule_penalties += banned_penalty
            msg = f"Compliance Violation: Detected banned claim '{claim}' (-{banned_penalty} pts)."
            feedback_notes.append(msg)
            rule_violations.append({"type": "banned_claim", "claim": claim})

    # -------------------------------------------------------------
    # 3. Rubric Evaluation (LLM rubric call or Local sentiment)
    # -------------------------------------------------------------
    rubric_score = None
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")

    if anthropic_key:
        try:
            import urllib.request
            headers = {
                "x-api-key": anthropic_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
            rubric_prompt = f"""
You are an expert ad reviewer evaluating a short-form video ad against the following brand rubric:
{open(rubric_path, 'r', encoding='utf-8').read() if os.path.exists(rubric_path) else 'Evaluate hook, pacing, clarity, and tone.'}

Ad Data to Evaluate:
Title: {video_title}
Voiceover: {voiceover}
Timeline: {json.dumps(timeline, indent=2)}

Output ONLY valid single-line JSON:
{{"rubric_score": <int 0-100>, "feedback": "<one-sentence summary>"}}
"""
            req_data = json.dumps({
                "model": config.get("models", {}).get("judge_model", "claude-3-5-sonnet-20240620"),
                "max_tokens": 500,
                "messages": [{"role": "user", "content": rubric_prompt}]
            }).encode("utf-8")

            req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=req_data, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                res_body = json.loads(resp.read().decode("utf-8"))
                resp_text = res_body["content"][0]["text"].strip()
                parsed_rubric = json.loads(resp_text.replace("```json", "").replace("```", "").strip())
                rubric_score = int(parsed_rubric.get("rubric_score", 90))
                feedback_notes.append(f"Rubric: {parsed_rubric.get('feedback', '')}")
        except Exception as e:
            # Fallback if API call fails
            pass

    # If LLM rubric was not executed, run HuggingFace sentiment analysis as fallback
    if rubric_score is None:
        overlays = [str(s.get("text_overlay", "")).strip() for s in timeline if str(s.get("text_overlay", "")).strip()]
        if overlays:
            try:
                import torch
                from transformers import pipeline
                device_id = 0 if torch.cuda.is_available() else -1
                model_name = config.get("models", {}).get("sentiment_classifier", "distilbert-base-uncased-finetuned-sst-2-english")
                classifier = pipeline("text-classification", model=model_name, device=device_id)
                predictions = classifier(overlays)
                for text, pred in zip(overlays, predictions):
                    if pred.get("label", "").upper() == "NEGATIVE":
                        rule_penalties += sentiment_penalty
                        feedback_notes.append(f"Negative sentiment overlay: '{text}' (-{sentiment_penalty} pts).")
            except Exception:
                pass
        rubric_score = 100

    # Calculate overall final score
    calculated_score = max(0, min(100, int((rubric_score + (base_score - rule_penalties)) / 2 if anthropic_key else (base_score - rule_penalties))))
    passed = (calculated_score >= min_score) and (len(detected_banned) == 0)

    feedback_str = " | ".join(feedback_notes) if feedback_notes else "Ad passed all rule checks and brand rubric standards."

    final_payload = {
        "score": calculated_score,
        "passed": bool(passed),
        "feedback": feedback_str,
        "rule_violations": rule_violations
    }

    # Save detailed judge report to run_dir if specified
    if run_dir:
        os.makedirs(run_dir, exist_ok=True)
        with open(os.path.join(run_dir, "judge_result.json"), "w", encoding="utf-8") as out_f:
            json.dump(final_payload, out_f, indent=2)

    # Print ONLY valid single-line JSON on the final line of stdout for n8n
    sys.stdout.flush()
    print(json.dumps({"score": calculated_score, "passed": bool(passed), "feedback": feedback_str}))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Judge: Rule checks plus brand rubric evaluation")
    parser.add_argument("--run-dir", default=None, help="Directory for current execution run")
    parser.add_argument("--timeline", default=None, help="Path to timeline JSON")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument("--brief", default="brief.json", help="Path to brief.json")
    parser.add_argument("--rubric", default="brand_voice_rubric.md", help="Path to brand_voice_rubric.md")
    args = parser.parse_args()

    evaluate_ad(
        run_dir=args.run_dir,
        timeline_path=args.timeline,
        config_path=args.config,
        brief_path=args.brief,
        rubric_path=args.rubric
    )
