import json

new_questions = [
    # Planning Ability
    ("I map out the entire process before starting a complex task.", "planning_ability", "positive"),
    ("I find it difficult to organize tasks logically to achieve a long-term goal.", "planning_ability", "negative"),
    # Responsibility
    ("I take full ownership of the outcomes when I am assigned a task.", "responsibility", "positive"),
    ("I tend to rely on others to ensure my work is completed properly.", "responsibility", "negative"),
    # Courage
    ("I am willing to stand up for my beliefs even when facing strong opposition.", "courage", "positive"),
    ("I avoid confronting people even when they are clearly in the wrong.", "courage", "negative"),
    # Determination
    ("I persist in overcoming obstacles until my objective is achieved.", "determination", "positive"),
    ("I quickly lose motivation when a project becomes unexpectedly difficult.", "determination", "negative"),
    # Social Relations
    ("I actively foster cooperation and harmony among group members.", "social_relations", "positive"),
    ("I find it exhausting to collaborate closely with team members.", "social_relations", "negative"),
    # Practical Ability
    ("I am resourceful at solving hands-on problems with limited tools.", "practical_ability", "positive"),
    ("I struggle to apply theoretical knowledge to real-world situations.", "practical_ability", "negative"),
    # Influencing Ability
    ("I can effectively persuade others to adopt a common objective.", "influencing_ability", "positive"),
    ("I find it challenging to guide a group toward a shared goal.", "influencing_ability", "negative"),
    # General Awareness
    ("I constantly stay informed about the events happening in my surroundings.", "general_awareness", "positive"),
    ("I often overlook important details that others notice easily.", "general_awareness", "negative"),
    # Expression
    ("I articulate my thoughts clearly and confidently to others.", "expression", "positive"),
    ("I struggle to find the right words to communicate my ideas effectively.", "expression", "negative"),
    # Physical Endurance
    ("I maintain my stamina and focus during physically demanding tasks.", "physical_endurance", "positive"),
    ("I quickly tire out when engaging in rigorous or strenuous activities.", "physical_endurance", "negative"),
    # Self-Confidence
    ("I believe in my capabilities to handle whatever challenges come my way.", "self_confidence", "positive"),
    ("I frequently doubt my abilities when taking on new responsibilities.", "self_confidence", "negative"),
]

# Append to questions.txt
with open("d:/OPI/questions.txt", "a") as f:
    for text, _, _ in new_questions:
        f.write(text + "\n")

# Append to questions_meta.json
with open("d:/OPI/questions_meta.json", "r") as f:
    meta = json.load(f)

start_id = max(item["id"] for item in meta) + 1

for text, trait, polarity in new_questions:
    meta.append({
        "id": start_id,
        "text": text,
        "trait": trait,
        "polarity": polarity,
        "confidence": 1.0,
        "phase": 2
    })
    start_id += 1

with open("d:/OPI/questions_meta.json", "w") as f:
    json.dump(meta, f, indent=2)

print(f"Successfully added {len(new_questions)} questions. Total questions: {len(meta)}")
