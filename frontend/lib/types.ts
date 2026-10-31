// Mirrors backend/core/schema.py. Keep the two in sync.

export type InjuryType = 'knee' | 'shoulder' | 'upper_body' | 'lower_body' | 'general';
export type MobilityLevel = 'limited' | 'moderate' | 'full';
export type Difficulty = 'conservative' | 'moderate' | 'aggressive';
export type ExerciseName = 'squat' | 'push_up';
export type FatigueLevel = 'building_baseline' | 'normal' | 'moderate' | 'high';
export type FormQuality = 'good' | 'bad';
export type SessionStatus = 'exercising' | 'resting' | 'complete';

export interface UserProfile {
  age: number;
  injury: InjuryType;
  mobility: MobilityLevel;
  pain_tolerance: number;
  difficulty?: Difficulty;
}

export interface Exercise {
  name: ExerciseName;
  sets: number;
  reps_per_set: number;
  rest_seconds: number;
  coaching_cues: string[];
  safety_warnings: string[];
}

export interface RehabPlan {
  exercises: Exercise[];
  warmup: string;
  cooldown: string;
  overall_safety: string;
}

export interface FrameMessage {
  type: 'frame';
  image: string;
}

/** [x, y, visibility] in normalized image coordinates */
export type LandmarkPoint = [number, number, number];

export interface ExerciseUpdate {
  status: SessionStatus;
  exercise: ExerciseName;
  exercise_index: number;
  set_number: number;
  total_sets: number;
  rep_in_set: number;
  reps_per_set: number;
  rep_count: number;
  phase: string;
  form_score: number | null;
  joint_scores: Record<string, number>;
  fatigue_level: FatigueLevel;
  fatigue_drift: number;
  ml_form_quality?: FormQuality | null;
  rest_seconds_remaining?: number | null;
  landmarks?: LandmarkPoint[] | null;
}

export interface RepSummary {
  exercise: ExerciseName;
  set_number: number;
  rep_number: number;
  form_score: number;
  fatigue_drift: number;
  fatigue_level: FatigueLevel;
}

export interface SessionReport {
  session_id: string;
  total_reps: number;
  total_exercises: number;
  avg_form_score: number;
  max_fatigue_drift: number;
  fatigue_alerts_count: number;
  xp_earned: number;
  badges: string[];
  reps: RepSummary[];
  duration_seconds: number;
}

export interface HistoryEntry {
  session_id: string;
  created_at: string;
  exercises: ExerciseName[];
  total_reps: number;
  avg_form_score: number;
}
