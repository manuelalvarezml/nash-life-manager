from __future__ import annotations

from datetime import datetime
from typing import Any

from backend.db.schema import (
    get_body_measurement_snapshots,
    get_exercise_logs,
    get_exercise_profile,
    get_latest_body_measurement_snapshot,
    get_nutrition_daily_totals,
    get_nutrition_profile,
    get_personal_records,
    get_workout_adherence_summary,
    get_workout_sessions,
    list_exercise_equipment,
)

MEASUREMENT_PROTOCOL = {
    "recommended": True,
    "why": [
        "Si: te conviene tomar medidas. Para ganar musculo, el peso solo no basta.",
        "Lo mas util para Nash es combinar peso, fuerza, cintura y perimetros repetibles.",
        "Lo importante no es un numero aislado, sino mediciones consistentes en el tiempo.",
    ],
    "timing": {
        "baseline": "Haz una linea base hoy o esta semana.",
        "frequency": "Repite cada 2-4 semanas; el peso corporal puedes registrarlo mas seguido.",
        "best_moment": "Manana, despues de ir al bano, antes de comer, antes de entrenar.",
    },
    "rules": [
        "Usa una cinta no elastica y la misma balanza siempre que puedas.",
        "Toma 2 mediciones de cada sitio. Si difieren por mas de 1 cm, toma una tercera y promedia las 2 mas cercanas.",
        "Mantiene la misma postura, el mismo lado del cuerpo y la misma tension de la cinta cada vez.",
        "No persigas precision falsa: mejor 6 medidas repetibles que 15 medidas mal hechas.",
    ],
    "sites": [
        {
            "code": "weight_kg",
            "label": "Peso",
            "how": "Balanza en superficie dura, poca ropa, mismo horario.",
            "source_note": "NHANES/PhenX weight protocol is the best-practice reference for measured weight.",
        },
        {
            "code": "height_cm",
            "label": "Altura",
            "how": "Talones juntos, pies levemente abiertos, cabeza mirando al frente, espalda larga, mide en cm.",
            "source_note": "NHANES/PhenX standing-height protocol is the best-practice reference for baseline height.",
        },
        {
            "code": "waist_cm",
            "label": "Cintura",
            "how": "Cinta horizontal justo sobre el borde superior de la cresta iliaca, al final de una exhalacion normal.",
            "source_note": "PhenX/NHANES selects the iliac-crest protocol as best practice and recommends documenting the exact protocol used.",
        },
        {
            "code": "hip_cm",
            "label": "Cadera",
            "how": "Cinta horizontal en la maxima extension de los gluteos.",
            "source_note": "PhenX/NHANES hip-circumference best-practice protocol.",
        },
        {
            "code": "arm_relaxed_cm",
            "label": "Brazo relajado",
            "how": "Mide el brazo derecho en el punto medio entre el acromion y el olecranon, con el brazo relajado.",
            "source_note": "PhenX/NHANES mid-upper-arm protocol provides the most standardized arm site.",
        },
        {
            "code": "arm_flexed_cm",
            "label": "Brazo flexionado",
            "how": "Opcional. Usa siempre el mismo lado y el punto de mayor contraccion del biceps.",
            "source_note": "Practical hypertrophy tracking site; less standardized than relaxed mid-arm, so consistency matters more.",
        },
        {
            "code": "chest_cm",
            "label": "Pecho",
            "how": "Opcional. Usa una linea horizontal constante a nivel del pecho y la misma respiracion cada vez.",
            "source_note": "Useful for serial tracking, but less standardized in self-measurement than waist/arm.",
        },
        {
            "code": "thigh_cm",
            "label": "Muslo",
            "how": "Usa siempre el mismo lado y el mismo punto medio del muslo o un punto marcado; no cambies de sitio entre mediciones.",
            "source_note": "Thigh circumference is used to track muscular change, but repeatability depends on consistent landmarks.",
        },
        {
            "code": "calf_cm",
            "label": "Pantorrilla",
            "how": "Mide en la parte mas ancha de la pantorrilla, con el peso repartido de forma similar cada vez.",
            "source_note": "Useful low-cost adjunct for serial muscle-size tracking.",
        },
    ],
}


EXERCISE_LIBRARY: dict[str, dict[str, Any]] = {
    "split_squat": {
        "name": "Sentadilla dividida",
        "movement_pattern": "knee_dominant",
        "exercise_type": "compound",
        "requirements": [["bodyweight"]],
        "equipment_context": "peso corporal",
        "coaching": "Torso ligeramente inclinado, rodilla estable, baja con control.",
    },
    "goblet_squat": {
        "name": "Goblet squat",
        "movement_pattern": "knee_dominant",
        "exercise_type": "compound",
        "requirements": [["dumbbells"], ["kettlebell"]],
        "equipment_context": "mancuerna o kettlebell",
        "coaching": "Busca rango completo sin perder control lumbar.",
    },
    "leg_press": {
        "name": "Leg press",
        "movement_pattern": "knee_dominant",
        "exercise_type": "compound",
        "requirements": [["machine_lower"]],
        "equipment_context": "maquina de piernas",
        "coaching": "Controla la bajada y evita despegar la cadera.",
    },
    "smith_squat": {
        "name": "Smith squat",
        "movement_pattern": "knee_dominant",
        "exercise_type": "compound",
        "requirements": [["smith"]],
        "equipment_context": "smith machine",
        "coaching": "Mantiene la trayectoria consistente y profundidad util.",
    },
    "barbell_squat": {
        "name": "Back squat",
        "movement_pattern": "knee_dominant",
        "exercise_type": "compound",
        "requirements": [["barbell", "rack"]],
        "equipment_context": "barra y rack",
        "coaching": "Solo si la tecnica te resulta segura hoy.",
    },
    "romanian_deadlift_db": {
        "name": "Romanian deadlift con mancuernas",
        "movement_pattern": "hip_hinge",
        "exercise_type": "compound",
        "requirements": [["dumbbells"]],
        "equipment_context": "mancuernas",
        "coaching": "Cadera atras, espalda neutra, estira femorales sin rebotar.",
    },
    "romanian_deadlift_barbell": {
        "name": "Romanian deadlift con barra",
        "movement_pattern": "hip_hinge",
        "exercise_type": "compound",
        "requirements": [["barbell"]],
        "equipment_context": "barra",
        "coaching": "Controla la eccentrica; no hace falta tocar el piso.",
    },
    "hip_hinge_band": {
        "name": "Pull-through o bisagra con banda",
        "movement_pattern": "hip_hinge",
        "exercise_type": "compound",
        "requirements": [["bands"]],
        "equipment_context": "bandas",
        "coaching": "Empuja la cadera atras y termina apretando gluteos.",
    },
    "glute_bridge": {
        "name": "Glute bridge",
        "movement_pattern": "hip_hinge",
        "exercise_type": "compound",
        "requirements": [["bodyweight"]],
        "equipment_context": "peso corporal",
        "coaching": "Pausa arriba 1 segundo y evita arquear de mas.",
    },
    "pushup": {
        "name": "Push-up",
        "movement_pattern": "horizontal_push",
        "exercise_type": "compound",
        "requirements": [["bodyweight"]],
        "equipment_context": "peso corporal",
        "coaching": "Ajusta elevando manos si aun no salen limpias en el piso.",
    },
    "db_floor_press": {
        "name": "Floor press con mancuernas",
        "movement_pattern": "horizontal_push",
        "exercise_type": "compound",
        "requirements": [["dumbbells"]],
        "equipment_context": "mancuernas",
        "coaching": "Buen reemplazo casero del press de pecho.",
    },
    "db_bench_press": {
        "name": "Press plano con mancuernas",
        "movement_pattern": "horizontal_push",
        "exercise_type": "compound",
        "requirements": [["dumbbells", "bench"]],
        "equipment_context": "mancuernas y banca",
        "coaching": "Controla la bajada y no rebotes.",
    },
    "barbell_bench_press": {
        "name": "Press de banca",
        "movement_pattern": "horizontal_push",
        "exercise_type": "compound",
        "requirements": [["barbell", "bench"]],
        "equipment_context": "barra y banca",
        "coaching": "Deja 1-3 RIR; no hace falta llegar a fallo para progresar.",
    },
    "machine_chest_press": {
        "name": "Chest press en maquina",
        "movement_pattern": "horizontal_push",
        "exercise_type": "compound",
        "requirements": [["machine_press"]],
        "equipment_context": "maquina de pecho",
        "coaching": "Buena opcion segura para acercarte mas al fallo.",
    },
    "one_arm_db_row": {
        "name": "Remo a una mano con mancuerna",
        "movement_pattern": "horizontal_pull",
        "exercise_type": "compound",
        "requirements": [["dumbbells"]],
        "equipment_context": "mancuernas",
        "coaching": "Lleva el codo hacia la cadera, sin encoger hombros.",
    },
    "band_row": {
        "name": "Remo con banda",
        "movement_pattern": "horizontal_pull",
        "exercise_type": "compound",
        "requirements": [["bands"]],
        "equipment_context": "bandas",
        "coaching": "Pausa atras para sentir espalda media.",
    },
    "cable_row": {
        "name": "Remo en cable",
        "movement_pattern": "horizontal_pull",
        "exercise_type": "compound",
        "requirements": [["cable"], ["machine_pull"]],
        "equipment_context": "cable o maquina de remo",
        "coaching": "No conviertas la serie en un tiron de espalda baja.",
    },
    "lat_pulldown": {
        "name": "Lat pulldown",
        "movement_pattern": "vertical_pull",
        "exercise_type": "compound",
        "requirements": [["cable"], ["machine_pull"]],
        "equipment_context": "polea",
        "coaching": "Pecho alto, controla la subida.",
    },
    "pullup": {
        "name": "Pull-up o chin-up",
        "movement_pattern": "vertical_pull",
        "exercise_type": "compound",
        "requirements": [["pullup_bar"]],
        "equipment_context": "barra de dominadas",
        "coaching": "Si esta muy duro, usa negativos o asistencia.",
    },
    "db_shoulder_press": {
        "name": "Press militar con mancuernas",
        "movement_pattern": "vertical_push",
        "exercise_type": "compound",
        "requirements": [["dumbbells"]],
        "equipment_context": "mancuernas",
        "coaching": "Gluteos apretados, costillas abajo.",
    },
    "machine_shoulder_press": {
        "name": "Shoulder press en maquina",
        "movement_pattern": "vertical_push",
        "exercise_type": "compound",
        "requirements": [["machine_press"]],
        "equipment_context": "maquina de hombro",
        "coaching": "Buena opcion para trabajo seguro cercano al fallo.",
    },
    "lateral_raise": {
        "name": "Elevaciones laterales",
        "movement_pattern": "lateral_raise",
        "exercise_type": "isolation",
        "requirements": [["dumbbells"], ["bands"]],
        "equipment_context": "mancuernas o bandas",
        "coaching": "Series controladas, sin impulso excesivo.",
    },
    "curl": {
        "name": "Curl de biceps",
        "movement_pattern": "elbow_flexion",
        "exercise_type": "isolation",
        "requirements": [["dumbbells"], ["barbell"], ["bands"]],
        "equipment_context": "mancuernas, barra o bandas",
        "coaching": "Ideal para acercarte a 0-1 RIR en la ultima serie.",
    },
    "triceps_pressdown": {
        "name": "Triceps pressdown",
        "movement_pattern": "elbow_extension",
        "exercise_type": "isolation",
        "requirements": [["cable"], ["bands"]],
        "equipment_context": "polea o banda",
        "coaching": "Extiende completo y controla el retorno.",
    },
    "hamstring_curl": {
        "name": "Leg curl",
        "movement_pattern": "knee_flexion",
        "exercise_type": "isolation",
        "requirements": [["machine_lower"]],
        "equipment_context": "maquina femoral",
        "coaching": "Muy buena para llevar cerca del fallo con bajo riesgo.",
    },
    "leg_extension": {
        "name": "Leg extension",
        "movement_pattern": "knee_extension",
        "exercise_type": "isolation",
        "requirements": [["machine_lower"]],
        "equipment_context": "maquina de cuadriceps",
        "coaching": "Pausa arriba y controla la bajada.",
    },
    "calf_raise": {
        "name": "Calf raise",
        "movement_pattern": "calves",
        "exercise_type": "isolation",
        "requirements": [["bodyweight"], ["dumbbells"]],
        "equipment_context": "peso corporal o mancuernas",
        "coaching": "Pausa abajo y arriba para que cuente.",
    },
    "dead_bug": {
        "name": "Dead bug",
        "movement_pattern": "core",
        "exercise_type": "accessory",
        "requirements": [["bodyweight"]],
        "equipment_context": "peso corporal",
        "coaching": "Exhala al extender para fijar tronco.",
    },
    "plank": {
        "name": "Plank",
        "movement_pattern": "core",
        "exercise_type": "accessory",
        "requirements": [["bodyweight"]],
        "equipment_context": "peso corporal",
        "coaching": "Mantiene pelvis neutra y tension total.",
    },
    "thoracic_mobility": {
        "name": "Movilidad toracica",
        "movement_pattern": "mobility",
        "exercise_type": "mobility",
        "requirements": [["bodyweight"]],
        "equipment_context": "peso corporal",
        "coaching": "8-10 repeticiones lentas por lado.",
    },
    "hip_flexor_stretch": {
        "name": "Estiramiento de flexor de cadera",
        "movement_pattern": "mobility",
        "exercise_type": "mobility",
        "requirements": [["bodyweight"]],
        "equipment_context": "peso corporal",
        "coaching": "30-45 segundos por lado.",
    },
}


PLAN_STRUCTURES: dict[str, dict[str, Any]] = {
    "minimum_home": {
        "name": "Minimo casa",
        "level": "minimum",
        "location": "home",
        "focus_code": "minimum_home",
        "goal": "Cumplir el minimo util sin negociar demasiado contigo mismo.",
        "estimated_duration_min": 12,
        "warmup": [
            "1 minuto de caminar o marchar",
            "6 respiraciones profundas",
            "1 ronda corta de movilidad toracica y cadera",
        ],
        "slots": [
            {"slot": "knee_dominant", "candidates": ["goblet_squat", "split_squat"], "sets": 2, "rep_range": "8-15", "rest_sec": 75},
            {"slot": "horizontal_push", "candidates": ["db_floor_press", "pushup"], "sets": 2, "rep_range": "8-15", "rest_sec": 75},
            {"slot": "horizontal_pull", "candidates": ["one_arm_db_row", "band_row", "pullup"], "sets": 2, "rep_range": "8-15", "rest_sec": 75},
            {"slot": "hip_hinge", "candidates": ["romanian_deadlift_db", "hip_hinge_band", "glute_bridge"], "sets": 1, "rep_range": "10-15", "rest_sec": 60},
            {"slot": "core", "candidates": ["dead_bug", "plank"], "sets": 1, "rep_range": "30-45 s", "rest_sec": 30},
        ],
        "guidance": [
            "Si haces esto, el dia ya cuenta.",
            "Ultima serie cerca de 1-2 RIR en movimientos seguros; no necesitas fallo tecnico en todo.",
        ],
    },
    "minimum_gym": {
        "name": "Minimo gym",
        "level": "minimum",
        "location": "gym",
        "focus_code": "minimum_gym",
        "goal": "Entrar, mover peso util, salir sin hacer del gimnasio una pelea mental.",
        "estimated_duration_min": 15,
        "warmup": [
            "3-4 minutos de caminata o bicicleta suave",
            "1 serie ligera del primer ejercicio",
        ],
        "slots": [
            {"slot": "knee_dominant", "candidates": ["leg_press", "smith_squat", "goblet_squat"], "sets": 2, "rep_range": "8-12", "rest_sec": 90},
            {"slot": "horizontal_push", "candidates": ["machine_chest_press", "db_bench_press", "pushup"], "sets": 2, "rep_range": "8-12", "rest_sec": 90},
            {"slot": "horizontal_pull", "candidates": ["cable_row", "one_arm_db_row", "band_row"], "sets": 2, "rep_range": "8-12", "rest_sec": 90},
            {"slot": "mobility", "candidates": ["thoracic_mobility", "hip_flexor_stretch"], "sets": 1, "rep_range": "8-10", "rest_sec": 30},
        ],
        "guidance": [
            "El objetivo minimo del gym es sostener el habito, no batir records hoy.",
        ],
    },
    "optimal_home_a": {
        "name": "Optimo casa A",
        "level": "optimal",
        "location": "home",
        "focus_code": "A",
        "goal": "Full body orientado a hipertrofia con material casero.",
        "estimated_duration_min": 40,
        "warmup": [
            "3 minutos de movilidad y activacion",
            "1 serie de aproximacion ligera en los dos primeros ejercicios",
        ],
        "slots": [
            {"slot": "knee_dominant", "candidates": ["goblet_squat", "split_squat"], "sets": 3, "rep_range": "6-12", "rest_sec": 120},
            {"slot": "horizontal_push", "candidates": ["db_floor_press", "pushup", "db_bench_press"], "sets": 3, "rep_range": "6-12", "rest_sec": 120},
            {"slot": "horizontal_pull", "candidates": ["one_arm_db_row", "band_row", "pullup"], "sets": 3, "rep_range": "8-12", "rest_sec": 90},
            {"slot": "hip_hinge", "candidates": ["romanian_deadlift_db", "hip_hinge_band", "glute_bridge"], "sets": 2, "rep_range": "8-12", "rest_sec": 120},
            {"slot": "lateral_raise", "candidates": ["lateral_raise"], "sets": 2, "rep_range": "12-20", "rest_sec": 60},
            {"slot": "core", "candidates": ["dead_bug", "plank"], "sets": 2, "rep_range": "30-45 s", "rest_sec": 30},
        ],
        "guidance": [
            "Busca 1-3 RIR en compuestos y 0-2 RIR en accesorios si la tecnica sigue limpia.",
        ],
    },
    "optimal_home_b": {
        "name": "Optimo casa B",
        "level": "optimal",
        "location": "home",
        "focus_code": "B",
        "goal": "Segundo full body para alternar estimulo y aburrirte menos.",
        "estimated_duration_min": 40,
        "warmup": [
            "3 minutos de movilidad de cadera, hombro y torax",
            "1 serie ligera en el primer push y primer pull",
        ],
        "slots": [
            {"slot": "hip_hinge", "candidates": ["romanian_deadlift_db", "glute_bridge", "hip_hinge_band"], "sets": 3, "rep_range": "6-12", "rest_sec": 120},
            {"slot": "vertical_push", "candidates": ["db_shoulder_press", "pushup"], "sets": 3, "rep_range": "6-12", "rest_sec": 90},
            {"slot": "vertical_pull", "candidates": ["pullup", "band_row", "one_arm_db_row"], "sets": 3, "rep_range": "6-12", "rest_sec": 90},
            {"slot": "knee_dominant", "candidates": ["split_squat", "goblet_squat"], "sets": 2, "rep_range": "8-15", "rest_sec": 90},
            {"slot": "arm_iso", "candidates": ["curl", "triceps_pressdown"], "sets": 2, "rep_range": "10-20", "rest_sec": 60},
            {"slot": "calves", "candidates": ["calf_raise"], "sets": 2, "rep_range": "12-20", "rest_sec": 45},
        ],
        "guidance": [
            "Si hoy tienes mas energia, suma una serie al ejercicio que mas disfrutes.",
        ],
    },
    "optimal_gym_a": {
        "name": "Optimo gym A",
        "level": "optimal",
        "location": "gym",
        "focus_code": "A",
        "goal": "Full body A para construir masa muscular con base sostenible.",
        "estimated_duration_min": 50,
        "warmup": [
            "4-5 minutos de cardio suave",
            "2 series de aproximacion en el primer ejercicio grande",
        ],
        "slots": [
            {"slot": "knee_dominant", "candidates": ["leg_press", "barbell_squat", "smith_squat", "goblet_squat"], "sets": 3, "rep_range": "6-10", "rest_sec": 150},
            {"slot": "horizontal_push", "candidates": ["machine_chest_press", "barbell_bench_press", "db_bench_press"], "sets": 3, "rep_range": "6-10", "rest_sec": 150},
            {"slot": "horizontal_pull", "candidates": ["cable_row", "one_arm_db_row"], "sets": 3, "rep_range": "8-12", "rest_sec": 120},
            {"slot": "posterior_chain", "candidates": ["hamstring_curl", "romanian_deadlift_barbell", "romanian_deadlift_db"], "sets": 2, "rep_range": "8-12", "rest_sec": 120},
            {"slot": "lateral_raise", "candidates": ["lateral_raise"], "sets": 2, "rep_range": "12-20", "rest_sec": 60},
            {"slot": "arm_iso", "candidates": ["curl", "triceps_pressdown"], "sets": 2, "rep_range": "10-15", "rest_sec": 60},
        ],
        "guidance": [
            "No necesitas ir a fallo en sentadilla o press pesado; deja 1-3 RIR y guarda el fallo para maquinas o aislados si quieres.",
        ],
    },
    "optimal_gym_b": {
        "name": "Optimo gym B",
        "level": "optimal",
        "location": "gym",
        "focus_code": "B",
        "goal": "Full body B para repartir el volumen semanal sin hacer la rutina tediosa.",
        "estimated_duration_min": 50,
        "warmup": [
            "4-5 minutos de cardio suave",
            "1-2 series de aproximacion antes del primer tiron y primer press",
        ],
        "slots": [
            {"slot": "hip_hinge", "candidates": ["romanian_deadlift_barbell", "romanian_deadlift_db", "hamstring_curl"], "sets": 3, "rep_range": "6-10", "rest_sec": 150},
            {"slot": "vertical_pull", "candidates": ["lat_pulldown", "pullup"], "sets": 3, "rep_range": "8-12", "rest_sec": 120},
            {"slot": "vertical_push", "candidates": ["machine_shoulder_press", "db_shoulder_press"], "sets": 3, "rep_range": "8-12", "rest_sec": 120},
            {"slot": "single_leg", "candidates": ["split_squat", "leg_extension", "goblet_squat"], "sets": 2, "rep_range": "10-15", "rest_sec": 90},
            {"slot": "chest_support", "candidates": ["machine_chest_press", "pushup"], "sets": 2, "rep_range": "8-12", "rest_sec": 90},
            {"slot": "calves", "candidates": ["calf_raise"], "sets": 2, "rep_range": "12-20", "rest_sec": 45},
        ],
        "guidance": [
            "La rutina B te da variedad sin romper la progresion.",
        ],
    },
}


def _normalize_token(value: str) -> str:
    return (
        value.strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
        .replace("/", "_")
    )


def _add_inferred_categories(bucket: set[str], raw_value: str) -> None:
    value = _normalize_token(raw_value)
    if not value:
        return
    if any(token in value for token in ["mancuer", "dumbbell"]):
        bucket.add("dumbbells")
    if any(token in value for token in ["banda", "band"]):
        bucket.add("bands")
    if any(token in value for token in ["barra", "barbell"]):
        bucket.add("barbell")
    if any(token in value for token in ["rack", "jaula", "power_cage"]):
        bucket.add("rack")
    if any(token in value for token in ["bench", "banca", "banco"]):
        bucket.add("bench")
    if any(token in value for token in ["smith"]):
        bucket.add("smith")
    if any(token in value for token in ["polea", "cable"]):
        bucket.add("cable")
    if any(token in value for token in ["dominada", "pullup", "pull_up"]):
        bucket.add("pullup_bar")
    if any(token in value for token in ["kettlebell", "pesa_rusa"]):
        bucket.add("kettlebell")
    if any(token in value for token in ["press_machine", "maquina_pecho", "chest_press"]):
        bucket.add("machine_press")
    if any(token in value for token in ["pulldown", "remo_maquina", "maquina_espalda", "machine_pull"]):
        bucket.add("machine_pull")
    if any(token in value for token in ["leg_press", "extension", "curl_femoral", "prensa", "maquina_pierna", "machine_lower"]):
        bucket.add("machine_lower")


def _collect_available_categories(profile: dict | None, location: str) -> set[str]:
    categories = {"bodyweight"}
    profile = profile or {}
    raw_equipment = profile.get("equipment") or []
    for value in raw_equipment:
        if isinstance(value, str):
            _add_inferred_categories(categories, value)

    for item in list_exercise_equipment(location=location):
        _add_inferred_categories(categories, item.get("category") or "")
        _add_inferred_categories(categories, item.get("label") or "")

    return categories


def _preference_score(exercise: dict[str, Any], preferences: list[str] | None) -> int:
    if not preferences:
        return 0

    text = " ".join(str(item).lower() for item in preferences)
    movement = exercise.get("movement_pattern") or ""
    equipment = str(exercise.get("equipment_context") or "").lower()
    name = str(exercise.get("name") or "").lower()
    score = 0

    if any(token in text for token in ["espalda", "remo", "dominada", "pull"]):
        if movement in {"horizontal_pull", "vertical_pull"}:
            score += 3
    if any(token in text for token in ["pecho", "press", "empuje"]):
        if movement in {"horizontal_push", "vertical_push"}:
            score += 3
    if any(token in text for token in ["pierna", "gluteo", "sentadilla", "cuadricep", "femoral"]):
        if movement in {"knee_dominant", "hip_hinge", "knee_extension", "knee_flexion"}:
            score += 3
    if any(token in text for token in ["brazo", "biceps", "triceps"]):
        if movement in {"elbow_flexion", "elbow_extension"}:
            score += 2
    if any(token in text for token in ["hombro", "laterales"]):
        if movement in {"vertical_push", "lateral_raise"}:
            score += 2
    if any(token in text for token in ["mancuerna", "dumbbell"]) and "mancuern" in equipment:
        score += 2
    if any(token in text for token in ["maquina", "machine"]) and "maquina" in equipment:
        score += 2
    if any(token in text for token in ["casa", "simple", "rapido", "corto", "cortas"]):
        if "peso corporal" in equipment or "mancuernas" in equipment:
            score += 1
    if any(token in name for token in ["press", "row", "remo", "curl"]):
        score += 1
    return score


def _movement_history_map(limit: int = 160) -> dict[str, dict[str, Any]]:
    history: dict[str, dict[str, Any]] = {}
    for log in get_exercise_logs(limit=limit):
        name = log.get("exercise_name")
        if not name or name in history:
            continue
        sets = log.get("sets") or []
        best_set = None
        for raw_set in sets:
            if not isinstance(raw_set, dict):
                continue
            reps = raw_set.get("reps") or 0
            weight_kg = raw_set.get("weight_kg") or 0
            if best_set is None or weight_kg > best_set["weight_kg"] or (
                weight_kg == best_set["weight_kg"] and reps > best_set["reps"]
            ):
                best_set = {
                    "reps": reps,
                    "weight_kg": weight_kg,
                    "rir": raw_set.get("rir"),
                    "reached_failure": raw_set.get("reached_failure"),
                }
        history[name] = {
            "date": log.get("date"),
            "level": log.get("level"),
            "location": log.get("actual_location") or log.get("location"),
            "best_set": best_set,
        }
    return history


def _requirement_matches(requirement: list[str], available: set[str]) -> bool:
    return all(token in available for token in requirement)


def _pick_exercise(
    candidates: list[str],
    available: set[str],
    preferences: list[str] | None = None,
) -> dict[str, Any]:
    ranked_candidates = sorted(
        candidates,
        key=lambda key: _preference_score(EXERCISE_LIBRARY.get(key, {}), preferences),
        reverse=True,
    )
    for key in ranked_candidates:
        exercise = EXERCISE_LIBRARY.get(key)
        if not exercise:
            continue
        requirements = exercise.get("requirements") or [["bodyweight"]]
        if any(_requirement_matches(option, available) for option in requirements):
            return exercise
    return EXERCISE_LIBRARY["pushup"]


def _rir_target(exercise_type: str, level: str) -> str:
    if level == "minimum":
        return "1-3 RIR"
    if exercise_type == "compound":
        return "1-3 RIR"
    if exercise_type == "mobility":
        return "tecnica limpia"
    return "0-2 RIR"


def _failure_guidance(exercise_type: str) -> str:
    if exercise_type == "compound":
        return "No hace falta fallo. Prioriza tecnica y deja 1-3 reps en reserva."
    if exercise_type == "mobility":
        return "Sin fallo; busca rango y control."
    return "Puedes acercarte mucho al fallo en la ultima serie si la tecnica sigue limpia."


def _progression_tip(exercise: dict[str, Any], slot: dict[str, Any], history: dict[str, dict[str, Any]]) -> str:
    last = history.get(exercise["name"])
    if not last or not last.get("best_set"):
        return "Empieza con una carga que te deje dentro del rango y con 2-3 reps en reserva."

    best = last["best_set"]
    reps = int(best.get("reps") or 0)
    weight_kg = float(best.get("weight_kg") or 0)
    rir = best.get("rir")
    rep_range = slot.get("rep_range", "")
    low = high = None
    if "-" in rep_range:
        try:
            low, high = [int(part.strip()) for part in rep_range.split("-", 1)]
        except ValueError:
            low = high = None

    if weight_kg <= 0:
        return "Intenta sumar 1-2 reps o volver la variante un poco mas dificil sin perder tecnica."
    if high is not None and reps >= high and (rir is None or int(rir) >= 1):
        return f"Tu ultima referencia fue {weight_kg:g} kg x {reps}. Si hoy se siente igual o mejor, sube un paso pequeno."
    if low is not None and reps < low:
        return f"Tu ultima referencia fue {weight_kg:g} kg x {reps}. Mantiene o baja un poco la carga hasta entrar limpio al rango."
    return f"Tu ultima referencia fue {weight_kg:g} kg x {reps}. Intenta ganar 1 rep o mejorar control antes de subir peso."


def _render_plan(
    plan_key: str,
    available: set[str],
    history: dict[str, dict[str, Any]],
    energy_level: int,
    preferences: list[str] | None = None,
) -> dict[str, Any]:
    structure = PLAN_STRUCTURES[plan_key]
    exercises = []
    extra_energy = energy_level >= 8 and structure["level"] == "optimal"

    for slot in structure["slots"]:
        exercise = _pick_exercise(slot["candidates"], available, preferences)
        entry = {
            "name": exercise["name"],
            "movement_pattern": exercise["movement_pattern"],
            "equipment_context": exercise["equipment_context"],
            "exercise_type": exercise["exercise_type"],
            "sets": slot["sets"] + (1 if extra_energy and exercise["exercise_type"] == "isolation" else 0),
            "rep_range": slot["rep_range"],
            "rest_sec": slot["rest_sec"],
            "rir_target": _rir_target(exercise["exercise_type"], structure["level"]),
            "failure_guidance": _failure_guidance(exercise["exercise_type"]),
            "coaching": exercise["coaching"],
            "progression_tip": _progression_tip(exercise, slot, history),
            "last_performance": history.get(exercise["name"]),
        }
        exercises.append(entry)

    return {
        "name": structure["name"],
        "level": structure["level"],
        "location": structure["location"],
        "focus_code": structure["focus_code"],
        "goal": structure["goal"],
        "estimated_duration_min": structure["estimated_duration_min"] + (5 if extra_energy else 0),
        "warmup": structure["warmup"],
        "guidance": structure["guidance"],
        "exercises": exercises,
        "extra_energy_enabled": extra_energy,
    }


def _choose_primary_mode(desired_mode: str | None, energy_level: int, available_time_min: int, minimum_minutes: int, optimal_minutes: int) -> str:
    if desired_mode in {"minimum", "optimal"}:
        return desired_mode
    if available_time_min <= minimum_minutes + 5:
        return "minimum"
    if energy_level <= 4:
        return "minimum"
    if available_time_min >= max(optimal_minutes - 10, 30) and energy_level >= 5:
        return "optimal"
    return "minimum"


def _next_focus_code(sessions: list[dict]) -> str:
    for session in sessions:
        if session.get("completed") != 1:
            continue
        focus = session.get("focus_code")
        if focus == "A":
            return "B"
        if focus == "B":
            return "A"
    return "A"


def _weekly_outline(profile: dict | None, primary_location: str) -> list[dict]:
    profile = profile or {}
    target_days = int(profile.get("workout_days_per_week") or 3)
    schedule_days = profile.get("schedule_days") or []
    if not schedule_days:
        schedule_days = ["lunes", "miercoles", "viernes"][:target_days]

    outline = []
    alternating = ["A", "B"] if target_days > 1 else ["A"]
    for index, day_name in enumerate(schedule_days[:target_days]):
        outline.append(
            {
                "day": day_name,
                "session": "optimal" if index < max(target_days - 1, 1) else "minimum",
                "location": primary_location if index < max(target_days - 1, 1) else "home",
                "focus_code": alternating[index % len(alternating)],
            }
        )
    return outline


def _measurement_change(current: dict | None, previous: dict | None) -> dict[str, Any]:
    if not current or not previous:
        return {}
    tracked_fields = [
        "weight_kg",
        "waist_cm",
        "hip_cm",
        "chest_cm",
        "arm_relaxed_cm",
        "arm_flexed_cm",
        "thigh_cm",
        "calf_cm",
    ]
    changes = {}
    for field in tracked_fields:
        current_value = current.get(field)
        previous_value = previous.get(field)
        if current_value is None or previous_value is None:
            continue
        changes[field] = round(float(current_value) - float(previous_value), 2)
    return changes


def _barrier_notes(profile: dict | None, location: str, minimum_minutes: int) -> list[str]:
    profile = profile or {}
    notes: list[str] = []
    barriers = " ".join(str(item).lower() for item in (profile.get("barriers") or []))

    if any(token in barriers for token in ["pereza", "motivacion", "disciplina", "procrast"]):
        notes.append(
            f"Cuando aparezca resistencia mental, negocia solo {minimum_minutes} minutos y empieza por el calentamiento."
        )
    if any(token in barriers for token in ["tiempo", "trabajo", "tarde", "cansancio"]):
        notes.append(
            "Tu plan minimo existe para dias apretados; proteger una sesion corta cuenta mas que esperar el dia perfecto."
        )
    if location == "gym" and any(
        token in barriers for token in ["ansiedad", "verguenza", "traslado", "gym", "gimnasio"]
    ):
        notes.append(
            "Si el gym se vuelve friccion hoy, cambia sin culpa al rescate en casa para sostener el habito."
        )
    if any(token in barriers for token in ["aburr", "monotonia"]):
        notes.append(
            "Alterna A/B y deja un ejercicio favorito casi al inicio para bajar la friccion de empezar."
        )
    return notes


def generate_workout_plan(
    *,
    location: str | None = None,
    energy_level: int | None = None,
    available_time_min: int | None = None,
    desired_mode: str | None = None,
) -> dict[str, Any]:
    profile = get_exercise_profile() or {}
    nutrition_profile = get_nutrition_profile() or {}
    nutrition_totals = get_nutrition_daily_totals()
    sessions = get_workout_sessions(limit=12)
    history = _movement_history_map()
    energy_level = int(energy_level or 6)
    minimum_minutes = int(profile.get("minimum_session_min") or 12)
    optimal_minutes = int(profile.get("optimal_session_min") or profile.get("time_per_workout_min") or 45)
    available_time_min = int(available_time_min or optimal_minutes)
    enjoyment = profile.get("enjoyment") or []

    preferred_location = location or profile.get("preferred_location") or ("gym" if profile.get("has_gym_access") else "home")
    if preferred_location == "either":
        preferred_location = "gym" if profile.get("has_gym_access") else "home"
    if preferred_location == "gym" and not profile.get("has_gym_access"):
        preferred_location = "home"

    primary_mode = _choose_primary_mode(
        desired_mode,
        energy_level,
        available_time_min,
        minimum_minutes,
        optimal_minutes,
    )
    next_focus = _next_focus_code(sessions)
    primary_location = preferred_location
    available_categories = _collect_available_categories(profile, primary_location)
    fallback_categories = _collect_available_categories(profile, "home")

    if primary_mode == "minimum":
        primary_key = "minimum_gym" if primary_location == "gym" else "minimum_home"
    else:
        primary_key = f"optimal_{primary_location}_{next_focus.lower()}"

    fallback_key = "minimum_home"
    primary_session = _render_plan(
        primary_key,
        available_categories,
        history,
        energy_level,
        enjoyment,
    )
    fallback_session = _render_plan(
        fallback_key,
        fallback_categories,
        history,
        max(energy_level - 1, 4),
        enjoyment,
    )

    protein_target = nutrition_profile.get("protein_target_g") or 0
    protein_today = nutrition_totals.get("protein") or 0
    protein_ratio = round((protein_today / protein_target) * 100) if protein_target else None

    adherence_7 = get_workout_adherence_summary(days=7)
    foundation_mode = adherence_7["total_sessions"] < 3 or profile.get("fitness_level") in (None, "beginner")

    notes = []
    if foundation_mode:
        notes.append("Estas en modo base: lo mas importante es encadenar semanas consistentes antes de subir mucho el volumen.")
    else:
        notes.append("Ya puedes empujar mas el volumen semanal sin perder sostenibilidad.")
    if protein_target and protein_today < protein_target:
        notes.append(f"Proteina hoy: {round(protein_today)}g de {round(protein_target)}g. Entrenar igual sirve, pero intenta cerrar el dia mas cerca de tu meta.")
    if primary_location == "gym":
        notes.append("Si no vas al gym hoy, usa el plan de rescate en casa para que el dia igual cuente.")
    notes.extend(_barrier_notes(profile, primary_location, minimum_minutes))
    if enjoyment:
        notes.append(f"El motor intentara priorizar lo que te engancha mas: {', '.join(str(item) for item in enjoyment[:4])}.")
    if not get_latest_body_measurement_snapshot():
        notes.append("Te conviene tomar una linea base esta semana: peso, cintura, brazo relajado y muslo ya dan una senal util.")

    weekly_sessions_target = int(profile.get("workout_days_per_week") or 3)
    hard_sets_range = "6-8" if foundation_mode else "8-12"

    return {
        "generated_at": datetime.now().isoformat(),
        "input": {
            "location": primary_location,
            "energy_level": energy_level,
            "available_time_min": available_time_min,
            "desired_mode": desired_mode or "auto",
        },
        "training_target": {
            "primary_goal": profile.get("primary_goal") or "muscle_gain",
            "weekly_sessions_target": weekly_sessions_target,
            "minimum_sessions_floor": min(2, weekly_sessions_target) if weekly_sessions_target > 1 else 1,
            "hard_sets_goal_per_muscle": hard_sets_range,
            "phase": "foundation" if foundation_mode else "build",
        },
        "primary_session": primary_session,
        "fallback_session": fallback_session,
        "weekly_outline": _weekly_outline(profile, primary_location),
        "adherence": {
            "last_7_days": adherence_7,
            "last_28_days": get_workout_adherence_summary(days=28),
        },
        "nutrition_bridge": {
            "protein_today_g": round(protein_today, 1),
            "protein_target_g": protein_target,
            "protein_progress_pct": protein_ratio,
        },
        "notes": notes,
    }


def build_exercise_dashboard() -> dict[str, Any]:
    profile = get_exercise_profile()
    equipment = list_exercise_equipment()
    measurements = get_body_measurement_snapshots(limit=8)
    latest_measurement = measurements[0] if measurements else None
    previous_measurement = measurements[1] if len(measurements) > 1 else None
    records = get_personal_records(limit=12)
    sessions = get_workout_sessions(limit=12)

    return {
        "profile": profile,
        "equipment": equipment,
        "measurements": measurements,
        "latest_measurement": latest_measurement or get_latest_body_measurement_snapshot(),
        "measurement_change": _measurement_change(latest_measurement, previous_measurement),
        "records": records,
        "recent_sessions": sessions,
        "adherence_7": get_workout_adherence_summary(days=7),
        "adherence_28": get_workout_adherence_summary(days=28),
        "measurement_protocol": MEASUREMENT_PROTOCOL,
        "today_plan": generate_workout_plan(),
    }
