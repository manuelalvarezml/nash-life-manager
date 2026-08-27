import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import {
  startGoalDiscovery,
  chatGoalDiscovery,
  saveDiscoveredGoal,
  endGoalDiscovery,
  fetchGoalsGraph,
  createGoalRelation,
  deleteGoalRelation,
  deleteGoal,
  updateGoal,
  type DiscoverySession,
  type ExtractedGoal,
  type ExtractedGoalRelation,
  type Goal,
  type GoalGraphEdge,
  type GoalNodeType,
  type LifeDomain,
} from '../api';

interface GoalDiscoveryProps {
  domains: LifeDomain[];
  onClose: () => void;
  onGoalSaved: () => void;
}

interface PendingGoal extends ExtractedGoal {
  local_id: string;
}

interface PendingRelation extends ExtractedGoalRelation {
  local_id: string;
}

interface GraphNodeView {
  id: string;
  kind: 'saved' | 'pending';
  label: string;
  goal?: Goal;
  pendingGoal?: PendingGoal;
}

interface GraphEdgeView {
  id: string;
  source_goal_id: number;
  target_goal_id: number;
  relation_type: string;
  kind: 'parent' | 'relation' | 'pending_relation';
  relation_id: number | null;
  note: string | null;
  weight: number | null;
  sourceNodeId: string;
  targetNodeId: string;
}

interface GoalEditDraft {
  node_type: GoalNodeType;
  title: string;
  description: string;
  why_matters: string;
  domain_code: string;
  domain_tags_input: string;
  horizon: string;
  start_date: string;
  target_date: string;
  cadence_text: string;
  time_cost_min: string;
  energy_cost: string;
  attention_cost: string;
  status: Goal['status'];
  progress_pct: number;
  motivation_type: string;
  importance: string;
  difficulty: string;
  commitment: string;
  specificity: string;
  locus_of_control: string;
  nash_opinion: string;
  coherence_score: string;
  conflicts_json: string;
  synergies_json: string;
  priority_rank: string;
}

interface PendingRelationDraft {
  source_title: string;
  target_title: string;
  relation_type: string;
  note: string;
}

const HORIZON_LABELS: Record<string, string> = {
  life: 'Vida',
  annual: 'Anual',
  quarterly: 'Trimestral',
  monthly: 'Mensual',
  weekly: 'Semanal',
};

const STATUS_LABELS: Record<Goal['status'], string> = {
  active: 'Activa',
  completed: 'Completada',
  paused: 'Pausada',
  abandoned: 'Abandonada',
};

const MOTIVATION_LABELS: Record<string, string> = {
  external: 'Externa',
  introjected: 'Introyectada',
  identified: 'Identificada',
  intrinsic: 'Intrínseca',
};

const NODE_TYPE_LABELS: Record<GoalNodeType, string> = {
  identity: 'Identity',
  goal: 'Goal',
  system: 'System',
  action: 'Action',
};

const NODE_TYPE_ICONS: Record<GoalNodeType, string> = {
  identity: '◎',
  goal: '◆',
  system: '⚙',
  action: '→',
};

const RELATION_OPTIONS = [
  { value: 'requires', label: 'Requiere' },
  { value: 'drives', label: 'Impulsa' },
  { value: 'reinforces', label: 'Refuerza' },
  { value: 'conflicts_with', label: 'Conflicto' },
  { value: 'costs', label: 'Costo' },
  { value: 'depends_on', label: 'Dependencia (legacy)' },
  { value: 'synergy', label: 'Afinidad (legacy)' },
  { value: 'supports', label: 'Apoya' },
  { value: 'blocks', label: 'Bloquea' },
  { value: 'related', label: 'Relacionada' },
] as const;

const RELATION_LABELS: Record<string, string> = {
  parent_child: 'Jerarquía',
  requires: 'Requiere',
  drives: 'Impulsa',
  reinforces: 'Refuerza',
  costs: 'Costo',
  related: 'Relacionada',
  supports: 'Apoya',
  depends_on: 'Depende de',
  conflicts_with: 'Conflicto',
  synergy: 'Sinergia',
  blocks: 'Bloquea',
};

const EDGE_CATEGORY_LABELS = {
  dependence: 'Dependencia',
  affinity: 'Afinidad',
  conflict: 'Conflicto',
} as const;

const EDGE_CATEGORY_COLORS = {
  dependence: '#2563EB',
  affinity: '#16A34A',
  conflict: '#DC2626',
} as const;

function getEdgeCategory(edge: GraphEdgeView): 'dependence' | 'affinity' | 'conflict' {
  if (edge.relation_type === 'parent_child' || edge.relation_type === 'depends_on' || edge.relation_type === 'requires') return 'dependence';
  if (edge.relation_type === 'conflicts_with' || edge.relation_type === 'blocks' || edge.relation_type === 'costs') return 'conflict';
  return 'affinity';
}

function getEdgeColor(edge: GraphEdgeView, selected: boolean): string {
  const base = EDGE_CATEGORY_COLORS[getEdgeCategory(edge)];
  return selected ? base : `${base}CC`;
}

function getDepthTargetY(depth: number, maxDepth: number, height: number): number {
  const top = 34;
  const bottom = Math.max(top + 1, height - 34);
  if (maxDepth <= 0) return (top + bottom) / 2;
  return top + (depth / maxDepth) * (bottom - top);
}

function getColorByChildCount(childrenCount: number): string {
  if (childrenCount >= 5) return '#16A34A';
  if (childrenCount >= 3) return '#0EA5E9';
  if (childrenCount >= 1) return '#14B8A6';
  return '#6366F1';
}

function parseDomainTagsInput(raw: string): string[] {
  return raw
    .replace(/,/g, '|')
    .split('|')
    .map((tag) => tag.trim().toLowerCase())
    .filter(Boolean);
}

function makeGoalFingerprint(goal: { title?: string | null; domain_code?: string | null; horizon?: string | null }) {
  const title = (goal.title || '').trim().toLowerCase();
  const nodeType = ((goal as ExtractedGoal).node_type || 'goal').trim().toLowerCase();
  const horizon = (goal.horizon || '').trim().toLowerCase();
  return `${title}|${nodeType}|${horizon}`;
}

function getNodeColor(node: GraphNodeView, selected: boolean, childrenCount: number): string {
  if (selected) return '#2563EB';
  if (node.kind === 'pending') return '#F59E0B';
  if (node.goal?.status === 'abandoned') return '#9CA3AF';
  return getColorByChildCount(childrenCount);
}

function nodeSupportsHorizon(nodeType: GoalNodeType): boolean {
  return nodeType === 'goal' || nodeType === 'system';
}

function nodeRequiresHorizon(nodeType: GoalNodeType): boolean {
  return nodeType === 'goal';
}

function nodeSupportsCadence(nodeType: GoalNodeType): boolean {
  return nodeType === 'system';
}

function nodeSupportsActionCosts(nodeType: GoalNodeType): boolean {
  return nodeType === 'action';
}

function canParentNode(parentType: GoalNodeType, childType: GoalNodeType): boolean {
  if (parentType === 'identity') return childType === 'goal' || childType === 'system';
  if (parentType === 'goal') return childType === 'goal' || childType === 'system' || childType === 'action';
  if (parentType === 'system') return childType === 'action';
  return false;
}

export function GoalDiscovery({ domains, onClose, onGoalSaved }: GoalDiscoveryProps) {
  const [session, setSession] = useState<DiscoverySession | null>(null);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [textInput, setTextInput] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingGoals, setPendingGoals] = useState<PendingGoal[]>([]);
  const [pendingRelations, setPendingRelations] = useState<PendingRelation[]>([]);
  const [savingGoalId, setSavingGoalId] = useState<string | null>(null);
  const [suppressedGoalFingerprints, setSuppressedGoalFingerprints] = useState<string[]>([]);

  const [savedGoals, setSavedGoals] = useState<Goal[]>([]);
  const [graphEdges, setGraphEdges] = useState<GoalGraphEdge[]>([]);
  const [graphLoading, setGraphLoading] = useState(false);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
  const [savingBatchGoals, setSavingBatchGoals] = useState(false);
  const [editingGoal, setEditingGoal] = useState(false);
  const [savingGoalEdits, setSavingGoalEdits] = useState(false);
  const [goalEditDraft, setGoalEditDraft] = useState<GoalEditDraft | null>(null);

  const [relationType, setRelationType] = useState<(typeof RELATION_OPTIONS)[number]['value']>('supports');
  const [relationTargetId, setRelationTargetId] = useState<string>('');
  const [relationNote, setRelationNote] = useState('');
  const [savingRelation, setSavingRelation] = useState(false);
  const [updatingParent, setUpdatingParent] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const pendingCounterRef = useRef(0);
  const pendingRelationCounterRef = useRef(0);

  const graphContainerRef = useRef<HTMLDivElement>(null);
  const nodeStateRef = useRef<Record<string, { x: number; y: number; vx: number; vy: number }>>({});
  const [graphSize, setGraphSize] = useState({ width: 380, height: 260 });
  const [renderVersion, setRenderVersion] = useState(0);

  const buildPendingGoals = useCallback((goals: ExtractedGoal[] | undefined): PendingGoal[] => {
    const source = goals || [];
    const seen = new Set<string>();
    const suppressed = new Set(suppressedGoalFingerprints);
    const built: PendingGoal[] = [];

    for (const goal of source) {
      const fingerprint = makeGoalFingerprint(goal);
      if (!goal.title || seen.has(fingerprint) || suppressed.has(fingerprint)) continue;
      seen.add(fingerprint);
      built.push({
        ...goal,
        local_id: `${Date.now()}-${pendingCounterRef.current++}`,
      });
    }

    return built;
  }, [suppressedGoalFingerprints]);

  const buildPendingRelations = useCallback((relations: ExtractedGoalRelation[] | undefined): PendingRelation[] => {
    const source = relations || [];
    const seen = new Set<string>();
    const built: PendingRelation[] = [];

    for (const relation of source) {
      const key = `${relation.source_title}|${relation.target_title}|${relation.relation_type}`;
      if (!relation.source_title || !relation.target_title || seen.has(key)) continue;
      seen.add(key);
      built.push({
        ...relation,
        local_id: `rel-${Date.now()}-${pendingRelationCounterRef.current++}`,
      });
    }

    return built;
  }, []);

  const appendPendingGoals = useCallback((goals: ExtractedGoal[] | undefined) => {
    const incoming = goals || [];
    if (incoming.length === 0) return;

    setPendingGoals((prev) => {
      const seen = new Set(prev.map((goal) => makeGoalFingerprint(goal)));
      const suppressed = new Set(suppressedGoalFingerprints);
      const additions: PendingGoal[] = [];

      for (const goal of incoming) {
        if (!goal.title) continue;
        const fingerprint = makeGoalFingerprint(goal);
        if (seen.has(fingerprint) || suppressed.has(fingerprint)) continue;
        seen.add(fingerprint);
        additions.push({
          ...goal,
          local_id: `${Date.now()}-${pendingCounterRef.current++}`,
        });
      }

      if (additions.length === 0) return prev;
      return [...prev, ...additions];
    });
  }, [suppressedGoalFingerprints]);

  const appendPendingRelations = useCallback((relations: ExtractedGoalRelation[] | undefined) => {
    const incoming = relations || [];
    if (incoming.length === 0) return;

    setPendingRelations((prev) => {
      const seen = new Set(prev.map((relation) => `${relation.source_title}|${relation.target_title}|${relation.relation_type}`));
      const additions: PendingRelation[] = [];
      for (const relation of incoming) {
        const key = `${relation.source_title}|${relation.target_title}|${relation.relation_type}`;
        if (!relation.source_title || !relation.target_title || seen.has(key)) continue;
        seen.add(key);
        additions.push({
          ...relation,
          local_id: `rel-${Date.now()}-${pendingRelationCounterRef.current++}`,
        });
      }
      if (additions.length === 0) return prev;
      return [...prev, ...additions];
    });
  }, []);

  const loadGraph = useCallback(async () => {
    setGraphLoading(true);
    try {
      const graph = await fetchGoalsGraph('all');
      setSavedGoals(graph.nodes || []);
      setGraphEdges(graph.edges || []);
    } catch {
      setError('No se pudo cargar el grafo de metas.');
    } finally {
      setGraphLoading(false);
    }
  }, []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [session?.messages]);

  // Keep pending list clean when a goal is already saved.
  useEffect(() => {
    if (!savedGoals.length) return;
    const savedFingerprints = new Set(savedGoals.map((goal) => makeGoalFingerprint(goal)));
    setPendingGoals((prev) => prev.filter((goal) => !savedFingerprints.has(makeGoalFingerprint(goal))));
  }, [savedGoals]);

  // Initialize session + graph
  useEffect(() => {
    const init = async () => {
      setLoading(true);
      try {
        const [sessionResult] = await Promise.all([startGoalDiscovery(), loadGraph()]);

        if (sessionResult.ok && sessionResult.session) {
          setSession(sessionResult.session);
          // Do not rehydrate all historical extracted goals when resuming; only add new ones from now on.
          if (sessionResult.resumed) {
            setPendingGoals([]);
            setPendingRelations([]);
          } else {
            setPendingGoals(buildPendingGoals(sessionResult.session.extracted_goals));
            setPendingRelations(buildPendingRelations(sessionResult.session.extracted_relations));
          }
          if (sessionResult.resumed) {
            setError(null);
          }
        } else {
          setError(sessionResult.error || 'Error starting session');
        }
      } catch {
        setError('Error connecting to server');
      } finally {
        setLoading(false);
      }
    };
    init();
  }, [buildPendingGoals, buildPendingRelations, loadGraph]);

  const sendMessage = useCallback(async (text?: string, audioBlob?: Blob) => {
    if (!session || (!text?.trim() && !audioBlob)) return;

    setSending(true);
    setError(null);

    try {
      const result = await chatGoalDiscovery(session.id, text, audioBlob);

      if (result.ok && result.session) {
        setSession(result.session);
        setTextInput('');
        appendPendingGoals(result.extracted_goals);
        appendPendingRelations(result.extracted_relations);
      } else {
        setError(result.error || 'Error sending message');
      }
    } catch {
      setError('Error communicating with Nash');
    } finally {
      setSending(false);
    }
  }, [appendPendingGoals, appendPendingRelations, session]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (textInput.trim()) {
      sendMessage(textInput.trim());
    }
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: 'audio/webm;codecs=opus',
      });

      chunksRef.current = [];

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          chunksRef.current.push(e.data);
        }
      };

      mediaRecorder.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        const audioBlob = new Blob(chunksRef.current, { type: 'audio/webm' });
        if (audioBlob.size > 0) {
          sendMessage(undefined, audioBlob);
        }
      };

      mediaRecorderRef.current = mediaRecorder;
      mediaRecorder.start();
      setIsRecording(true);
    } catch {
      setError('No se pudo acceder al microfono');
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };

  const resolveGraphNodeIdByTitle = useCallback((
    title: string,
    savedList: Goal[] = savedGoals,
    pendingList: PendingGoal[] = pendingGoals,
  ): string | null => {
    const normalized = title.trim().toLowerCase();
    if (!normalized) return null;

    const pendingMatch = pendingList.find((goal) => goal.title?.trim().toLowerCase() === normalized);
    if (pendingMatch) return `pending-${pendingMatch.local_id}`;

    const savedMatch = savedList.find((goal) => goal.title?.trim().toLowerCase() === normalized);
    if (savedMatch) return `goal-${savedMatch.id}`;

    return null;
  }, [pendingGoals, savedGoals]);

  const persistReadyPendingRelations = useCallback(async (
    savedList: Goal[],
    pendingList: PendingGoal[],
  ) => {
    const ready = pendingRelations.filter((relation) => {
      const source = resolveGraphNodeIdByTitle(relation.source_title, savedList, pendingList);
      const target = resolveGraphNodeIdByTitle(relation.target_title, savedList, pendingList);
      return source?.startsWith('goal-') && target?.startsWith('goal-');
    });

    if (ready.length === 0) return;

    const persistedIds: string[] = [];
    for (const relation of ready) {
      const sourceNodeId = resolveGraphNodeIdByTitle(relation.source_title, savedList, pendingList);
      const targetNodeId = resolveGraphNodeIdByTitle(relation.target_title, savedList, pendingList);
      if (!sourceNodeId?.startsWith('goal-') || !targetNodeId?.startsWith('goal-')) continue;

      const result = await createGoalRelation({
        source_goal_id: Number(sourceNodeId.replace('goal-', '')),
        target_goal_id: Number(targetNodeId.replace('goal-', '')),
        relation_type: relation.relation_type as (typeof RELATION_OPTIONS)[number]['value'],
        note: relation.note || undefined,
      });
      if (result.ok) {
        persistedIds.push(relation.local_id);
      }
    }

    if (persistedIds.length > 0) {
      setPendingRelations((prev) => prev.filter((relation) => !persistedIds.includes(relation.local_id)));
      await loadGraph();
    }
  }, [loadGraph, pendingRelations, resolveGraphNodeIdByTitle]);

  const handleSaveGoal = async (localId: string) => {
    if (!session) return;

    const goal = pendingGoals.find((pending) => pending.local_id === localId);
    if (!goal) return;

    setSavingGoalId(localId);
    setError(null);

    try {
      const result = await saveDiscoveredGoal(session.id, goal);
      if (result.ok && result.goal) {
        const fingerprint = makeGoalFingerprint(goal);
        const nextPendingGoals = pendingGoals.filter((pending) => pending.local_id !== localId);
        const nextSavedGoals = [result.goal, ...savedGoals.filter((item) => item.id !== result.goal!.id)];
        setSuppressedGoalFingerprints((prev) => (prev.includes(fingerprint) ? prev : [...prev, fingerprint]));
        setPendingGoals(nextPendingGoals);
        setSavedGoals(nextSavedGoals);
        await persistReadyPendingRelations(nextSavedGoals, nextPendingGoals);
        onGoalSaved();
        setSelectedEdgeId(null);

        setSelectedNodeId(`goal-${result.goal.id}`);
      } else {
        setError(result.error || 'Error saving goal');
      }
    } catch {
      setError('Error saving goal');
    } finally {
      setSavingGoalId(null);
    }
  };

  const handleDismissGoal = (localId: string) => {
    const goal = pendingGoals.find((item) => item.local_id === localId);
    if (goal) {
      const fingerprint = makeGoalFingerprint(goal);
      const normalizedTitle = (goal.title || '').trim().toLowerCase();
      setSuppressedGoalFingerprints((prev) => (prev.includes(fingerprint) ? prev : [...prev, fingerprint]));
      setPendingRelations((prev) =>
        prev.filter((relation) => {
          const source = relation.source_title.trim().toLowerCase();
          const target = relation.target_title.trim().toLowerCase();
          return source !== normalizedTitle && target !== normalizedTitle;
        }),
      );
    }
    setPendingGoals((prev) => prev.filter((item) => item.local_id !== localId));
  };

  const handleSaveBatchGoals = async (count: number) => {
    if (!session || pendingGoals.length === 0) return;
    setSavingBatchGoals(true);
    setError(null);

    const subset = pendingGoals.slice(0, count);
    let savedCount = 0;
    let lastSavedGoalId: number | null = null;
    let nextSavedGoals = [...savedGoals];
    let nextPendingGoals = [...pendingGoals];

    for (const goal of subset) {
      try {
        const result = await saveDiscoveredGoal(session.id, goal);
        if (result.ok && result.goal) {
          savedCount += 1;
          lastSavedGoalId = result.goal.id;
          const fingerprint = makeGoalFingerprint(goal);
          setSuppressedGoalFingerprints((prev) => (prev.includes(fingerprint) ? prev : [...prev, fingerprint]));
          nextPendingGoals = nextPendingGoals.filter((pending) => pending.local_id !== goal.local_id);
          nextSavedGoals = [result.goal, ...nextSavedGoals.filter((item) => item.id !== result.goal!.id)];
        }
      } catch {
        // Continue batch save and report summary below.
      }
    }

    setPendingGoals(nextPendingGoals);
    setSavedGoals(nextSavedGoals);
    await persistReadyPendingRelations(nextSavedGoals, nextPendingGoals);

    onGoalSaved();
    setSelectedEdgeId(null);
    if (lastSavedGoalId != null) {
      setSelectedNodeId(`goal-${lastSavedGoalId}`);
    }
    if (savedCount === 0) {
      setError('No se pudo guardar el lote de metas.');
    }
    setSavingBatchGoals(false);
  };

  const handlePendingGoalFieldChange = (
    localId: string,
    field: keyof PendingGoal,
    value: string | number | null | string[],
  ) => {
    setPendingGoals((prev) =>
      prev.map((goal) => {
        if (goal.local_id !== localId) return goal;
        return { ...goal, [field]: value } as PendingGoal;
      }),
    );
  };

  const handlePendingRelationFieldChange = (
    localId: string,
    field: keyof PendingRelationDraft,
    value: string,
  ) => {
    setPendingRelations((prev) =>
      prev.map((relation) => {
        if (relation.local_id !== localId) return relation;
        return {
          ...relation,
          [field]: value,
        };
      }),
    );
  };

  const handleDismissPendingRelation = (localId: string) => {
    setPendingRelations((prev) => prev.filter((relation) => relation.local_id !== localId));
    if (selectedEdgeId === `pending-relation-${localId}`) {
      setSelectedEdgeId(null);
    }
  };

  const handleDeleteSavedGoal = async () => {
    if (!selectedSavedGoal) return;
    if (!confirm(`¿Eliminar meta "${selectedSavedGoal.title}"?`)) return;

    const goalId = selectedSavedGoal.id;
    const fingerprint = makeGoalFingerprint(selectedSavedGoal);
    setError(null);

    try {
      const result = await deleteGoal(goalId);
      if (!result.ok) {
        setError(result.error || 'No se pudo eliminar la meta.');
        return;
      }

      setSuppressedGoalFingerprints((prev) => (prev.includes(fingerprint) ? prev : [...prev, fingerprint]));
      setSavedGoals((prev) => prev.filter((goal) => goal.id !== goalId));
      setGraphEdges((prev) => prev.filter((edge) => edge.source_goal_id !== goalId && edge.target_goal_id !== goalId));
      setPendingGoals((prev) => prev.filter((goal) => makeGoalFingerprint(goal) !== fingerprint));
      setSelectedNodeId(null);
      setSelectedEdgeId(null);
      onGoalSaved();
    } catch {
      setError('Error eliminando meta.');
    }
  };

  const handleEndSession = async () => {
    if (!session) return;

    try {
      await endGoalDiscovery(session.id);
      onClose();
    } catch {
      setError('Error ending session');
    }
  };

  const combinedNodes = useMemo<GraphNodeView[]>(() => {
    const saved = savedGoals.map((goal) => ({
      id: `goal-${goal.id}`,
      kind: 'saved' as const,
      label: goal.title,
      goal,
    }));

    const pending = pendingGoals.map((goal) => ({
      id: `pending-${goal.local_id}`,
      kind: 'pending' as const,
      label: goal.title,
      pendingGoal: goal,
    }));

    return [...saved, ...pending];
  }, [savedGoals, pendingGoals]);

  const combinedEdges = useMemo<GraphEdgeView[]>(() => {
    const availableNodeIds = new Set(combinedNodes.map((node) => node.id));
    const persistedEdges: GraphEdgeView[] = (graphEdges || [])
      .map((edge) => ({
        ...edge,
        sourceNodeId: `goal-${edge.source_goal_id}`,
        targetNodeId: `goal-${edge.target_goal_id}`,
      }))
      .filter((edge) => availableNodeIds.has(edge.sourceNodeId) && availableNodeIds.has(edge.targetNodeId));

    const stagedEdges: GraphEdgeView[] = [];
    for (const relation of pendingRelations) {
      const sourceNodeId = resolveGraphNodeIdByTitle(relation.source_title);
      const targetNodeId = resolveGraphNodeIdByTitle(relation.target_title);
      if (!sourceNodeId || !targetNodeId) continue;
      if (!availableNodeIds.has(sourceNodeId) || !availableNodeIds.has(targetNodeId)) continue;
      stagedEdges.push({
        id: `pending-relation-${relation.local_id}`,
        source_goal_id: sourceNodeId.startsWith('goal-') ? Number(sourceNodeId.replace('goal-', '')) : -1,
        target_goal_id: targetNodeId.startsWith('goal-') ? Number(targetNodeId.replace('goal-', '')) : -1,
        relation_type: relation.relation_type,
        kind: 'pending_relation',
        relation_id: null,
        note: relation.note || null,
        weight: null,
        sourceNodeId,
        targetNodeId,
      });
    }

    return [...persistedEdges, ...stagedEdges];
  }, [combinedNodes, graphEdges, pendingRelations, resolveGraphNodeIdByTitle]);

  const hierarchyLayout = useMemo(() => {
    const nodeIds = combinedNodes.map((node) => node.id);
    const parentEdges = combinedEdges.filter((edge) => edge.kind === 'parent');
    const parentByChild = new Map<string, string[]>();
    const childrenCountByNodeId: Record<string, number> = {};

    for (const nodeId of nodeIds) {
      childrenCountByNodeId[nodeId] = 0;
    }

    for (const edge of parentEdges) {
      const list = parentByChild.get(edge.targetNodeId) || [];
      list.push(edge.sourceNodeId);
      parentByChild.set(edge.targetNodeId, list);
      childrenCountByNodeId[edge.sourceNodeId] = (childrenCountByNodeId[edge.sourceNodeId] || 0) + 1;
    }

    const depthMemo = new Map<string, number>();
    const visiting = new Set<string>();

    const computeDepth = (nodeId: string): number => {
      if (depthMemo.has(nodeId)) return depthMemo.get(nodeId)!;
      if (visiting.has(nodeId)) return 0;

      visiting.add(nodeId);
      const parents = parentByChild.get(nodeId) || [];
      let depth = 0;
      if (parents.length > 0) {
        const parentDepths = parents.map((parentId) => computeDepth(parentId));
        depth = Math.min(...parentDepths) + 1;
      }
      visiting.delete(nodeId);
      depthMemo.set(nodeId, depth);
      return depth;
    };

    const depthByNodeId: Record<string, number> = {};
    let maxDepth = 0;
    for (const nodeId of nodeIds) {
      const depth = computeDepth(nodeId);
      depthByNodeId[nodeId] = depth;
      maxDepth = Math.max(maxDepth, depth);
    }

    return {
      depthByNodeId,
      maxDepth,
      childrenCountByNodeId,
    };
  }, [combinedEdges, combinedNodes]);

  const savedGoalById = useMemo(() => {
    const map = new Map<number, Goal>();
    for (const goal of savedGoals) {
      map.set(goal.id, goal);
    }
    return map;
  }, [savedGoals]);

  const selectedSavedGoal = useMemo(() => {
    if (!selectedNodeId || !selectedNodeId.startsWith('goal-')) return null;
    const goalId = Number(selectedNodeId.replace('goal-', ''));
    return savedGoalById.get(goalId) || null;
  }, [savedGoalById, selectedNodeId]);

  const selectedPendingGoal = useMemo(() => {
    if (!selectedNodeId || !selectedNodeId.startsWith('pending-')) return null;
    const localId = selectedNodeId.replace('pending-', '');
    return pendingGoals.find((goal) => goal.local_id === localId) || null;
  }, [pendingGoals, selectedNodeId]);

  const selectedNodeRelations = useMemo(() => {
    if (!selectedSavedGoal) return [];
    return combinedEdges.filter(
      (edge) => edge.source_goal_id === selectedSavedGoal.id || edge.target_goal_id === selectedSavedGoal.id,
    );
  }, [combinedEdges, selectedSavedGoal]);

  const selectedEdge = useMemo(() => {
    if (!selectedEdgeId) return null;
    return combinedEdges.find((edge) => edge.id === selectedEdgeId) || null;
  }, [combinedEdges, selectedEdgeId]);

  const selectedPendingRelation = useMemo(() => {
    if (!selectedEdgeId || !selectedEdgeId.startsWith('pending-relation-')) return null;
    const localId = selectedEdgeId.replace('pending-relation-', '');
    return pendingRelations.find((relation) => relation.local_id === localId) || null;
  }, [pendingRelations, selectedEdgeId]);

  // Keep selected node valid.
  useEffect(() => {
    if (!selectedNodeId) return;
    const exists = combinedNodes.some((node) => node.id === selectedNodeId);
    if (!exists) {
      setSelectedNodeId(null);
    }
  }, [combinedNodes, selectedNodeId]);

  useEffect(() => {
    if (!selectedEdgeId) return;
    const exists = combinedEdges.some((edge) => edge.id === selectedEdgeId);
    if (!exists) {
      setSelectedEdgeId(null);
    }
  }, [combinedEdges, selectedEdgeId]);

  // Set a default relation target whenever the selected saved goal changes.
  useEffect(() => {
    if (!selectedSavedGoal) return;
    const firstCandidate = savedGoals.find(
      (goal) => goal.id !== selectedSavedGoal.id && canParentNode(goal.node_type, selectedSavedGoal.node_type),
    );
    setRelationTargetId(firstCandidate ? String(firstCandidate.id) : '');
  }, [savedGoals, selectedSavedGoal]);

  useEffect(() => {
    if (!selectedSavedGoal) {
      setEditingGoal(false);
      setGoalEditDraft(null);
      return;
    }

    const tags = selectedSavedGoal.domain_tags || [];
    const conflictsText =
      typeof selectedSavedGoal.conflicts_json === 'string'
        ? selectedSavedGoal.conflicts_json
        : JSON.stringify(selectedSavedGoal.conflicts_json ?? [], null, 2);
    const synergiesText =
      typeof selectedSavedGoal.synergies_json === 'string'
        ? selectedSavedGoal.synergies_json
        : JSON.stringify(selectedSavedGoal.synergies_json ?? [], null, 2);

    setGoalEditDraft({
      node_type: selectedSavedGoal.node_type || 'goal',
      title: selectedSavedGoal.title || '',
      description: selectedSavedGoal.description || '',
      why_matters: selectedSavedGoal.why_matters || '',
      domain_code: selectedSavedGoal.domain_code || '',
      domain_tags_input: tags.join(' | '),
      horizon: selectedSavedGoal.horizon || 'quarterly',
      start_date: selectedSavedGoal.start_date || '',
      target_date: selectedSavedGoal.target_date || '',
      cadence_text: selectedSavedGoal.cadence_text || '',
      time_cost_min: selectedSavedGoal.time_cost_min != null ? String(selectedSavedGoal.time_cost_min) : '',
      energy_cost: selectedSavedGoal.energy_cost != null ? String(selectedSavedGoal.energy_cost) : '',
      attention_cost: selectedSavedGoal.attention_cost != null ? String(selectedSavedGoal.attention_cost) : '',
      status: selectedSavedGoal.status || 'active',
      progress_pct: selectedSavedGoal.progress_pct ?? 0,
      motivation_type: selectedSavedGoal.motivation_type || '',
      importance: selectedSavedGoal.importance != null ? String(selectedSavedGoal.importance) : '',
      difficulty: selectedSavedGoal.difficulty != null ? String(selectedSavedGoal.difficulty) : '',
      commitment: selectedSavedGoal.commitment != null ? String(selectedSavedGoal.commitment) : '',
      specificity: selectedSavedGoal.specificity != null ? String(selectedSavedGoal.specificity) : '',
      locus_of_control: selectedSavedGoal.locus_of_control || '',
      nash_opinion: selectedSavedGoal.nash_opinion || '',
      coherence_score: selectedSavedGoal.coherence_score != null ? String(selectedSavedGoal.coherence_score) : '',
      conflicts_json: conflictsText || '[]',
      synergies_json: synergiesText || '[]',
      priority_rank: selectedSavedGoal.priority_rank != null ? String(selectedSavedGoal.priority_rank) : '',
    });
    setEditingGoal(true);
  }, [selectedSavedGoal]);

  // Keep graph size synced with container size.
  useEffect(() => {
    const el = graphContainerRef.current;
    if (!el) return;

    const update = () => {
      setGraphSize({
        width: Math.max(260, el.clientWidth),
        height: Math.max(220, el.clientHeight),
      });
    };

    update();

    const observer = new ResizeObserver(update);
    observer.observe(el);

    return () => observer.disconnect();
  }, []);

  // Initialize node positions for new nodes.
  useEffect(() => {
    const width = graphSize.width;
    const height = graphSize.height;

    const ids = new Set(combinedNodes.map((node) => node.id));
    const state = nodeStateRef.current;

    for (const key of Object.keys(state)) {
      if (!ids.has(key)) {
        delete state[key];
      }
    }

    combinedNodes.forEach((node) => {
      if (!state[node.id]) {
        const depth = hierarchyLayout.depthByNodeId[node.id] || 0;
        const targetY = getDepthTargetY(depth, hierarchyLayout.maxDepth, height);
        state[node.id] = {
          x: 28 + Math.random() * Math.max(1, width - 56),
          y: targetY + (Math.random() - 0.5) * 22,
          vx: 0,
          vy: 0,
        };
      }
    });
  }, [combinedNodes, graphSize.height, graphSize.width, hierarchyLayout.depthByNodeId, hierarchyLayout.maxDepth]);

  // Floating force simulation.
  useEffect(() => {
    if (combinedNodes.length === 0) return;

    let rafId = 0;
    let frameCount = 0;

    const step = () => {
      const width = graphSize.width;
      const height = graphSize.height;
      const state = nodeStateRef.current;

      const nodeIds = combinedNodes.map((node) => node.id);

      // Repulsion between every node pair.
      for (let i = 0; i < nodeIds.length; i += 1) {
        for (let j = i + 1; j < nodeIds.length; j += 1) {
          const a = state[nodeIds[i]];
          const b = state[nodeIds[j]];
          if (!a || !b) continue;

          const dx = a.x - b.x;
          const dy = a.y - b.y;
          const distSq = Math.max(dx * dx + dy * dy, 1);
          const dist = Math.sqrt(distSq);
          const force = 1200 / distSq;
          const fx = (dx / dist) * force;
          const fy = (dy / dist) * force;

          a.vx += fx;
          a.vy += fy;
          b.vx -= fx;
          b.vy -= fy;
        }
      }

      // Attraction along edges.
      for (const edge of combinedEdges) {
        const source = state[edge.sourceNodeId];
        const target = state[edge.targetNodeId];
        if (!source || !target) continue;

        const dx = target.x - source.x;
        const dy = target.y - source.y;
        const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
        const desired = edge.kind === 'parent' ? 105 : 140;
        const strength = edge.kind === 'parent' ? 0.01 : 0.007;
        const pull = (dist - desired) * strength;

        source.vx += dx * pull;
        source.vy += dy * pull;
        target.vx -= dx * pull;
        target.vy -= dy * pull;
      }

      // Global gravity and integration.
      const centerX = width / 2;
      for (const nodeId of nodeIds) {
        const node = state[nodeId];
        if (!node) continue;

        const depth = hierarchyLayout.depthByNodeId[nodeId] || 0;
        const targetY = getDepthTargetY(depth, hierarchyLayout.maxDepth, height);

        node.vx += (centerX - node.x) * 0.0007;
        node.vy += (targetY - node.y) * 0.006;

        node.vx *= 0.9;
        node.vy *= 0.9;

        node.x += node.vx;
        node.y += node.vy;

        const padding = 24;
        if (node.x < padding) {
          node.x = padding;
          node.vx *= -0.4;
        }
        if (node.x > width - padding) {
          node.x = width - padding;
          node.vx *= -0.4;
        }
        if (node.y < padding) {
          node.y = padding;
          node.vy *= -0.4;
        }
        if (node.y > height - padding) {
          node.y = height - padding;
          node.vy *= -0.4;
        }
      }

      frameCount += 1;
      if (frameCount % 2 === 0) {
        setRenderVersion((v) => v + 1);
      }
      rafId = requestAnimationFrame(step);
    };

    rafId = requestAnimationFrame(step);
    return () => cancelAnimationFrame(rafId);
  }, [combinedEdges, combinedNodes, graphSize.height, graphSize.width, hierarchyLayout.depthByNodeId, hierarchyLayout.maxDepth]);

  const renderedNodes = useMemo(
    () =>
      combinedNodes.map((node) => {
        const state = nodeStateRef.current[node.id];
        return {
          ...node,
          x: state?.x ?? graphSize.width / 2,
          y: state?.y ?? graphSize.height / 2,
        };
      }),
    [combinedNodes, graphSize.height, graphSize.width, renderVersion],
  );

  const handleUpdateParent = async (newParentIdRaw: string) => {
    if (!selectedSavedGoal) return;

    const parentGoalId = newParentIdRaw ? Number(newParentIdRaw) : null;
    setUpdatingParent(true);
    setError(null);

    try {
      const result = await updateGoal(selectedSavedGoal.id, { parent_goal_id: parentGoalId });
      if (!result.ok) {
        setError(result.error || 'No se pudo actualizar el nodo padre.');
      } else {
        await loadGraph();
        onGoalSaved();
      }
    } catch {
      setError('Error actualizando la jerarquía de esta meta.');
    } finally {
      setUpdatingParent(false);
    }
  };

  const handleCreateRelation = async () => {
    if (!selectedSavedGoal || !relationTargetId) return;

    setSavingRelation(true);
    setError(null);

    try {
      const result = await createGoalRelation({
        source_goal_id: selectedSavedGoal.id,
        target_goal_id: Number(relationTargetId),
        relation_type: relationType,
        note: relationNote.trim() || undefined,
      });

      if (!result.ok) {
        setError(result.error || 'No se pudo crear la relación.');
      } else {
        setRelationNote('');
        await loadGraph();
        setSelectedEdgeId(null);
      }
    } catch {
      setError('Error creando relación entre metas.');
    } finally {
      setSavingRelation(false);
    }
  };

  const handleDeleteRelation = async (relationId: number) => {
    setError(null);
    try {
      const result = await deleteGoalRelation(relationId);
      if (!result.ok) {
        setError(result.error || 'No se pudo eliminar la relación.');
      } else {
        await loadGraph();
        setSelectedEdgeId(null);
      }
    } catch {
      setError('Error eliminando la relación.');
    }
  };

  const handleSaveGoalEdits = async () => {
    if (!selectedSavedGoal || !goalEditDraft) return;

    setSavingGoalEdits(true);
    setError(null);

    const toInt = (raw: string) => {
      if (!raw.trim()) return null;
      const value = Number(raw);
      return Number.isFinite(value) ? Math.round(value) : null;
    };
    const toFloat = (raw: string) => {
      if (!raw.trim()) return null;
      const value = Number(raw);
      return Number.isFinite(value) ? value : null;
    };
    const parseJsonField = (raw: string) => {
      const text = raw.trim();
      if (!text) return '[]';
      try {
        return JSON.stringify(JSON.parse(text));
      } catch {
        return JSON.stringify(text.split('\n').map((line) => line.trim()).filter(Boolean));
      }
    };

    const updates = {
      node_type: goalEditDraft.node_type,
      title: goalEditDraft.title.trim(),
      description: goalEditDraft.description.trim() || null,
      why_matters: goalEditDraft.why_matters.trim() || null,
      domain_code: goalEditDraft.domain_code || null,
      domain_tags: parseDomainTagsInput(goalEditDraft.domain_tags_input),
      horizon: nodeSupportsHorizon(goalEditDraft.node_type) ? (goalEditDraft.horizon as Goal['horizon']) : null,
      start_date: goalEditDraft.start_date || null,
      target_date: goalEditDraft.target_date || null,
      cadence_text: nodeSupportsCadence(goalEditDraft.node_type) ? (goalEditDraft.cadence_text.trim() || null) : null,
      time_cost_min: nodeSupportsActionCosts(goalEditDraft.node_type) ? toInt(goalEditDraft.time_cost_min) : null,
      energy_cost: nodeSupportsActionCosts(goalEditDraft.node_type) ? toInt(goalEditDraft.energy_cost) : null,
      attention_cost: nodeSupportsActionCosts(goalEditDraft.node_type) ? toInt(goalEditDraft.attention_cost) : null,
      status: goalEditDraft.status,
      progress_pct: Math.max(0, Math.min(100, goalEditDraft.progress_pct)),
      motivation_type: (goalEditDraft.motivation_type || null) as Goal['motivation_type'],
      importance: toInt(goalEditDraft.importance),
      difficulty: toInt(goalEditDraft.difficulty),
      commitment: toInt(goalEditDraft.commitment),
      specificity: toInt(goalEditDraft.specificity),
      locus_of_control: (goalEditDraft.locus_of_control || null) as Goal['locus_of_control'],
      nash_opinion: goalEditDraft.nash_opinion.trim() || null,
      coherence_score: toFloat(goalEditDraft.coherence_score),
      conflicts_json: parseJsonField(goalEditDraft.conflicts_json),
      synergies_json: parseJsonField(goalEditDraft.synergies_json),
      priority_rank: toInt(goalEditDraft.priority_rank),
    };

    if (!updates.title) {
      setError('La meta necesita título.');
      setSavingGoalEdits(false);
      return;
    }

    try {
      const result = await updateGoal(selectedSavedGoal.id, updates);
      if (!result.ok || !result.goal) {
        setError(result.error || 'No se pudo actualizar la meta.');
      } else {
        setEditingGoal(false);
        setSavedGoals((prev) => prev.map((goal) => (goal.id === result.goal!.id ? result.goal! : goal)));
        onGoalSaved();
        setSelectedNodeId(`goal-${selectedSavedGoal.id}`);
      }
    } catch {
      setError('Error guardando cambios de la meta.');
    } finally {
      setSavingGoalEdits(false);
    }
  };

  if (loading) {
    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
        <div className="bg-[var(--nash-bg)] rounded-xl p-8 text-center">
          <div className="animate-spin h-8 w-8 border-2 border-[var(--nash-accent)] border-t-transparent rounded-full mx-auto mb-4" />
          <p className="text-[var(--nash-text-muted)]">Iniciando sesion de descubrimiento...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-[var(--nash-bg)] z-50 flex flex-col">
      {/* Header */}
      <div className="bg-[var(--nash-surface)] border-b border-[var(--nash-border)] px-4 py-3 flex items-center justify-between">
        <div>
          <h2 className="font-semibold text-[var(--nash-prussian)]">Explorar Mis Metas</h2>
          <p className="text-xs text-[var(--nash-text-muted)]">
            Conversa con Nash y forma tu mapa de metas en tiempo real
          </p>
        </div>
        <button
          onClick={handleEndSession}
          className="text-sm text-[var(--nash-text-muted)] hover:text-[var(--nash-text)] px-3 py-1 border border-[var(--nash-border)] rounded-lg cursor-pointer"
        >
          Terminar
        </button>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* Main chat area */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {(!session?.messages || session.messages.length === 0) && (
              <div className="text-center py-8 text-[var(--nash-text-muted)]">
                <p className="text-lg mb-2">Hola, estoy aqui para ayudarte a explorar tus metas.</p>
                <p className="text-sm">Cuentame: ¿que area de tu vida te gustaria mejorar?</p>
              </div>
            )}

            {session?.messages.map((msg, i) => (
              <div
                key={i}
                className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[80%] rounded-lg px-4 py-3 ${
                    msg.role === 'user'
                      ? 'bg-[var(--nash-accent)] text-white'
                      : 'bg-[var(--nash-surface)] border border-[var(--nash-border)]'
                  }`}
                >
                  <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                  <p className="text-xs opacity-60 mt-1">{msg.role === 'user' ? 'Tu' : 'Nash'}</p>
                </div>
              </div>
            ))}

            {sending && (
              <div className="flex justify-start">
                <div className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded-lg px-4 py-3">
                  <div className="flex items-center gap-2">
                    <div className="animate-pulse flex gap-1">
                      <span className="w-2 h-2 bg-[var(--nash-accent)] rounded-full"></span>
                      <span className="w-2 h-2 bg-[var(--nash-accent)] rounded-full animation-delay-200"></span>
                      <span className="w-2 h-2 bg-[var(--nash-accent)] rounded-full animation-delay-400"></span>
                    </div>
                    <span className="text-xs text-[var(--nash-text-muted)]">Nash esta pensando...</span>
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Error message */}
          {error && (
            <div className="px-4 py-2 bg-red-50 border-t border-red-200">
              <p className="text-sm text-red-600">{error}</p>
            </div>
          )}

          {/* Input area */}
          <div className="border-t border-[var(--nash-border)] p-4 bg-[var(--nash-surface)]">
            <form onSubmit={handleSubmit} className="flex gap-3">
              <input
                type="text"
                value={textInput}
                onChange={(e) => setTextInput(e.target.value)}
                placeholder="Escribe tu mensaje..."
                disabled={sending || isRecording}
                className="flex-1 bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg px-4 py-2 text-sm disabled:opacity-50"
              />

              <button
                type="button"
                onClick={isRecording ? stopRecording : startRecording}
                disabled={sending}
                className={`w-12 h-10 rounded-lg flex items-center justify-center cursor-pointer transition-colors ${
                  isRecording
                    ? 'bg-red-500 text-white animate-pulse'
                    : 'bg-[var(--nash-teal)] text-white hover:opacity-90'
                } disabled:opacity-50`}
                title={isRecording ? 'Detener grabacion' : 'Grabar voz'}
              >
                {isRecording ? (
                  <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                    <rect x="6" y="6" width="12" height="12" rx="2" />
                  </svg>
                ) : (
                  <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z" />
                    <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
                  </svg>
                )}
              </button>

              <button
                type="submit"
                disabled={sending || isRecording || !textInput.trim()}
                className="px-4 py-2 bg-[var(--nash-accent)] text-white rounded-lg text-sm font-medium hover:opacity-90 disabled:opacity-50 cursor-pointer disabled:cursor-not-allowed"
              >
                Enviar
              </button>
            </form>
          </div>
        </div>

        {/* Right side: graph top + details bottom */}
        <div className="w-[40%] min-w-[360px] max-w-[560px] border-l border-[var(--nash-border)] bg-[var(--nash-surface)] flex flex-col">
          <div className="h-[52%] min-h-[260px] border-b border-[var(--nash-border)] flex flex-col">
            <div className="p-3 border-b border-[var(--nash-border)] flex items-center justify-between gap-2">
              <div>
                <h3 className="font-semibold text-sm">Mapa de Metas</h3>
                <p className="text-xs text-[var(--nash-text-muted)]">
                  {savedGoals.length} guardadas · {pendingGoals.length} pendientes
                </p>
              </div>
              <button
                type="button"
                onClick={loadGraph}
                disabled={graphLoading}
                className="text-xs text-[var(--nash-accent)] hover:underline disabled:opacity-50 cursor-pointer"
              >
                {graphLoading ? 'Actualizando...' : 'Actualizar'}
              </button>
            </div>

            <div ref={graphContainerRef} className="flex-1 relative bg-[var(--nash-bg)]">
              {combinedNodes.length === 0 ? (
                <div className="absolute inset-0 flex items-center justify-center text-xs text-[var(--nash-text-muted)] px-4 text-center">
                  Las metas apareceran aqui en forma de nodos.
                </div>
              ) : (
                <svg width="100%" height="100%" viewBox={`0 0 ${graphSize.width} ${graphSize.height}`}>
                  {combinedEdges.map((edge) => {
                    const source = nodeStateRef.current[edge.sourceNodeId];
                    const target = nodeStateRef.current[edge.targetNodeId];
                    if (!source || !target) return null;

                    const midX = (source.x + target.x) / 2;
                    const midY = (source.y + target.y) / 2;
                    const edgeSelected = edge.id === selectedEdgeId;
                    const color = getEdgeColor(edge, edgeSelected);
                    const categoryLabel = EDGE_CATEGORY_LABELS[getEdgeCategory(edge)];

                    return (
                      <g
                        key={edge.id}
                        className="cursor-pointer"
                        onClick={(event) => {
                          event.stopPropagation();
                          setSelectedEdgeId(edge.id);
                          setSelectedNodeId(null);
                        }}
                      >
                        <line
                          x1={source.x}
                          y1={source.y}
                          x2={target.x}
                          y2={target.y}
                          stroke={color}
                          strokeWidth={edgeSelected ? 3 : edge.kind === 'parent' ? 2.2 : 1.8}
                          strokeDasharray={edge.kind === 'parent' ? '0' : '5 4'}
                          opacity={edgeSelected ? 1 : 0.86}
                          style={{ pointerEvents: 'stroke' }}
                        />
                        <text
                          x={midX}
                          y={midY - 4}
                          fontSize="9"
                          fill={color}
                          textAnchor="middle"
                          className="pointer-events-none"
                        >
                          {categoryLabel}
                        </text>
                      </g>
                    );
                  })}

                  {renderedNodes.map((node) => {
                    const selected = node.id === selectedNodeId;
                    const nodeType = node.kind === 'saved'
                      ? (node.goal?.node_type || 'goal')
                      : (node.pendingGoal?.node_type || 'goal');
                    const childrenCount = hierarchyLayout.childrenCountByNodeId[node.id] || 0;
                    const color = getNodeColor(node, selected, childrenCount);
                    const radius = node.kind === 'pending' ? 16 : 19;

                    return (
                      <g
                        key={node.id}
                        transform={`translate(${node.x}, ${node.y})`}
                        onClick={() => {
                          setSelectedNodeId(node.id);
                          setSelectedEdgeId(null);
                        }}
                        className="cursor-pointer"
                      >
                        <circle
                          r={radius}
                          fill={color}
                          fillOpacity={node.kind === 'pending' ? 0.78 : 0.9}
                          stroke={selected ? '#1E293B' : '#FFFFFF'}
                          strokeWidth={selected ? 2.8 : 1.8}
                        />
                        <text
                          y={4}
                          textAnchor="middle"
                          fontSize="12"
                          fill="white"
                          className="pointer-events-none"
                        >
                          {NODE_TYPE_ICONS[nodeType]}
                        </text>
                        <text
                          y={radius + 14}
                          textAnchor="middle"
                          fontSize="10"
                          fill="var(--nash-text)"
                          className="pointer-events-none"
                        >
                          {node.label.length > 18 ? `${node.label.slice(0, 16)}...` : node.label}
                        </text>
                      </g>
                    );
                  })}
                </svg>
              )}
            </div>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {pendingGoals.length > 1 && (
              <div className="border border-[var(--nash-border)] rounded-lg p-3 bg-[var(--nash-bg)] space-y-2">
                <p className="text-xs font-medium text-[var(--nash-text-muted)]">Guardado rápido por lote</p>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => handleSaveBatchGoals(2)}
                    disabled={savingBatchGoals || pendingGoals.length < 2}
                    className="text-xs px-3 py-1.5 bg-[var(--nash-success)] text-white rounded disabled:opacity-50 cursor-pointer disabled:cursor-not-allowed"
                  >
                    {savingBatchGoals ? 'Guardando...' : 'Guardar 2 metas'}
                  </button>
                  <button
                    type="button"
                    onClick={() => handleSaveBatchGoals(3)}
                    disabled={savingBatchGoals || pendingGoals.length < 3}
                    className="text-xs px-3 py-1.5 bg-[var(--nash-success)] text-white rounded disabled:opacity-50 cursor-pointer disabled:cursor-not-allowed"
                  >
                    {savingBatchGoals ? 'Guardando...' : 'Guardar 3 metas'}
                  </button>
                  <button
                    type="button"
                    onClick={() => handleSaveBatchGoals(pendingGoals.length)}
                    disabled={savingBatchGoals}
                    className="text-xs px-3 py-1.5 border border-[var(--nash-success)] text-[var(--nash-success)] rounded disabled:opacity-50 cursor-pointer disabled:cursor-not-allowed"
                  >
                    Guardar todas ({pendingGoals.length})
                  </button>
                </div>
              </div>
            )}

            {pendingRelations.length > 0 && (
              <div className="border border-[var(--nash-border)] rounded-lg p-3 bg-[var(--nash-bg)]">
                <p className="text-xs font-medium text-[var(--nash-text-muted)]">
                  {pendingRelations.length} relaciones pendientes detectadas
                </p>
              </div>
            )}

            {selectedEdge && (
              <div className="space-y-2 border rounded-lg p-3 bg-[var(--nash-bg)]" style={{ borderColor: getEdgeColor(selectedEdge, true) }}>
                <p className="text-[11px] uppercase tracking-wide font-semibold" style={{ color: getEdgeColor(selectedEdge, true) }}>
                  Enlace seleccionado · {EDGE_CATEGORY_LABELS[getEdgeCategory(selectedEdge)]}
                </p>
                {selectedPendingRelation ? (
                  <div className="space-y-2">
                    <input
                      value={selectedPendingRelation.source_title}
                      onChange={(e) => handlePendingRelationFieldChange(selectedPendingRelation.local_id, 'source_title', e.target.value)}
                      placeholder="Nodo origen"
                      className="w-full bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs"
                    />
                    <input
                      value={selectedPendingRelation.target_title}
                      onChange={(e) => handlePendingRelationFieldChange(selectedPendingRelation.local_id, 'target_title', e.target.value)}
                      placeholder="Nodo destino"
                      className="w-full bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs"
                    />
                    <select
                      value={selectedPendingRelation.relation_type}
                      onChange={(e) => handlePendingRelationFieldChange(selectedPendingRelation.local_id, 'relation_type', e.target.value)}
                      className="w-full bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs"
                    >
                      {RELATION_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>{option.label}</option>
                      ))}
                    </select>
                    <textarea
                      value={selectedPendingRelation.note || ''}
                      onChange={(e) => handlePendingRelationFieldChange(selectedPendingRelation.local_id, 'note', e.target.value)}
                      placeholder="Nota opcional"
                      rows={2}
                      className="w-full bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs"
                    />
                    <button
                      type="button"
                      onClick={() => handleDismissPendingRelation(selectedPendingRelation.local_id)}
                      className="text-xs text-[var(--nash-error)] hover:underline cursor-pointer"
                    >
                      Descartar relación pendiente
                    </button>
                  </div>
                ) : (
                  <>
                    <p className="text-xs text-[var(--nash-text)]">
                      {savedGoalById.get(selectedEdge.source_goal_id)?.title || `Meta ${selectedEdge.source_goal_id}`} → {savedGoalById.get(selectedEdge.target_goal_id)?.title || `Meta ${selectedEdge.target_goal_id}`}
                    </p>
                    <p className="text-xs text-[var(--nash-text-muted)]">
                      Tipo: {RELATION_LABELS[selectedEdge.relation_type] || selectedEdge.relation_type}
                    </p>
                    {selectedEdge.note && (
                      <p className="text-xs text-[var(--nash-text-muted)]">{selectedEdge.note}</p>
                    )}
                  </>
                )}
                {selectedEdge.kind === 'relation' && selectedEdge.relation_id && (
                  <button
                    type="button"
                    onClick={() => handleDeleteRelation(selectedEdge.relation_id!)}
                    className="text-xs text-[var(--nash-error)] hover:underline cursor-pointer"
                  >
                    Eliminar enlace
                  </button>
                )}
              </div>
            )}

            {!selectedSavedGoal && !selectedPendingGoal && !selectedEdge && (
              <div className="text-xs text-[var(--nash-text-muted)]">
                Haz click en un nodo o un enlace del grafo para ver su detalle y editar.
              </div>
            )}

            {selectedPendingGoal && (
              <div className="space-y-3">
                <div>
                  <p className="text-[11px] uppercase tracking-wide text-[var(--nash-warning)] font-semibold">Nodo pendiente</p>
                  <h4 className="font-semibold text-[var(--nash-text)] mt-1">
                    {NODE_TYPE_ICONS[selectedPendingGoal.node_type || 'goal']} {selectedPendingGoal.title}
                  </h4>
                </div>

                <div className="space-y-2 border border-[var(--nash-border)] rounded-lg p-3 bg-[var(--nash-bg)]">
                  <select
                    value={selectedPendingGoal.node_type || 'goal'}
                    onChange={(e) => handlePendingGoalFieldChange(selectedPendingGoal.local_id, 'node_type', e.target.value as GoalNodeType)}
                    className="w-full bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs"
                  >
                    {Object.entries(NODE_TYPE_LABELS).map(([key, label]) => (
                      <option key={key} value={key}>{label}</option>
                    ))}
                  </select>
                  <input
                    value={selectedPendingGoal.title || ''}
                    onChange={(e) => handlePendingGoalFieldChange(selectedPendingGoal.local_id, 'title', e.target.value)}
                    placeholder="Título"
                    className="w-full bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs"
                  />
                  <textarea
                    value={selectedPendingGoal.description || ''}
                    onChange={(e) => handlePendingGoalFieldChange(selectedPendingGoal.local_id, 'description', e.target.value)}
                    placeholder="Descripción"
                    rows={2}
                    className="w-full bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs"
                  />
                  <div className="grid grid-cols-2 gap-2">
                    <input
                      value={selectedPendingGoal.domain_code || ''}
                      onChange={(e) => handlePendingGoalFieldChange(selectedPendingGoal.local_id, 'domain_code', e.target.value)}
                      placeholder="Dominio principal"
                      className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs"
                    />
                    <input
                      value={(selectedPendingGoal.domain_tags || []).join(' | ')}
                      onChange={(e) => handlePendingGoalFieldChange(selectedPendingGoal.local_id, 'domain_tags', parseDomainTagsInput(e.target.value))}
                      placeholder="Tags dominio (|)"
                      className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    {nodeSupportsHorizon(selectedPendingGoal.node_type || 'goal') ? (
                      <select
                        value={selectedPendingGoal.horizon || ''}
                        onChange={(e) => handlePendingGoalFieldChange(selectedPendingGoal.local_id, 'horizon', e.target.value)}
                        className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs"
                      >
                        {!nodeRequiresHorizon(selectedPendingGoal.node_type || 'goal') && <option value="">Sin horizonte</option>}
                        {Object.entries(HORIZON_LABELS).map(([key, label]) => (
                          <option key={key} value={key}>{label}</option>
                        ))}
                      </select>
                    ) : (
                      <div className="bg-[var(--nash-surface)] border border-dashed border-[var(--nash-border)] rounded px-2 py-1.5 text-xs text-[var(--nash-text-muted)]">
                        Sin horizonte
                      </div>
                    )}
                    <input
                      type="date"
                      value={selectedPendingGoal.start_date || ''}
                      onChange={(e) => handlePendingGoalFieldChange(selectedPendingGoal.local_id, 'start_date', e.target.value || null)}
                      className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <input
                      type="date"
                      value={selectedPendingGoal.target_date || ''}
                      onChange={(e) => handlePendingGoalFieldChange(selectedPendingGoal.local_id, 'target_date', e.target.value || null)}
                      className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs"
                    />
                    <div />
                  </div>
                  {nodeSupportsCadence(selectedPendingGoal.node_type || 'goal') && (
                    <input
                      value={selectedPendingGoal.cadence_text || ''}
                      onChange={(e) => handlePendingGoalFieldChange(selectedPendingGoal.local_id, 'cadence_text', e.target.value)}
                      placeholder="Cadencia (daily, weekly, 3x/semana...)"
                      className="w-full bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs"
                    />
                  )}
                  {nodeSupportsActionCosts(selectedPendingGoal.node_type || 'goal') && (
                    <div className="grid grid-cols-3 gap-2">
                      <input
                        value={selectedPendingGoal.time_cost_min ?? ''}
                        onChange={(e) => handlePendingGoalFieldChange(selectedPendingGoal.local_id, 'time_cost_min', e.target.value ? Number(e.target.value) : null)}
                        placeholder="Tiempo (min)"
                        className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs"
                      />
                      <input
                        value={selectedPendingGoal.energy_cost ?? ''}
                        onChange={(e) => handlePendingGoalFieldChange(selectedPendingGoal.local_id, 'energy_cost', e.target.value ? Number(e.target.value) : null)}
                        placeholder="Energía 1-5"
                        className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs"
                      />
                      <input
                        value={selectedPendingGoal.attention_cost ?? ''}
                        onChange={(e) => handlePendingGoalFieldChange(selectedPendingGoal.local_id, 'attention_cost', e.target.value ? Number(e.target.value) : null)}
                        placeholder="Atención 1-5"
                        className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs"
                      />
                    </div>
                  )}
                  <div className="grid grid-cols-3 gap-2">
                    <input
                      value={selectedPendingGoal.importance ?? ''}
                      onChange={(e) => handlePendingGoalFieldChange(selectedPendingGoal.local_id, 'importance', e.target.value ? Number(e.target.value) : null)}
                      placeholder="Importancia"
                      className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs"
                    />
                    <input
                      value={selectedPendingGoal.difficulty ?? ''}
                      onChange={(e) => handlePendingGoalFieldChange(selectedPendingGoal.local_id, 'difficulty', e.target.value ? Number(e.target.value) : null)}
                      placeholder="Dificultad"
                      className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs"
                    />
                    <input
                      value={selectedPendingGoal.commitment ?? ''}
                      onChange={(e) => handlePendingGoalFieldChange(selectedPendingGoal.local_id, 'commitment', e.target.value ? Number(e.target.value) : null)}
                      placeholder="Compromiso"
                      className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs"
                    />
                  </div>
                  <input
                    value={selectedPendingGoal.motivation_type || ''}
                    onChange={(e) => handlePendingGoalFieldChange(selectedPendingGoal.local_id, 'motivation_type', e.target.value)}
                    placeholder="Motivación"
                    className="w-full bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs"
                  />
                  <textarea
                    value={selectedPendingGoal.why_matters || ''}
                    onChange={(e) => handlePendingGoalFieldChange(selectedPendingGoal.local_id, 'why_matters', e.target.value)}
                    placeholder="Por qué importa"
                    rows={2}
                    className="w-full bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs"
                  />
                  <textarea
                    value={selectedPendingGoal.nash_opinion || ''}
                    onChange={(e) => handlePendingGoalFieldChange(selectedPendingGoal.local_id, 'nash_opinion', e.target.value)}
                    placeholder="Opinión de Nash"
                    rows={2}
                    className="w-full bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs"
                  />
                </div>

                <div className="flex gap-2">
                  <button
                    onClick={() => handleSaveGoal(selectedPendingGoal.local_id)}
                    disabled={savingGoalId === selectedPendingGoal.local_id}
                    className="flex-1 text-xs py-2 bg-[var(--nash-success)] text-white rounded hover:opacity-90 disabled:opacity-50 cursor-pointer disabled:cursor-not-allowed"
                  >
                    {savingGoalId === selectedPendingGoal.local_id ? 'Guardando...' : 'Guardar nodo'}
                  </button>
                  <button
                    onClick={() => handleDismissGoal(selectedPendingGoal.local_id)}
                    disabled={savingGoalId === selectedPendingGoal.local_id}
                    className="text-xs py-2 px-3 text-[var(--nash-text-muted)] hover:text-[var(--nash-error)] cursor-pointer"
                  >
                    Descartar
                  </button>
                </div>
              </div>
            )}

            {selectedSavedGoal && (
              <div className="space-y-4">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="text-[11px] uppercase tracking-wide text-[var(--nash-accent)] font-semibold">Nodo guardado</p>
                    <h4 className="font-semibold text-[var(--nash-text)] mt-1">
                      {NODE_TYPE_ICONS[selectedSavedGoal.node_type]} {selectedSavedGoal.title}
                    </h4>
                    <p className="text-xs text-[var(--nash-text-muted)] mt-1">
                      Estado: {STATUS_LABELS[selectedSavedGoal.status]} · Progreso: {selectedSavedGoal.progress_pct}%
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => setEditingGoal((prev) => !prev)}
                      className="text-xs px-2 py-1 border border-[var(--nash-border)] rounded hover:bg-[var(--nash-bg)] cursor-pointer"
                    >
                      {editingGoal ? 'Cerrar edición' : 'Editar'}
                    </button>
                    <button
                      type="button"
                      onClick={handleDeleteSavedGoal}
                      className="text-xs px-2 py-1 border border-[var(--nash-error)] text-[var(--nash-error)] rounded hover:bg-red-50 cursor-pointer"
                    >
                      Eliminar nodo
                    </button>
                  </div>
                </div>

                {!editingGoal && (
                  <div className="text-xs grid grid-cols-1 gap-2">
                    <p><span className="font-medium">Descripción:</span> {selectedSavedGoal.description || '—'}</p>
                    <p><span className="font-medium">Por qué importa:</span> {selectedSavedGoal.why_matters || '—'}</p>
                    <p><span className="font-medium">Tipo:</span> {NODE_TYPE_LABELS[selectedSavedGoal.node_type]}</p>
                    <p><span className="font-medium">Dominio principal:</span> {selectedSavedGoal.domain_code || '—'}</p>
                    <p><span className="font-medium">Tags:</span> {selectedSavedGoal.domain_tags?.join(' | ') || '—'}</p>
                    {nodeSupportsHorizon(selectedSavedGoal.node_type) && (
                      <p><span className="font-medium">Horizonte:</span> {selectedSavedGoal.horizon ? (HORIZON_LABELS[selectedSavedGoal.horizon] || selectedSavedGoal.horizon) : '—'}</p>
                    )}
                    <p><span className="font-medium">Fecha de inicio:</span> {selectedSavedGoal.start_date || '—'}</p>
                    <p><span className="font-medium">Fecha objetivo:</span> {selectedSavedGoal.target_date || '—'}</p>
                    {nodeSupportsCadence(selectedSavedGoal.node_type) && (
                      <p><span className="font-medium">Cadencia:</span> {selectedSavedGoal.cadence_text || '—'}</p>
                    )}
                    {nodeSupportsActionCosts(selectedSavedGoal.node_type) && (
                      <p><span className="font-medium">Costos:</span> Tiempo {selectedSavedGoal.time_cost_min ?? '—'} min · Energía {selectedSavedGoal.energy_cost ?? '—'}/5 · Atención {selectedSavedGoal.attention_cost ?? '—'}/5</p>
                    )}
                    <p><span className="font-medium">Motivación:</span> {selectedSavedGoal.motivation_type ? (MOTIVATION_LABELS[selectedSavedGoal.motivation_type] || selectedSavedGoal.motivation_type) : '—'}</p>
                    <p><span className="font-medium">Importancia:</span> {selectedSavedGoal.importance ?? '—'}</p>
                    <p><span className="font-medium">Dificultad:</span> {selectedSavedGoal.difficulty ?? '—'}</p>
                    <p><span className="font-medium">Compromiso:</span> {selectedSavedGoal.commitment ?? '—'}</p>
                    <p><span className="font-medium">Especificidad:</span> {selectedSavedGoal.specificity ?? '—'}</p>
                    <p><span className="font-medium">Locus de control:</span> {selectedSavedGoal.locus_of_control || '—'}</p>
                    <p><span className="font-medium">Coherencia:</span> {selectedSavedGoal.coherence_score ?? '—'}</p>
                    <p><span className="font-medium">Prioridad:</span> {selectedSavedGoal.priority_rank ?? '—'}</p>
                    <p><span className="font-medium">Nash:</span> {selectedSavedGoal.nash_opinion || '—'}</p>
                    <p><span className="font-medium">Conflictos JSON:</span> {selectedSavedGoal.conflicts_json || '[]'}</p>
                    <p><span className="font-medium">Sinergias JSON:</span> {selectedSavedGoal.synergies_json || '[]'}</p>
                  </div>
                )}

                {editingGoal && goalEditDraft && (
                  <div className="space-y-2 border border-[var(--nash-border)] rounded-lg p-3 bg-[var(--nash-bg)]">
                    <select value={goalEditDraft.node_type} onChange={(e) => setGoalEditDraft({ ...goalEditDraft, node_type: e.target.value as GoalNodeType })} className="w-full bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs">
                      {Object.entries(NODE_TYPE_LABELS).map(([key, label]) => (
                        <option key={key} value={key}>{label}</option>
                      ))}
                    </select>
                    <input value={goalEditDraft.title} onChange={(e) => setGoalEditDraft({ ...goalEditDraft, title: e.target.value })} placeholder="Título" className="w-full bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs" />
                    <textarea value={goalEditDraft.description} onChange={(e) => setGoalEditDraft({ ...goalEditDraft, description: e.target.value })} placeholder="Descripción" rows={2} className="w-full bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs" />
                    <textarea value={goalEditDraft.why_matters} onChange={(e) => setGoalEditDraft({ ...goalEditDraft, why_matters: e.target.value })} placeholder="Por qué importa" rows={2} className="w-full bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs" />
                    <input value={goalEditDraft.domain_tags_input} onChange={(e) => setGoalEditDraft({ ...goalEditDraft, domain_tags_input: e.target.value })} placeholder="Tags de dominio (career|music|ai)" className="w-full bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs" />
                    <div className="grid grid-cols-2 gap-2">
                      <select value={goalEditDraft.domain_code} onChange={(e) => setGoalEditDraft({ ...goalEditDraft, domain_code: e.target.value })} className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs">
                        <option value="">Sin dominio principal</option>
                        {domains.map((domain) => (
                          <option key={domain.code} value={domain.code}>{domain.icon} {domain.name_es}</option>
                        ))}
                      </select>
                      {nodeSupportsHorizon(goalEditDraft.node_type) ? (
                        <select value={goalEditDraft.horizon} onChange={(e) => setGoalEditDraft({ ...goalEditDraft, horizon: e.target.value })} className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs">
                          {!nodeRequiresHorizon(goalEditDraft.node_type) && <option value="">Sin horizonte</option>}
                          {Object.entries(HORIZON_LABELS).map(([key, label]) => (
                            <option key={key} value={key}>{label}</option>
                          ))}
                        </select>
                      ) : (
                        <div className="bg-[var(--nash-surface)] border border-dashed border-[var(--nash-border)] rounded px-2 py-1.5 text-xs text-[var(--nash-text-muted)]">
                          Sin horizonte
                        </div>
                      )}
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <input type="date" value={goalEditDraft.start_date} onChange={(e) => setGoalEditDraft({ ...goalEditDraft, start_date: e.target.value })} className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs" />
                      <input type="date" value={goalEditDraft.target_date} onChange={(e) => setGoalEditDraft({ ...goalEditDraft, target_date: e.target.value })} className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs" />
                    </div>
                    {nodeSupportsCadence(goalEditDraft.node_type) && (
                      <input value={goalEditDraft.cadence_text} onChange={(e) => setGoalEditDraft({ ...goalEditDraft, cadence_text: e.target.value })} placeholder="Cadencia (daily, weekly, 3x/semana...)" className="w-full bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs" />
                    )}
                    {nodeSupportsActionCosts(goalEditDraft.node_type) && (
                      <div className="grid grid-cols-3 gap-2">
                        <input value={goalEditDraft.time_cost_min} onChange={(e) => setGoalEditDraft({ ...goalEditDraft, time_cost_min: e.target.value })} placeholder="Tiempo (min)" className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs" />
                        <input value={goalEditDraft.energy_cost} onChange={(e) => setGoalEditDraft({ ...goalEditDraft, energy_cost: e.target.value })} placeholder="Energía 1-5" className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs" />
                        <input value={goalEditDraft.attention_cost} onChange={(e) => setGoalEditDraft({ ...goalEditDraft, attention_cost: e.target.value })} placeholder="Atención 1-5" className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs" />
                      </div>
                    )}
                    <div className="grid grid-cols-2 gap-2">
                      <select value={goalEditDraft.status} onChange={(e) => setGoalEditDraft({ ...goalEditDraft, status: e.target.value as Goal['status'] })} className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs">
                        {Object.entries(STATUS_LABELS).map(([key, label]) => (
                          <option key={key} value={key}>{label}</option>
                        ))}
                      </select>
                      <div />
                    </div>
                    <div>
                      <label className="text-xs text-[var(--nash-text-muted)]">Progreso: {goalEditDraft.progress_pct}%</label>
                      <input type="range" min={0} max={100} value={goalEditDraft.progress_pct} onChange={(e) => setGoalEditDraft({ ...goalEditDraft, progress_pct: Number(e.target.value) })} className="w-full" />
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <select value={goalEditDraft.motivation_type} onChange={(e) => setGoalEditDraft({ ...goalEditDraft, motivation_type: e.target.value })} className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs">
                        <option value="">Sin motivación</option>
                        {Object.entries(MOTIVATION_LABELS).map(([key, label]) => (
                          <option key={key} value={key}>{label}</option>
                        ))}
                      </select>
                      <select value={goalEditDraft.locus_of_control} onChange={(e) => setGoalEditDraft({ ...goalEditDraft, locus_of_control: e.target.value })} className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs">
                        <option value="">Locus no definido</option>
                        <option value="internal">Interno</option>
                        <option value="external">Externo</option>
                        <option value="mixed">Mixto</option>
                      </select>
                    </div>
                    <div className="grid grid-cols-3 gap-2">
                      <input value={goalEditDraft.importance} onChange={(e) => setGoalEditDraft({ ...goalEditDraft, importance: e.target.value })} placeholder="Importancia" className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs" />
                      <input value={goalEditDraft.difficulty} onChange={(e) => setGoalEditDraft({ ...goalEditDraft, difficulty: e.target.value })} placeholder="Dificultad" className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs" />
                      <input value={goalEditDraft.commitment} onChange={(e) => setGoalEditDraft({ ...goalEditDraft, commitment: e.target.value })} placeholder="Compromiso" className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs" />
                    </div>
                    <div className="grid grid-cols-3 gap-2">
                      <input value={goalEditDraft.specificity} onChange={(e) => setGoalEditDraft({ ...goalEditDraft, specificity: e.target.value })} placeholder="Especificidad" className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs" />
                      <input value={goalEditDraft.coherence_score} onChange={(e) => setGoalEditDraft({ ...goalEditDraft, coherence_score: e.target.value })} placeholder="Coherencia" className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs" />
                      <input value={goalEditDraft.priority_rank} onChange={(e) => setGoalEditDraft({ ...goalEditDraft, priority_rank: e.target.value })} placeholder="Prioridad" className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs" />
                    </div>
                    <textarea value={goalEditDraft.nash_opinion} onChange={(e) => setGoalEditDraft({ ...goalEditDraft, nash_opinion: e.target.value })} placeholder="Opinión de Nash" rows={2} className="w-full bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs" />
                    <textarea value={goalEditDraft.conflicts_json} onChange={(e) => setGoalEditDraft({ ...goalEditDraft, conflicts_json: e.target.value })} placeholder='Conflictos JSON (ej: [{"goal_id":2,"note":"..."}])' rows={2} className="w-full bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs font-mono" />
                    <textarea value={goalEditDraft.synergies_json} onChange={(e) => setGoalEditDraft({ ...goalEditDraft, synergies_json: e.target.value })} placeholder='Sinergias JSON (ej: [{"goal_id":3,"note":"..."}])' rows={2} className="w-full bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs font-mono" />
                    <div className="flex gap-2">
                      <button type="button" onClick={handleSaveGoalEdits} disabled={savingGoalEdits} className="flex-1 text-xs py-2 bg-[var(--nash-success)] text-white rounded hover:opacity-90 disabled:opacity-50 cursor-pointer disabled:cursor-not-allowed">
                        {savingGoalEdits ? 'Guardando...' : 'Guardar cambios'}
                      </button>
                      <button type="button" onClick={() => setEditingGoal(false)} className="text-xs py-2 px-3 text-[var(--nash-text-muted)] border border-[var(--nash-border)] rounded hover:bg-[var(--nash-surface)] cursor-pointer">
                        Cancelar
                      </button>
                    </div>
                  </div>
                )}

                <div className="space-y-1">
                  <label className="text-xs font-medium text-[var(--nash-text-muted)]">Nodo padre (jerarquía)</label>
                  <select
                    value={selectedSavedGoal.parent_goal_id ?? ''}
                    onChange={(e) => handleUpdateParent(e.target.value)}
                    disabled={updatingParent}
                    className="w-full bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                  >
                    <option value="">Sin meta padre</option>
                    {savedGoals
                      .filter((goal) => goal.id !== selectedSavedGoal.id && canParentNode(goal.node_type, selectedSavedGoal.node_type))
                      .map((goal) => (
                        <option key={goal.id} value={goal.id}>
                          {NODE_TYPE_ICONS[goal.node_type]} {goal.title}
                        </option>
                      ))}
                  </select>
                </div>

                <div className="space-y-2 border border-[var(--nash-border)] rounded-lg p-3 bg-[var(--nash-bg)]">
                  <p className="text-xs font-medium text-[var(--nash-text-muted)]">Crear relación</p>

                  <select
                    value={relationTargetId}
                    onChange={(e) => setRelationTargetId(e.target.value)}
                    className="w-full bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                  >
                    <option value="">Selecciona meta destino</option>
                    {savedGoals
                      .filter((goal) => goal.id !== selectedSavedGoal.id)
                      .map((goal) => (
                        <option key={goal.id} value={goal.id}>
                          {NODE_TYPE_ICONS[goal.node_type]} {goal.title}
                        </option>
                      ))}
                  </select>

                  <select
                    value={relationType}
                    onChange={(e) => setRelationType(e.target.value as (typeof RELATION_OPTIONS)[number]['value'])}
                    className="w-full bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                  >
                    {RELATION_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>{option.label}</option>
                    ))}
                  </select>

                  <input
                    value={relationNote}
                    onChange={(e) => setRelationNote(e.target.value)}
                    placeholder="Nota opcional sobre esta relación"
                    className="w-full bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                  />

                  <button
                    type="button"
                    onClick={handleCreateRelation}
                    disabled={!relationTargetId || savingRelation}
                    className="w-full text-xs py-2 bg-[var(--nash-accent)] text-white rounded hover:opacity-90 disabled:opacity-50 cursor-pointer disabled:cursor-not-allowed"
                  >
                    {savingRelation ? 'Creando...' : 'Crear relación'}
                  </button>
                </div>

                <div className="space-y-2">
                  <p className="text-xs font-medium text-[var(--nash-text-muted)]">Relaciones de este nodo</p>

                  {selectedNodeRelations.length === 0 && (
                    <p className="text-xs text-[var(--nash-text-muted)]">Aun no tiene relaciones.</p>
                  )}

                  {selectedNodeRelations.map((edge) => {
                    const outgoing = edge.source_goal_id === selectedSavedGoal.id;
                    const otherGoalId = outgoing ? edge.target_goal_id : edge.source_goal_id;
                    const otherGoal = savedGoalById.get(otherGoalId);
                    const otherLabel = otherGoal?.title || `Meta ${otherGoalId}`;
                    const edgeColor = getEdgeColor(edge, selectedEdgeId === edge.id);

                    return (
                      <div
                        key={edge.id}
                        className="text-xs border rounded-lg p-2 bg-[var(--nash-bg)] cursor-pointer"
                        style={{ borderColor: edgeColor }}
                        onClick={() => {
                          setSelectedEdgeId(edge.id);
                          setSelectedNodeId(null);
                        }}
                      >
                        <p className="font-medium text-[var(--nash-text)]">
                          {outgoing ? '→' : '←'} {RELATION_LABELS[edge.relation_type] || edge.relation_type} {otherLabel}
                        </p>
                        <p className="mt-1" style={{ color: edgeColor }}>
                          Categoría: {EDGE_CATEGORY_LABELS[getEdgeCategory(edge)]}
                        </p>
                        {edge.note && (
                          <p className="text-[var(--nash-text-muted)] mt-1">{edge.note}</p>
                        )}
                        {edge.kind === 'relation' && edge.relation_id && (
                          <button
                            type="button"
                            onClick={(event) => {
                              event.stopPropagation();
                              handleDeleteRelation(edge.relation_id!);
                            }}
                            className="mt-1 text-[var(--nash-error)] hover:underline cursor-pointer"
                          >
                            Eliminar relación
                          </button>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {session && (
              <div className="pt-3 border-t border-[var(--nash-border)] text-xs text-[var(--nash-text-muted)]">
                <p>Mensajes: {session.messages.length}</p>
                <p>Metas confirmadas: {session.goals_confirmed || 0}</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
