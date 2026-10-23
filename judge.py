import os
import sys
import json
import warnings

# Suppress HuggingFace / PyTorch verbose logs so stdout remains clean
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
warnings.filterwarnings("ignore")

def evaluate_timeline():
    timeline_path = "/workspace/inputs/current_timeline.json"
    
    if not os.path.exists(timeline_path):
        output = {
            "score": 0,
            "feedback": f"Critical Error: Timeline file not found at {timeline_path}"
        }
        sys.stdout.flush()
        print(json.dumps(output))
        return

    try:
        with open(timeline_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        output = {
            "score": 0,
            "feedback": f"JSON Parsing Error in timeline: {str(e)}"
        }
        sys.stdout.flush()
        print(json.dumps(output))
        return

    timeline = data.get("timeline", [])
    if not timeline:
        output = {
            "score": 0,
            "feedback": "Empty timeline provided."
        }
        sys.stdout.flush()
        print(json.dumps(output))
        return

    base_score = 100
    pacing_penalties = 0
    feedback_notes = []

    # 1. Pacing Evaluation: 15 points penalty for any clip exceeding 3.5 seconds
    for idx, clip in enumerate(timeline, start=1):
        scene_id = clip.get("scene", idx)
        try:
            start_time = float(clip.get("start_time", 0.0))
            end_time = float(clip.get("end_time", 0.0))
            duration = end_time - start_time
            if duration > 3.5:
                pacing_penalties += 15
                feedback_notes.append(
                    f"Scene {scene_id}: Clip duration {duration:.2f}s exceeds 3.5s pacing threshold (-15 pts)."
                )
        except (ValueError, TypeError):
            pacing_penalties += 15
            feedback_notes.append(f"Scene {scene_id}: Invalid timestamp format (-15 pts).")

    # 2. Sentiment Analysis on text_overlay using DistilBERT SST-2
    sentiment_penalties = 0
    overlays_to_analyze = []
    overlay_scenes = []

    for idx, clip in enumerate(timeline, start=1):
        text = str(clip.get("text_overlay", "")).strip()
        if text:
            overlays_to_analyze.append(text)
            overlay_scenes.append(clip.get("scene", idx))

    if overlays_to_analyze:
        try:
            import torch
            from transformers import pipeline

            # Target device=0 (RTX 4090 GPU) as specified, fallback to CPU (-1) if CUDA is unavailable
            device_id = 0 if torch.cuda.is_available() else -1
            try:
                classifier = pipeline(
                    "text-classification",
                    model="distilbert-base-uncased-finetuned-sst-2-english",
                    device=0
                )
            except Exception:
                classifier = pipeline(
                    "text-classification",
                    model="distilbert-base-uncased-finetuned-sst-2-english",
                    device=device_id
                )

            predictions = classifier(overlays_to_analyze)
            for scene_id, text, pred in zip(overlay_scenes, overlays_to_analyze, predictions):
                label = pred.get("label", "").upper()
                score = pred.get("score", 0.0)
                if label == "NEGATIVE":
                    penalty = 10
                    sentiment_penalties += penalty
                    feedback_notes.append(
                        f"Scene {scene_id}: Negative sentiment detected in '{text}' ({score:.2f} conf) (-{penalty} pts)."
                    )
                else:
                    feedback_notes.append(
                        f"Scene {scene_id}: Positive hook sentiment in '{text}'."
                    )
        except Exception as err:
            feedback_notes.append(f"Sentiment analysis note: {str(err)}")

    final_score = max(0, min(100, base_score - pacing_penalties - sentiment_penalties))

    if not feedback_notes:
        feedback_str = "All clips passed pacing and sentiment quality criteria."
    else:
        feedback_str = " | ".join(feedback_notes)

    result = {
        "score": int(final_score),
        "feedback": feedback_str
    }

    # Guarantee: Print ONLY valid single-line JSON on the final line of stdout
    sys.stdout.flush()
    print(json.dumps(result))

if __name__ == "__main__":
    evaluate_timeline()
