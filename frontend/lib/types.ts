// Mirrors backend/core/schema.py. Keep the two in sync.

export type InjuryType = 'knee' | 'shoulder' | 'upper_body' | 'lower_body' | 'general';
export type MobilityLevel = 'limited' | 'moderate' | 'full';
export type Difficulty = 'conservative' | 'moderate' | 'aggressive';
export type ExerciseName = 'squat' | 'push_up';
export type FatigueLevel = 'building_baseline' | 'normal' | 'moderate' | 'high';
export type FormQuality = 'good' | 'bad';
export type SessionStatus = 'exercising' | 'resting' | 'complete';
export type PostureCheck = 'good' | 'needs_attention' | 'acceptable_for_rehab_depth';
export type AnalysisStatus = 'pending' | 'complete' | 'unavailable';

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

export interface SkipRestMessage {
  type: 'skip_rest';
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
  /** Rule-based phase: drives rep counting and scoring */
  phase: string;
  /** null when no person was detected */
  form_score: number | null;
  joint_scores: Record<string, number>;
  fatigue_level: FatigueLevel;
  fatigue_drift: number;
  // ML signals: squat only, null for push-ups or occluded joints
  ml_phase: string | null;
  ml_phase_confidence: number | null;
  /** Verdicts for the last completed rep */
  ml_form_quality: FormQuality | null;
  posture_check: PostureCheck | null;
  anomaly_score: number | null;
  is_anomalous: boolean;
  asymmetry_detected: boolean;
  /** Degrees of left/right difference by joint, only joints over the threshold */
  asymmetry_details: Record<string, number>;
  rest_seconds_remaining: number | null;
  /** LLM coaching for the set just completed; null while it loads */
  set_coaching: string | null;
  landmarks: LandmarkPoint[] | null;
}

export interface RepSummary {
  exercise: ExerciseName;
  set_number: number;
  rep_number: number;
  form_score: number;
  fatigue_drift: number;
  fatigue_level: FatigueLevel;
  ml_form_quality: FormQuality | null;
  posture_check: PostureCheck | null;
  asymmetry: Record<string, number>;
  is_anomalous: boolean;
}

export interface SetCoaching {
  exercise: ExerciseName;
  set_number: number;
  coaching_text: string;
}

export interface SessionAnalysis {
  summary: string;
  findings: string[];
  weak_joints: string[];
}

export interface TrendComparison {
  summary: string;
  trends: string[];
  recommendation: string;
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
  /** Mean left/right difference per joint, degrees */
  symmetry_summary: Record<string, number>;
  /** Frames flagged as unusual movement */
  anomaly_count: number;
  set_coaching: SetCoaching[];
  analysis_status: AnalysisStatus;
  ai_session_analysis: SessionAnalysis | null;
  ai_trend_comparison: TrendComparison | null;
  ai_next_plan: RehabPlan | null;
}

export interface SuggestedPlan {
  source_session_id: string;
  created_at: string;
  plan: RehabPlan;
}

export interface HistoryEntry {
  session_id: string;
  created_at: string;
  exercises: ExerciseName[];
  total_reps: number;
  avg_form_score: number;
}
