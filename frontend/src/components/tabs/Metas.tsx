import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  fetchLifeDomains,
  fetchGoals,
  fetchGoalsSummary,
  fetchGoalsGraph,
  createGoalRelation,
  deleteGoalRelation,
  rateDomains,
  createGoal,
  updateGoal,
  deleteGoal,
  type LifeDomain,
  type Goal,
  type GoalGraphEdge,
  type GoalNodeType,
  type GoalsSummary,
} from '../../api';
import { GoalDiscovery } from '../GoalDiscovery';

const HORIZON_LABELS: Record<string, string> = {
  life: 'Vida',
  annual: 'Anual',
  quarterly: 'Trimestral',
  monthly: 'Mensual',
  weekly: 'Semanal',
};

const STATUS_LABELS: Record<string, string> = {
  active: 'Activa',
  completed: 'Completada',
  abandoned: 'Abandonada',
  paused: 'Pausada',
};

const MOTIVATION_LABELS: Record<string, { label: string; color: string }> = {
  external: { label: 'Externa', color: 'var(--nash-text-muted)' },
  introjected: { label: 'Introyectada', color: 'var(--nash-warning)' },
  identified: { label: 'Identificada', color: 'var(--nash-teal)' },
  intrinsic: { label: 'Intrinseca', color: 'var(--nash-success)' },
};

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

function getEdgeCategory(edge: GoalGraphEdge): 'dependence' | 'affinity' | 'conflict' {
  if (edge.relation_type === 'parent_child' || edge.relation_type === 'depends_on' || edge.relation_type === 'requires') return 'dependence';
  if (edge.relation_type === 'conflicts_with' || edge.relation_type === 'blocks' || edge.relation_type === 'costs') return 'conflict';
  return 'affinity';
}

function getColorByChildCount(childrenCount: number): string {
  if (childrenCount >= 5) return '#16A34A';
  if (childrenCount >= 3) return '#0EA5E9';
  if (childrenCount >= 1) return '#14B8A6';
  return '#6366F1';
}

function getDepthTargetY(depth: number, maxDepth: number, height: number): number {
  const top = 38;
  const bottom = Math.max(top + 1, height - 32);
  if (maxDepth <= 0) return (top + bottom) / 2;
  return top + (depth / maxDepth) * (bottom - top);
}

function parseDomainTagsInput(raw: string): string[] {
  return raw
    .replace(/,/g, '|')
    .split('|')
    .map((tag) => tag.trim().toLowerCase())
    .filter(Boolean);
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

function getGoalTypeBadge(goal: Goal): string {
  if (goal.node_type === 'goal') {
    if (goal.parent_goal_id) return 'Sub-goal';
    return 'Goal';
  }
  return NODE_TYPE_LABELS[goal.node_type];
}

export function Metas() {
  const [domains, setDomains] = useState<LifeDomain[]>([]);
  const [goals, setGoals] = useState<Goal[]>([]);
  const [summary, setSummary] = useState<GoalsSummary | null>(null);
  const [graphNodes, setGraphNodes] = useState<Goal[]>([]);
  const [graphEdges, setGraphEdges] = useState<GoalGraphEdge[]>([]);
  const [loading, setLoading] = useState(true);

  // Filters
  const [statusFilter, setStatusFilter] = useState<string>('active');
  const [horizonFilter, setHorizonFilter] = useState<string>('');
  const [domainFilter, setDomainFilter] = useState<string>('');
  const [nodeTypeFilter, setNodeTypeFilter] = useState<string>('');

  // UI state
  const [showRatingModal, setShowRatingModal] = useState(false);
  const [showGoalModal, setShowGoalModal] = useState(false);
  const [showDiscovery, setShowDiscovery] = useState(false);
  const [ratingValues, setRatingValues] = useState<Record<string, number>>({});
  const [savingRatings, setSavingRatings] = useState(false);

  // New goal form
  const [newGoal, setNewGoal] = useState({
    node_type: 'goal' as GoalNodeType,
    title: '',
    domain_code: '',
    description: '',
    why_matters: '',
    horizon: 'quarterly',
    start_date: '',
    target_date: '',
    cadence_text: '',
    time_cost_min: '',
    energy_cost: '',
    attention_cost: '',
    motivation_type: '',
  });
  const [savingGoal, setSavingGoal] = useState(false);
  const [selectedGraphGoalId, setSelectedGraphGoalId] = useState<number | null>(null);
  const [editingGraphGoal, setEditingGraphGoal] = useState(false);
  const [goalEditDraft, setGoalEditDraft] = useState<GoalEditDraft | null>(null);
  const [savingGraphGoal, setSavingGraphGoal] = useState(false);
  const [graphError, setGraphError] = useState<string | null>(null);
  const [relationTargetId, setRelationTargetId] = useState<string>('');
  const [relationType, setRelationType] = useState<(typeof RELATION_OPTIONS)[number]['value']>('requires');
  const [relationNote, setRelationNote] = useState('');
  const [savingRelation, setSavingRelation] = useState(false);
  const [updatingParent, setUpdatingParent] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [domainsRes, goalsRes, summaryRes, graphRes] = await Promise.all([
        fetchLifeDomains(),
        fetchGoals({
          status: statusFilter || undefined,
          domain: domainFilter || undefined,
          horizon: horizonFilter || undefined,
          node_type: (nodeTypeFilter || undefined) as GoalNodeType | undefined,
        }),
        fetchGoalsSummary(),
        fetchGoalsGraph('all'),
      ]);
      setDomains(domainsRes.domains);
      setGoals(goalsRes.goals);
      setSummary(summaryRes);
      setGraphNodes(graphRes.nodes || []);
      setGraphEdges(graphRes.edges || []);

      // Initialize rating values from current ratings
      const currentRatings: Record<string, number> = {};
      domainsRes.domains.forEach((d) => {
        if (d.latest_rating) {
          currentRatings[d.code] = d.latest_rating;
        }
      });
      setRatingValues(currentRatings);
    } catch (e) {
      console.error('Error loading goals data:', e);
    } finally {
      setLoading(false);
    }
  }, [statusFilter, horizonFilter, domainFilter, nodeTypeFilter]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleRatingChange = (code: string, value: number) => {
    setRatingValues((prev) => ({ ...prev, [code]: value }));
  };

  const handleSaveRatings = async () => {
    setSavingRatings(true);
    try {
      await rateDomains(ratingValues);
      setShowRatingModal(false);
      loadData();
    } catch (e) {
      console.error('Error saving ratings:', e);
    } finally {
      setSavingRatings(false);
    }
  };

  const handleCreateGoal = async () => {
    if (!newGoal.title.trim()) return;

    setSavingGoal(true);
    try {
      const nodeType = newGoal.node_type;
      const result = await createGoal({
        ...newGoal,
        node_type: nodeType,
        domain_code: newGoal.domain_code || undefined,
        horizon: nodeSupportsHorizon(nodeType) ? (newGoal.horizon as Goal['horizon']) : null,
        motivation_type: newGoal.motivation_type || undefined,
        start_date: newGoal.start_date || undefined,
        target_date: newGoal.target_date || undefined,
        cadence_text: nodeSupportsCadence(nodeType) ? (newGoal.cadence_text || undefined) : undefined,
        time_cost_min: nodeSupportsActionCosts(nodeType) && newGoal.time_cost_min ? Number(newGoal.time_cost_min) : undefined,
        energy_cost: nodeSupportsActionCosts(nodeType) && newGoal.energy_cost ? Number(newGoal.energy_cost) : undefined,
        attention_cost: nodeSupportsActionCosts(nodeType) && newGoal.attention_cost ? Number(newGoal.attention_cost) : undefined,
      });
      if (result.ok) {
        setShowGoalModal(false);
        setNewGoal({
          node_type: 'goal',
          title: '',
          domain_code: '',
          description: '',
          why_matters: '',
          horizon: 'quarterly',
          start_date: '',
          target_date: '',
          cadence_text: '',
          time_cost_min: '',
          energy_cost: '',
          attention_cost: '',
          motivation_type: '',
        });
        loadData();
      }
    } catch (e) {
      console.error('Error creating goal:', e);
    } finally {
      setSavingGoal(false);
    }
  };

  const handleUpdateGoalStatus = async (goalId: number, status: string) => {
    try {
      await updateGoal(goalId, { status: status as Goal['status'] });
      loadData();
    } catch (e) {
      console.error('Error updating goal:', e);
    }
  };

  const handleUpdateProgress = async (goalId: number, progress: number) => {
    try {
      await updateGoal(goalId, { progress_pct: progress });
      loadData();
    } catch (e) {
      console.error('Error updating progress:', e);
    }
  };

  const handleDeleteGoal = async (goalId: number): Promise<boolean> => {
    if (!confirm('¿Eliminar esta meta?')) return false;
    try {
      await deleteGoal(goalId);
      loadData();
      return true;
    } catch (e) {
      console.error('Error deleting goal:', e);
      return false;
    }
    return false;
  };

  // Calculate average rating for wheel visualization
  const avgRating = domains.length > 0
    ? domains.reduce((sum, d) => sum + (d.latest_rating || 0), 0) / domains.filter(d => d.latest_rating).length || 0
    : 0;

  const visibleGraphNodes = useMemo(() => {
    if (goals.length === 0) return [];
    const graphById = new Map(graphNodes.map((node) => [node.id, node]));
    return goals.map((goal) => graphById.get(goal.id) || goal);
  }, [goals, graphNodes]);

  const visibleGraphEdges = useMemo(() => {
    const visibleIds = new Set(visibleGraphNodes.map((goal) => goal.id));
    return graphEdges.filter((edge) => visibleIds.has(edge.source_goal_id) && visibleIds.has(edge.target_goal_id));
  }, [graphEdges, visibleGraphNodes]);

  const goalsGraphLayout = useMemo(() => {
    const width = 980;
    const minHeight = 220;
    const layerGap = 90;
    const paddingX = 56;
    const nodeRadius = 18;

    if (visibleGraphNodes.length === 0) {
      return {
        width,
        height: minHeight,
        nodeRadius,
        depthById: {} as Record<number, number>,
        childrenCountById: {} as Record<number, number>,
        positionsById: {} as Record<number, { x: number; y: number }>,
      };
    }

    const parentEdges = visibleGraphEdges.filter((edge) => edge.kind === 'parent');
    const parentByChild = new Map<number, number[]>();
    const childrenCountById: Record<number, number> = {};

    for (const goal of visibleGraphNodes) {
      childrenCountById[goal.id] = 0;
    }

    for (const edge of parentEdges) {
      const list = parentByChild.get(edge.target_goal_id) || [];
      list.push(edge.source_goal_id);
      parentByChild.set(edge.target_goal_id, list);
      childrenCountById[edge.source_goal_id] = (childrenCountById[edge.source_goal_id] || 0) + 1;
    }

    const depthMemo = new Map<number, number>();
    const visiting = new Set<number>();

    const computeDepth = (goalId: number): number => {
      if (depthMemo.has(goalId)) return depthMemo.get(goalId)!;
      if (visiting.has(goalId)) return 0;

      visiting.add(goalId);
      const parents = parentByChild.get(goalId) || [];
      let depth = 0;
      if (parents.length > 0) {
        const parentDepths = parents.map((parentId) => computeDepth(parentId));
        depth = Math.min(...parentDepths) + 1;
      }
      visiting.delete(goalId);
      depthMemo.set(goalId, depth);
      return depth;
    };

    const depthById: Record<number, number> = {};
    let maxDepth = 0;
    for (const goal of visibleGraphNodes) {
      const depth = computeDepth(goal.id);
      depthById[goal.id] = depth;
      maxDepth = Math.max(maxDepth, depth);
    }

    const levels = new Map<number, Goal[]>();
    for (const goal of visibleGraphNodes) {
      const depth = depthById[goal.id] || 0;
      const levelGoals = levels.get(depth) || [];
      levelGoals.push(goal);
      levels.set(depth, levelGoals);
    }

    const height = Math.max(minHeight, 90 + maxDepth * layerGap);
    const positionsById: Record<number, { x: number; y: number }> = {};

    for (const [depth, levelGoalsRaw] of levels.entries()) {
      const levelGoals = [...levelGoalsRaw].sort((a, b) => {
        const childDiff = (childrenCountById[b.id] || 0) - (childrenCountById[a.id] || 0);
        if (childDiff !== 0) return childDiff;
        return a.title.localeCompare(b.title);
      });

      const y = getDepthTargetY(depth, maxDepth, height);
      if (levelGoals.length === 1) {
        positionsById[levelGoals[0].id] = { x: width / 2, y };
      } else {
        const span = Math.max(1, width - paddingX * 2);
        const step = span / (levelGoals.length - 1);
        levelGoals.forEach((goal, idx) => {
          positionsById[goal.id] = {
            x: paddingX + idx * step,
            y,
          };
        });
      }
    }

    return {
      width,
      height,
      nodeRadius,
      depthById,
      childrenCountById,
      positionsById,
    };
  }, [visibleGraphEdges, visibleGraphNodes]);

  const graphGoalById = useMemo(() => {
    const map = new Map<number, Goal>();
    for (const goal of graphNodes) {
      map.set(goal.id, goal);
    }
    return map;
  }, [graphNodes]);

  const selectedGraphGoal = useMemo(() => {
    if (selectedGraphGoalId == null) return null;
    return graphGoalById.get(selectedGraphGoalId) || null;
  }, [graphGoalById, selectedGraphGoalId]);

  const selectedGraphRelations = useMemo(() => {
    if (!selectedGraphGoal) return [];
    return graphEdges.filter(
      (edge) => edge.source_goal_id === selectedGraphGoal.id || edge.target_goal_id === selectedGraphGoal.id,
    );
  }, [graphEdges, selectedGraphGoal]);

  useEffect(() => {
    if (visibleGraphNodes.length === 0) {
      setSelectedGraphGoalId(null);
      return;
    }
    if (selectedGraphGoalId == null || !visibleGraphNodes.some((goal) => goal.id === selectedGraphGoalId)) {
      setSelectedGraphGoalId(visibleGraphNodes[0].id);
    }
  }, [selectedGraphGoalId, visibleGraphNodes]);

  useEffect(() => {
    if (!selectedGraphGoal) {
      setGoalEditDraft(null);
      setEditingGraphGoal(false);
      setRelationTargetId('');
      return;
    }

    const tags = selectedGraphGoal.domain_tags || [];
    const conflictsText =
      typeof selectedGraphGoal.conflicts_json === 'string'
        ? selectedGraphGoal.conflicts_json
        : JSON.stringify(selectedGraphGoal.conflicts_json ?? [], null, 2);
    const synergiesText =
      typeof selectedGraphGoal.synergies_json === 'string'
        ? selectedGraphGoal.synergies_json
        : JSON.stringify(selectedGraphGoal.synergies_json ?? [], null, 2);

    setGoalEditDraft({
      node_type: selectedGraphGoal.node_type || 'goal',
      title: selectedGraphGoal.title || '',
      description: selectedGraphGoal.description || '',
      why_matters: selectedGraphGoal.why_matters || '',
      domain_code: selectedGraphGoal.domain_code || '',
      domain_tags_input: tags.join(' | '),
      horizon: selectedGraphGoal.horizon || 'quarterly',
      start_date: selectedGraphGoal.start_date || '',
      target_date: selectedGraphGoal.target_date || '',
      cadence_text: selectedGraphGoal.cadence_text || '',
      time_cost_min: selectedGraphGoal.time_cost_min != null ? String(selectedGraphGoal.time_cost_min) : '',
      energy_cost: selectedGraphGoal.energy_cost != null ? String(selectedGraphGoal.energy_cost) : '',
      attention_cost: selectedGraphGoal.attention_cost != null ? String(selectedGraphGoal.attention_cost) : '',
      status: selectedGraphGoal.status || 'active',
      progress_pct: selectedGraphGoal.progress_pct ?? 0,
      motivation_type: selectedGraphGoal.motivation_type || '',
      importance: selectedGraphGoal.importance != null ? String(selectedGraphGoal.importance) : '',
      difficulty: selectedGraphGoal.difficulty != null ? String(selectedGraphGoal.difficulty) : '',
      commitment: selectedGraphGoal.commitment != null ? String(selectedGraphGoal.commitment) : '',
      specificity: selectedGraphGoal.specificity != null ? String(selectedGraphGoal.specificity) : '',
      locus_of_control: selectedGraphGoal.locus_of_control || '',
      nash_opinion: selectedGraphGoal.nash_opinion || '',
      coherence_score: selectedGraphGoal.coherence_score != null ? String(selectedGraphGoal.coherence_score) : '',
      conflicts_json: conflictsText || '[]',
      synergies_json: synergiesText || '[]',
      priority_rank: selectedGraphGoal.priority_rank != null ? String(selectedGraphGoal.priority_rank) : '',
    });

    const firstCandidate = graphNodes.find(
      (goal) => goal.id !== selectedGraphGoal.id && canParentNode(goal.node_type, selectedGraphGoal.node_type),
    );
    setRelationTargetId(firstCandidate ? String(firstCandidate.id) : '');
    setEditingGraphGoal(false);
  }, [graphNodes, selectedGraphGoal]);

  const handleSaveGraphGoalEdits = async () => {
    if (!selectedGraphGoal || !goalEditDraft) return;

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
      setGraphError('La meta necesita título.');
      return;
    }

    setSavingGraphGoal(true);
    setGraphError(null);
    try {
      const result = await updateGoal(selectedGraphGoal.id, updates);
      if (!result.ok) {
        setGraphError(result.error || 'No se pudo actualizar la meta.');
      } else {
        await loadData();
        setSelectedGraphGoalId(selectedGraphGoal.id);
        setEditingGraphGoal(false);
      }
    } catch {
      setGraphError('Error guardando cambios del nodo.');
    } finally {
      setSavingGraphGoal(false);
    }
  };

  const handleUpdateGraphParent = async (newParentIdRaw: string) => {
    if (!selectedGraphGoal) return;
    const parentGoalId = newParentIdRaw ? Number(newParentIdRaw) : null;

    setUpdatingParent(true);
    setGraphError(null);
    try {
      const result = await updateGoal(selectedGraphGoal.id, { parent_goal_id: parentGoalId });
      if (!result.ok) {
        setGraphError(result.error || 'No se pudo actualizar nodo padre.');
      } else {
        await loadData();
        setSelectedGraphGoalId(selectedGraphGoal.id);
      }
    } catch {
      setGraphError('Error actualizando jerarquía.');
    } finally {
      setUpdatingParent(false);
    }
  };

  const handleCreateGraphRelation = async () => {
    if (!selectedGraphGoal || !relationTargetId) return;

    setSavingRelation(true);
    setGraphError(null);
    try {
      const result = await createGoalRelation({
        source_goal_id: selectedGraphGoal.id,
        target_goal_id: Number(relationTargetId),
        relation_type: relationType,
        note: relationNote.trim() || undefined,
      });
      if (!result.ok) {
        setGraphError(result.error || 'No se pudo crear la relación.');
      } else {
        setRelationNote('');
        await loadData();
        setSelectedGraphGoalId(selectedGraphGoal.id);
      }
    } catch {
      setGraphError('Error creando relación.');
    } finally {
      setSavingRelation(false);
    }
  };

  const handleDeleteGraphRelation = async (relationId: number) => {
    setGraphError(null);
    try {
      const result = await deleteGoalRelation(relationId);
      if (!result.ok) {
        setGraphError(result.error || 'No se pudo eliminar la relación.');
      } else {
        await loadData();
      }
    } catch {
      setGraphError('Error eliminando relación.');
    }
  };

  const handleDeleteSelectedGraphGoal = async () => {
    if (!selectedGraphGoal) return;
    const deleted = await handleDeleteGoal(selectedGraphGoal.id);
    if (deleted) {
      setSelectedGraphGoalId(null);
      setGraphError(null);
    }
  };

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-6">
        <p className="text-[var(--nash-text-muted)]">Cargando...</p>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-6 space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-[var(--nash-prussian)]">Metas</h2>
        <div className="flex gap-3">
          <button
            onClick={() => setShowDiscovery(true)}
            className="bg-[var(--nash-teal)] text-white px-4 py-2 rounded-lg text-sm font-medium hover:opacity-90 cursor-pointer flex items-center gap-2"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
            Explorar Metas
          </button>
          <button
            onClick={() => setShowGoalModal(true)}
            className="bg-[var(--nash-accent)] text-white px-4 py-2 rounded-lg text-sm font-medium hover:opacity-90 cursor-pointer"
          >
            + Nuevo Nodo
          </button>
        </div>
      </div>

      {/* Summary Stats */}
      {summary && (
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded-lg p-4 text-center">
            <p className="text-2xl font-bold text-[var(--nash-accent)]">{summary.active}</p>
            <p className="text-xs text-[var(--nash-text-muted)]">Activas</p>
          </div>
          <div className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded-lg p-4 text-center">
            <p className="text-2xl font-bold text-[var(--nash-success)]">{summary.completed}</p>
            <p className="text-xs text-[var(--nash-text-muted)]">Completadas</p>
          </div>
          <div className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded-lg p-4 text-center">
            <p className="text-2xl font-bold text-[var(--nash-text)]">{summary.total}</p>
            <p className="text-xs text-[var(--nash-text-muted)]">Total</p>
          </div>
        </div>
      )}

      {/* Wheel of Life Section */}
      <div className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded-lg p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="font-semibold text-[var(--nash-text)]">Rueda de la Vida</h3>
            <p className="text-xs text-[var(--nash-text-muted)]">
              Promedio: {avgRating.toFixed(1)}/10
            </p>
          </div>
          <button
            onClick={() => setShowRatingModal(true)}
            className="text-sm text-[var(--nash-accent)] hover:underline cursor-pointer"
          >
            Actualizar
          </button>
        </div>

        {/* Domain Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {domains.map((domain) => (
            <div
              key={domain.code}
              className="bg-[var(--nash-bg)] rounded-lg p-3 text-center"
              style={{ borderLeft: `4px solid ${domain.color}` }}
            >
              <span className="text-2xl">{domain.icon}</span>
              <p className="text-sm font-medium mt-1">{domain.name_es}</p>
              <p className="text-xl font-bold" style={{ color: domain.color }}>
                {domain.latest_rating || '-'}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
        >
          <option value="">Todos los estados</option>
          <option value="active">Activas</option>
          <option value="completed">Completadas</option>
          <option value="paused">Pausadas</option>
          <option value="abandoned">Abandonadas</option>
        </select>

        <select
          value={horizonFilter}
          onChange={(e) => setHorizonFilter(e.target.value)}
          className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
        >
          <option value="">Todos los horizontes</option>
          {Object.entries(HORIZON_LABELS).map(([k, v]) => (
            <option key={k} value={k}>{v}</option>
          ))}
        </select>

        <select
          value={domainFilter}
          onChange={(e) => setDomainFilter(e.target.value)}
          className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
        >
          <option value="">Todos los dominios</option>
          {domains.map((d) => (
            <option key={d.code} value={d.code}>{d.icon} {d.name_es}</option>
          ))}
        </select>

        <select
          value={nodeTypeFilter}
          onChange={(e) => setNodeTypeFilter(e.target.value)}
          className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
        >
          <option value="">Todos los tipos</option>
          {Object.entries(NODE_TYPE_LABELS).map(([key, label]) => (
            <option key={key} value={key}>{NODE_TYPE_ICONS[key as GoalNodeType]} {label}</option>
          ))}
        </select>
      </div>

      {/* Goals Graph Visualizer */}
      <div className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded-lg p-4">
        <div className="flex items-start justify-between gap-3 mb-3">
          <div>
            <h3 className="font-semibold text-[var(--nash-text)]">Visualizador de Metas</h3>
            <p className="text-xs text-[var(--nash-text-muted)]">
              Selecciona un nodo para ver su carta editable y sus relaciones
            </p>
            <div className="flex flex-wrap gap-2 mt-2">
              {Object.entries(NODE_TYPE_LABELS).map(([key, label]) => (
                <span key={key} className="text-[11px] px-2 py-0.5 rounded bg-[var(--nash-bg)] text-[var(--nash-text-muted)] border border-[var(--nash-border)]">
                  {NODE_TYPE_ICONS[key as GoalNodeType]} {label}
                </span>
              ))}
            </div>
          </div>
          <span className="text-xs text-[var(--nash-text-muted)]">
            {visibleGraphNodes.length} nodos · {visibleGraphEdges.length} enlaces
          </span>
        </div>

        {graphError && (
          <div className="mb-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
            {graphError}
          </div>
        )}

        {visibleGraphNodes.length === 0 ? (
          <p className="text-sm text-[var(--nash-text-muted)] py-6 text-center">
            No hay metas para visualizar con los filtros actuales.
          </p>
        ) : (
          <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1.7fr)_minmax(340px,1fr)] gap-4">
            <div className="overflow-x-auto border border-[var(--nash-border)] rounded-lg bg-[var(--nash-bg)] p-2">
              <svg
                width="100%"
                height={Math.min(460, goalsGraphLayout.height + 28)}
                viewBox={`0 0 ${goalsGraphLayout.width} ${goalsGraphLayout.height}`}
              >
                {visibleGraphEdges.map((edge) => {
                  const source = goalsGraphLayout.positionsById[edge.source_goal_id];
                  const target = goalsGraphLayout.positionsById[edge.target_goal_id];
                  if (!source || !target) return null;

                  const color = EDGE_CATEGORY_COLORS[getEdgeCategory(edge)];

                  return (
                    <line
                      key={edge.id}
                      x1={source.x}
                      y1={source.y}
                      x2={target.x}
                      y2={target.y}
                      stroke={color}
                      strokeWidth={edge.kind === 'parent' ? 2.2 : 1.7}
                      strokeDasharray={edge.kind === 'parent' ? '0' : '5 4'}
                      opacity={0.86}
                    />
                  );
                })}

                {visibleGraphNodes.map((goal) => {
                  const pos = goalsGraphLayout.positionsById[goal.id];
                  if (!pos) return null;

                  const childrenCount = goalsGraphLayout.childrenCountById[goal.id] || 0;
                  const color = getColorByChildCount(childrenCount);
                  const shortTitle = goal.title.length > 24 ? `${goal.title.slice(0, 22)}...` : goal.title;
                  const selected = selectedGraphGoalId === goal.id;
                  const typeIcon = NODE_TYPE_ICONS[goal.node_type];
                  const typeLabel = getGoalTypeBadge(goal);

                  return (
                    <g
                      key={goal.id}
                      transform={`translate(${pos.x}, ${pos.y})`}
                      className="cursor-pointer"
                      onClick={() => {
                        setSelectedGraphGoalId(goal.id);
                        setGraphError(null);
                      }}
                    >
                      <circle
                        r={goalsGraphLayout.nodeRadius}
                        fill={color}
                        fillOpacity={selected ? 1 : 0.92}
                        stroke={selected ? '#1E293B' : '#FFFFFF'}
                        strokeWidth={selected ? 2.8 : 1.8}
                      />
                      <text
                        y={4}
                        textAnchor="middle"
                        fontSize="12"
                        fill="white"
                      >
                        {typeIcon}
                      </text>
                      <text
                        y={goalsGraphLayout.nodeRadius + 13}
                        textAnchor="middle"
                        fontSize="10"
                        fill="var(--nash-text)"
                      >
                        {shortTitle}
                      </text>
                      <text
                        y={-goalsGraphLayout.nodeRadius - 7}
                        textAnchor="middle"
                        fontSize="9"
                        fill="var(--nash-text-muted)"
                      >
                        {typeLabel} · {childrenCount} hijos
                      </text>
                      <title>{goal.title}</title>
                    </g>
                  );
                })}
              </svg>
            </div>

            <div className="border border-[var(--nash-border)] rounded-lg bg-[var(--nash-bg)] p-3 max-h-[460px] overflow-y-auto space-y-3">
              {!selectedGraphGoal && (
                <p className="text-xs text-[var(--nash-text-muted)]">
                  Selecciona un nodo del grafo para editar su carta y gestionar relaciones.
                </p>
              )}

              {selectedGraphGoal && (
                <>
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="text-[11px] uppercase tracking-wide text-[var(--nash-accent)] font-semibold">Nodo seleccionado</p>
                      <h4 className="font-semibold text-sm text-[var(--nash-text)] mt-1">
                        {NODE_TYPE_ICONS[selectedGraphGoal.node_type]} {selectedGraphGoal.title}
                      </h4>
                      <p className="text-xs text-[var(--nash-text-muted)] mt-1">
                        Estado: {STATUS_LABELS[selectedGraphGoal.status]} · Progreso: {selectedGraphGoal.progress_pct}%
                      </p>
                      <div className="flex flex-wrap gap-2 mt-2">
                        <span className="text-[11px] px-2 py-0.5 rounded bg-[var(--nash-prussian-soft)] text-[var(--nash-prussian)]">
                          {getGoalTypeBadge(selectedGraphGoal)}
                        </span>
                        {selectedGraphGoal.node_type === 'goal' && !selectedGraphGoal.parent_goal_id && (goalsGraphLayout.childrenCountById[selectedGraphGoal.id] || 0) > 0 && (
                          <span className="text-[11px] px-2 py-0.5 rounded bg-[var(--nash-surface)] text-[var(--nash-text-muted)]">
                            Super-goal
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => setEditingGraphGoal((prev) => !prev)}
                        className="text-xs px-2 py-1 border border-[var(--nash-border)] rounded hover:bg-[var(--nash-surface)] cursor-pointer"
                      >
                        {editingGraphGoal ? 'Cerrar edición' : 'Editar'}
                      </button>
                      <button
                        type="button"
                        onClick={handleDeleteSelectedGraphGoal}
                        className="text-xs px-2 py-1 border border-[var(--nash-error)] text-[var(--nash-error)] rounded hover:bg-red-50 cursor-pointer"
                      >
                        Eliminar
                      </button>
                    </div>
                  </div>

                  {!editingGraphGoal && (
                    <div className="text-xs grid grid-cols-1 gap-1.5">
                      <p><span className="font-medium">Descripción:</span> {selectedGraphGoal.description || '—'}</p>
                      <p><span className="font-medium">Por qué importa:</span> {selectedGraphGoal.why_matters || '—'}</p>
                      <p><span className="font-medium">Tipo:</span> {NODE_TYPE_LABELS[selectedGraphGoal.node_type]}</p>
                      <p><span className="font-medium">Dominio principal:</span> {selectedGraphGoal.domain_code || '—'}</p>
                      <p><span className="font-medium">Tags:</span> {selectedGraphGoal.domain_tags?.join(' | ') || '—'}</p>
                      {nodeSupportsHorizon(selectedGraphGoal.node_type) && (
                        <p><span className="font-medium">Horizonte:</span> {selectedGraphGoal.horizon ? (HORIZON_LABELS[selectedGraphGoal.horizon] || selectedGraphGoal.horizon) : '—'}</p>
                      )}
                      <p><span className="font-medium">Fecha de inicio:</span> {selectedGraphGoal.start_date || '—'}</p>
                      <p><span className="font-medium">Fecha objetivo:</span> {selectedGraphGoal.target_date || '—'}</p>
                      {nodeSupportsCadence(selectedGraphGoal.node_type) && (
                        <p><span className="font-medium">Cadencia:</span> {selectedGraphGoal.cadence_text || '—'}</p>
                      )}
                      {nodeSupportsActionCosts(selectedGraphGoal.node_type) && (
                        <p><span className="font-medium">Costos:</span> Tiempo {selectedGraphGoal.time_cost_min ?? '—'} min · Energía {selectedGraphGoal.energy_cost ?? '—'}/5 · Atención {selectedGraphGoal.attention_cost ?? '—'}/5</p>
                      )}
                      <p><span className="font-medium">Motivación:</span> {selectedGraphGoal.motivation_type ? (MOTIVATION_LABELS[selectedGraphGoal.motivation_type]?.label || selectedGraphGoal.motivation_type) : '—'}</p>
                    </div>
                  )}

                  {editingGraphGoal && goalEditDraft && (
                    <div className="space-y-2 border border-[var(--nash-border)] rounded-lg p-3 bg-[var(--nash-surface)]">
                      <select value={goalEditDraft.node_type} onChange={(e) => setGoalEditDraft({ ...goalEditDraft, node_type: e.target.value as GoalNodeType })} className="w-full bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs">
                        {Object.entries(NODE_TYPE_LABELS).map(([key, label]) => (
                          <option key={key} value={key}>{label}</option>
                        ))}
                      </select>
                      <input value={goalEditDraft.title} onChange={(e) => setGoalEditDraft({ ...goalEditDraft, title: e.target.value })} placeholder="Título" className="w-full bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs" />
                      <textarea value={goalEditDraft.description} onChange={(e) => setGoalEditDraft({ ...goalEditDraft, description: e.target.value })} placeholder="Descripción" rows={2} className="w-full bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs" />
                      <textarea value={goalEditDraft.why_matters} onChange={(e) => setGoalEditDraft({ ...goalEditDraft, why_matters: e.target.value })} placeholder="Por qué importa" rows={2} className="w-full bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs" />
                      <input value={goalEditDraft.domain_tags_input} onChange={(e) => setGoalEditDraft({ ...goalEditDraft, domain_tags_input: e.target.value })} placeholder="Tags de dominio (career|music|ai)" className="w-full bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs" />
                      <div className="grid grid-cols-2 gap-2">
                        <select value={goalEditDraft.domain_code} onChange={(e) => setGoalEditDraft({ ...goalEditDraft, domain_code: e.target.value })} className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs">
                          <option value="">Sin dominio principal</option>
                          {domains.map((domain) => (
                            <option key={domain.code} value={domain.code}>{domain.icon} {domain.name_es}</option>
                          ))}
                        </select>
                        {nodeSupportsHorizon(goalEditDraft.node_type) ? (
                          <select value={goalEditDraft.horizon} onChange={(e) => setGoalEditDraft({ ...goalEditDraft, horizon: e.target.value })} className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs">
                            {!nodeRequiresHorizon(goalEditDraft.node_type) && <option value="">Sin horizonte</option>}
                            {Object.entries(HORIZON_LABELS).map(([key, label]) => (
                              <option key={key} value={key}>{label}</option>
                            ))}
                          </select>
                        ) : (
                          <div className="text-xs px-2 py-1.5 border border-dashed border-[var(--nash-border)] rounded text-[var(--nash-text-muted)]">
                            Este tipo no usa horizonte
                          </div>
                        )}
                      </div>
                      <div className="grid grid-cols-2 gap-2">
                        <input type="date" value={goalEditDraft.start_date} onChange={(e) => setGoalEditDraft({ ...goalEditDraft, start_date: e.target.value })} className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs" />
                        <input type="date" value={goalEditDraft.target_date} onChange={(e) => setGoalEditDraft({ ...goalEditDraft, target_date: e.target.value })} className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs" />
                      </div>
                      {nodeSupportsCadence(goalEditDraft.node_type) && (
                        <input value={goalEditDraft.cadence_text} onChange={(e) => setGoalEditDraft({ ...goalEditDraft, cadence_text: e.target.value })} placeholder="Cadencia (daily, weekly, 3x/semana...)" className="w-full bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs" />
                      )}
                      {nodeSupportsActionCosts(goalEditDraft.node_type) && (
                        <div className="grid grid-cols-3 gap-2">
                          <input value={goalEditDraft.time_cost_min} onChange={(e) => setGoalEditDraft({ ...goalEditDraft, time_cost_min: e.target.value })} placeholder="Tiempo (min)" className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs" />
                          <input value={goalEditDraft.energy_cost} onChange={(e) => setGoalEditDraft({ ...goalEditDraft, energy_cost: e.target.value })} placeholder="Energía 1-5" className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs" />
                          <input value={goalEditDraft.attention_cost} onChange={(e) => setGoalEditDraft({ ...goalEditDraft, attention_cost: e.target.value })} placeholder="Atención 1-5" className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs" />
                        </div>
                      )}
                      <div className="grid grid-cols-2 gap-2">
                        <select value={goalEditDraft.status} onChange={(e) => setGoalEditDraft({ ...goalEditDraft, status: e.target.value as Goal['status'] })} className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs">
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
                        <select value={goalEditDraft.motivation_type} onChange={(e) => setGoalEditDraft({ ...goalEditDraft, motivation_type: e.target.value })} className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs">
                          <option value="">Sin motivación</option>
                          {Object.entries(MOTIVATION_LABELS).map(([key, item]) => (
                            <option key={key} value={key}>{item.label}</option>
                          ))}
                        </select>
                        <select value={goalEditDraft.locus_of_control} onChange={(e) => setGoalEditDraft({ ...goalEditDraft, locus_of_control: e.target.value })} className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs">
                          <option value="">Locus no definido</option>
                          <option value="internal">Interno</option>
                          <option value="external">Externo</option>
                          <option value="mixed">Mixto</option>
                        </select>
                      </div>
                      <div className="grid grid-cols-3 gap-2">
                        <input value={goalEditDraft.importance} onChange={(e) => setGoalEditDraft({ ...goalEditDraft, importance: e.target.value })} placeholder="Importancia" className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs" />
                        <input value={goalEditDraft.difficulty} onChange={(e) => setGoalEditDraft({ ...goalEditDraft, difficulty: e.target.value })} placeholder="Dificultad" className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs" />
                        <input value={goalEditDraft.commitment} onChange={(e) => setGoalEditDraft({ ...goalEditDraft, commitment: e.target.value })} placeholder="Compromiso" className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs" />
                      </div>
                      <div className="grid grid-cols-3 gap-2">
                        <input value={goalEditDraft.specificity} onChange={(e) => setGoalEditDraft({ ...goalEditDraft, specificity: e.target.value })} placeholder="Especificidad" className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs" />
                        <input value={goalEditDraft.coherence_score} onChange={(e) => setGoalEditDraft({ ...goalEditDraft, coherence_score: e.target.value })} placeholder="Coherencia" className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs" />
                        <input value={goalEditDraft.priority_rank} onChange={(e) => setGoalEditDraft({ ...goalEditDraft, priority_rank: e.target.value })} placeholder="Prioridad" className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs" />
                      </div>
                      <textarea value={goalEditDraft.nash_opinion} onChange={(e) => setGoalEditDraft({ ...goalEditDraft, nash_opinion: e.target.value })} placeholder="Opinión de Nash" rows={2} className="w-full bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs" />
                      <textarea value={goalEditDraft.conflicts_json} onChange={(e) => setGoalEditDraft({ ...goalEditDraft, conflicts_json: e.target.value })} placeholder='Conflictos JSON' rows={2} className="w-full bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs font-mono" />
                      <textarea value={goalEditDraft.synergies_json} onChange={(e) => setGoalEditDraft({ ...goalEditDraft, synergies_json: e.target.value })} placeholder='Sinergias JSON' rows={2} className="w-full bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs font-mono" />
                      <div className="flex gap-2">
                        <button type="button" onClick={handleSaveGraphGoalEdits} disabled={savingGraphGoal} className="flex-1 text-xs py-2 bg-[var(--nash-success)] text-white rounded hover:opacity-90 disabled:opacity-50 cursor-pointer disabled:cursor-not-allowed">
                          {savingGraphGoal ? 'Guardando...' : 'Guardar cambios'}
                        </button>
                        <button type="button" onClick={() => setEditingGraphGoal(false)} className="text-xs py-2 px-3 text-[var(--nash-text-muted)] border border-[var(--nash-border)] rounded hover:bg-[var(--nash-surface)] cursor-pointer">
                          Cancelar
                        </button>
                      </div>
                    </div>
                  )}

                  <div className="space-y-1">
                    <label className="text-xs font-medium text-[var(--nash-text-muted)]">Nodo padre (jerarquía)</label>
                    <select
                      value={selectedGraphGoal.parent_goal_id ?? ''}
                      onChange={(e) => handleUpdateGraphParent(e.target.value)}
                      disabled={updatingParent}
                      className="w-full bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs"
                    >
                      <option value="">Sin meta padre</option>
                      {graphNodes
                        .filter((goal) => goal.id !== selectedGraphGoal.id && canParentNode(goal.node_type, selectedGraphGoal.node_type))
                        .map((goal) => (
                          <option key={goal.id} value={goal.id}>
                            {NODE_TYPE_ICONS[goal.node_type]} {goal.title}
                          </option>
                        ))}
                    </select>
                  </div>

                  <div className="space-y-2 border border-[var(--nash-border)] rounded-lg p-3 bg-[var(--nash-surface)]">
                    <p className="text-xs font-medium text-[var(--nash-text-muted)]">Crear relación</p>
                    <select
                      value={relationTargetId}
                      onChange={(e) => setRelationTargetId(e.target.value)}
                      className="w-full bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs"
                    >
                      <option value="">Selecciona meta destino</option>
                      {graphNodes
                        .filter((goal) => goal.id !== selectedGraphGoal.id)
                        .map((goal) => (
                          <option key={goal.id} value={goal.id}>
                            {NODE_TYPE_ICONS[goal.node_type]} {goal.title}
                          </option>
                        ))}
                    </select>

                    <select
                      value={relationType}
                      onChange={(e) => setRelationType(e.target.value as (typeof RELATION_OPTIONS)[number]['value'])}
                      className="w-full bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs"
                    >
                      {RELATION_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>{option.label}</option>
                      ))}
                    </select>

                    <input
                      value={relationNote}
                      onChange={(e) => setRelationNote(e.target.value)}
                      placeholder="Nota opcional de la relación"
                      className="w-full bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded px-2 py-1.5 text-xs"
                    />

                    <button
                      type="button"
                      onClick={handleCreateGraphRelation}
                      disabled={!relationTargetId || savingRelation}
                      className="w-full text-xs py-2 bg-[var(--nash-accent)] text-white rounded hover:opacity-90 disabled:opacity-50 cursor-pointer disabled:cursor-not-allowed"
                    >
                      {savingRelation ? 'Creando...' : 'Crear relación'}
                    </button>
                  </div>

                  <div className="space-y-2">
                    <p className="text-xs font-medium text-[var(--nash-text-muted)]">Relaciones del nodo</p>
                    {selectedGraphRelations.length === 0 && (
                      <p className="text-xs text-[var(--nash-text-muted)]">Aún no tiene relaciones.</p>
                    )}
                    {selectedGraphRelations.map((edge) => {
                      const outgoing = edge.source_goal_id === selectedGraphGoal.id;
                      const otherGoalId = outgoing ? edge.target_goal_id : edge.source_goal_id;
                      const otherGoal = graphGoalById.get(otherGoalId);
                      const otherLabel = otherGoal?.title || `Meta ${otherGoalId}`;
                      const edgeColor = EDGE_CATEGORY_COLORS[getEdgeCategory(edge)];

                      return (
                        <div
                          key={edge.id}
                          className="text-xs border rounded-lg p-2 bg-[var(--nash-bg)]"
                          style={{ borderColor: edgeColor }}
                        >
                          <p className="font-medium text-[var(--nash-text)]">
                            {outgoing ? '→' : '←'} {RELATION_LABELS[edge.relation_type] || edge.relation_type} {otherLabel}
                          </p>
                          <p className="mt-1" style={{ color: edgeColor }}>
                            {EDGE_CATEGORY_LABELS[getEdgeCategory(edge)]}
                          </p>
                          {edge.note && (
                            <p className="text-[var(--nash-text-muted)] mt-1">{edge.note}</p>
                          )}
                          {edge.kind === 'relation' && edge.relation_id && (
                            <button
                              type="button"
                              onClick={() => handleDeleteGraphRelation(edge.relation_id!)}
                              className="mt-1 text-[var(--nash-error)] hover:underline cursor-pointer"
                            >
                              Eliminar relación
                            </button>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Goals List */}
      <div className="space-y-3">
        {goals.length === 0 && (
          <p className="text-[var(--nash-text-muted)] text-center py-8">
            No hay metas con estos filtros. Crea una nueva meta para empezar.
          </p>
        )}

        {goals.map((goal) => (
          <div
            key={goal.id}
            className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded-lg p-4 hover:border-[var(--nash-accent)]/30 transition-colors"
          >
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span>{NODE_TYPE_ICONS[goal.node_type]}</span>
                  <h4 className="font-medium text-[var(--nash-text)]">{goal.title}</h4>
                </div>

                {goal.description && (
                  <p className="text-sm text-[var(--nash-text-muted)] mb-2">{goal.description}</p>
                )}

                {goal.why_matters && (
                  <p className="text-xs text-[var(--nash-teal)] mb-2 italic">
                    Por que: {goal.why_matters}
                  </p>
                )}

                <p className="text-xs text-[var(--nash-text-muted)] mb-2">
                  Inicio: {goal.start_date || '—'} · Objetivo: {goal.target_date || '—'}
                </p>
                {goal.node_type === 'system' && (
                  <p className="text-xs text-[var(--nash-text-muted)] mb-2">
                    Cadencia: {goal.cadence_text || '—'}
                  </p>
                )}
                {goal.node_type === 'action' && (
                  <p className="text-xs text-[var(--nash-text-muted)] mb-2">
                    Costos: {goal.time_cost_min ?? '—'} min · Energía {goal.energy_cost ?? '—'}/5 · Atención {goal.attention_cost ?? '—'}/5
                  </p>
                )}

                {/* Progress bar */}
                <div className="flex items-center gap-3 mb-2">
                  <div className="flex-1 h-2 bg-[var(--nash-bg)] rounded-full overflow-hidden">
                    <div
                      className="h-full bg-[var(--nash-accent)] transition-all"
                      style={{ width: `${goal.progress_pct}%` }}
                    />
                  </div>
                  <span className="text-xs text-[var(--nash-text-muted)] w-12">
                    {goal.progress_pct}%
                  </span>
                </div>

                {/* Tags */}
                <div className="flex flex-wrap gap-2">
                  <span className="text-xs px-2 py-0.5 rounded bg-[var(--nash-prussian-soft)] text-[var(--nash-prussian)]">
                    {getGoalTypeBadge(goal)}
                  </span>
                  {goal.horizon && (
                    <span className="text-xs px-2 py-0.5 rounded bg-[var(--nash-prussian-soft)] text-[var(--nash-prussian)]">
                      {HORIZON_LABELS[goal.horizon]}
                    </span>
                  )}
                  <span className={`text-xs px-2 py-0.5 rounded ${
                    goal.status === 'active' ? 'bg-[var(--nash-teal-soft)] text-[var(--nash-teal)]' :
                    goal.status === 'completed' ? 'bg-green-100 text-green-700' :
                    goal.status === 'paused' ? 'bg-yellow-100 text-yellow-700' :
                    'bg-gray-100 text-gray-600'
                  }`}>
                    {STATUS_LABELS[goal.status]}
                  </span>
                  {goal.motivation_type && (
                    <span
                      className="text-xs px-2 py-0.5 rounded bg-[var(--nash-surface-2)]"
                      style={{ color: MOTIVATION_LABELS[goal.motivation_type]?.color }}
                    >
                      {MOTIVATION_LABELS[goal.motivation_type]?.label}
                    </span>
                  )}
                  {goal.domain_name && (
                    <span className="text-xs px-2 py-0.5 rounded bg-[var(--nash-surface-2)] text-[var(--nash-text-muted)]">
                      {goal.domain_name}
                    </span>
                  )}
                </div>
              </div>

              {/* Actions */}
              <div className="flex flex-col gap-1">
                {goal.status === 'active' && (
                  <>
                    <button
                      onClick={() => handleUpdateProgress(goal.id, Math.min(100, goal.progress_pct + 10))}
                      className="text-xs text-[var(--nash-teal)] hover:underline cursor-pointer"
                      title="Aumentar progreso"
                    >
                      +10%
                    </button>
                    <button
                      onClick={() => handleUpdateGoalStatus(goal.id, 'completed')}
                      className="text-xs text-[var(--nash-success)] hover:underline cursor-pointer"
                    >
                      Completar
                    </button>
                    <button
                      onClick={() => handleUpdateGoalStatus(goal.id, 'paused')}
                      className="text-xs text-[var(--nash-warning)] hover:underline cursor-pointer"
                    >
                      Pausar
                    </button>
                  </>
                )}
                {goal.status === 'paused' && (
                  <button
                    onClick={() => handleUpdateGoalStatus(goal.id, 'active')}
                    className="text-xs text-[var(--nash-teal)] hover:underline cursor-pointer"
                  >
                    Reactivar
                  </button>
                )}
                <button
                  onClick={() => handleDeleteGoal(goal.id)}
                  className="text-xs text-[var(--nash-error)] hover:underline cursor-pointer"
                >
                  Eliminar
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Rating Modal */}
      {showRatingModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-[var(--nash-bg)] rounded-xl p-6 max-w-lg w-full max-h-[80vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">Actualizar Rueda de la Vida</h3>
              <button
                onClick={() => setShowRatingModal(false)}
                className="text-[var(--nash-text-muted)] hover:text-[var(--nash-text)] cursor-pointer"
              >
                ✕
              </button>
            </div>

            <p className="text-sm text-[var(--nash-text-muted)] mb-4">
              Califica cada area de tu vida del 1 al 10
            </p>

            <div className="space-y-4">
              {domains.map((domain) => (
                <div key={domain.code}>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm">
                      {domain.icon} {domain.name_es}
                    </span>
                    <span className="text-sm font-bold" style={{ color: domain.color }}>
                      {ratingValues[domain.code] || '-'}
                    </span>
                  </div>
                  <input
                    type="range"
                    min="1"
                    max="10"
                    value={ratingValues[domain.code] || 5}
                    onChange={(e) => handleRatingChange(domain.code, parseInt(e.target.value))}
                    className="w-full"
                    style={{ accentColor: domain.color }}
                  />
                </div>
              ))}
            </div>

            <div className="flex justify-end gap-3 mt-6">
              <button
                onClick={() => setShowRatingModal(false)}
                className="px-4 py-2 text-sm text-[var(--nash-text-muted)] hover:text-[var(--nash-text)] cursor-pointer"
              >
                Cancelar
              </button>
              <button
                onClick={handleSaveRatings}
                disabled={savingRatings}
                className="px-4 py-2 text-sm bg-[var(--nash-accent)] text-white rounded-lg hover:opacity-90 disabled:opacity-50 cursor-pointer disabled:cursor-not-allowed"
              >
                {savingRatings ? 'Guardando...' : 'Guardar'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* New Goal Modal */}
      {showGoalModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-[var(--nash-bg)] rounded-xl p-6 max-w-lg w-full max-h-[80vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">Nuevo Nodo</h3>
              <button
                onClick={() => setShowGoalModal(false)}
                className="text-[var(--nash-text-muted)] hover:text-[var(--nash-text)] cursor-pointer"
              >
                ✕
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">Tipo de nodo</label>
                <select
                  value={newGoal.node_type}
                  onChange={(e) => setNewGoal({ ...newGoal, node_type: e.target.value as GoalNodeType })}
                  className="w-full bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                >
                  {Object.entries(NODE_TYPE_LABELS).map(([key, label]) => (
                    <option key={key} value={key}>{NODE_TYPE_ICONS[key as GoalNodeType]} {label}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">Titulo *</label>
                <input
                  type="text"
                  value={newGoal.title}
                  onChange={(e) => setNewGoal({ ...newGoal, title: e.target.value })}
                  placeholder={
                    newGoal.node_type === 'identity'
                      ? 'Ej: Ser una persona calma y estable'
                      : newGoal.node_type === 'system'
                        ? 'Ej: Revisión semanal de carrera'
                        : newGoal.node_type === 'action'
                          ? 'Ej: Postular a 3 roles esta semana'
                          : '¿Qué quieres lograr?'
                  }
                  className="w-full bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">Por que es importante (auto-concordancia)</label>
                <textarea
                  value={newGoal.why_matters}
                  onChange={(e) => setNewGoal({ ...newGoal, why_matters: e.target.value })}
                  placeholder="¿Por que quieres esto? ¿Como se conecta con tus valores?"
                  rows={2}
                  className="w-full bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-1">Dominio</label>
                  <select
                    value={newGoal.domain_code}
                    onChange={(e) => setNewGoal({ ...newGoal, domain_code: e.target.value })}
                    className="w-full bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                  >
                    <option value="">Sin dominio</option>
                    {domains.map((d) => (
                      <option key={d.code} value={d.code}>{d.icon} {d.name_es}</option>
                    ))}
                  </select>
                </div>

                {nodeSupportsHorizon(newGoal.node_type) ? (
                  <div>
                    <label className="block text-sm font-medium mb-1">Horizonte</label>
                    <select
                      value={newGoal.horizon}
                      onChange={(e) => setNewGoal({ ...newGoal, horizon: e.target.value })}
                      className="w-full bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                    >
                      {!nodeRequiresHorizon(newGoal.node_type) && <option value="">Sin horizonte</option>}
                      {Object.entries(HORIZON_LABELS).map(([k, v]) => (
                        <option key={k} value={k}>{v}</option>
                      ))}
                    </select>
                  </div>
                ) : (
                  <div className="flex items-end">
                    <div className="w-full text-xs text-[var(--nash-text-muted)] border border-dashed border-[var(--nash-border)] rounded-lg px-3 py-2">
                      Este tipo no usa horizonte.
                    </div>
                  </div>
                )}
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-1">Tipo de motivacion</label>
                  <select
                    value={newGoal.motivation_type}
                    onChange={(e) => setNewGoal({ ...newGoal, motivation_type: e.target.value })}
                    className="w-full bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                  >
                    <option value="">No especificado</option>
                    <option value="intrinsic">Intrinseca (disfruto haciendolo)</option>
                    <option value="identified">Identificada (creo que es importante)</option>
                    <option value="introjected">Introyectada (me sentiria culpable si no)</option>
                    <option value="external">Externa (otros esperan que lo haga)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1">Fecha de inicio</label>
                  <input
                    type="date"
                    value={newGoal.start_date}
                    onChange={(e) => setNewGoal({ ...newGoal, start_date: e.target.value })}
                    className="w-full bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1">Fecha objetivo</label>
                  <input
                    type="date"
                    value={newGoal.target_date}
                    onChange={(e) => setNewGoal({ ...newGoal, target_date: e.target.value })}
                    className="w-full bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                  />
                </div>
              </div>

              {nodeSupportsCadence(newGoal.node_type) && (
                <div>
                  <label className="block text-sm font-medium mb-1">Cadencia</label>
                  <input
                    type="text"
                    value={newGoal.cadence_text}
                    onChange={(e) => setNewGoal({ ...newGoal, cadence_text: e.target.value })}
                    placeholder="daily, weekly, 3x/semana..."
                    className="w-full bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                  />
                </div>
              )}

              {nodeSupportsActionCosts(newGoal.node_type) && (
                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <label className="block text-sm font-medium mb-1">Tiempo (min)</label>
                    <input
                      type="number"
                      min="0"
                      value={newGoal.time_cost_min}
                      onChange={(e) => setNewGoal({ ...newGoal, time_cost_min: e.target.value })}
                      className="w-full bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Energía (1-5)</label>
                    <input
                      type="number"
                      min="1"
                      max="5"
                      value={newGoal.energy_cost}
                      onChange={(e) => setNewGoal({ ...newGoal, energy_cost: e.target.value })}
                      className="w-full bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Atención (1-5)</label>
                    <input
                      type="number"
                      min="1"
                      max="5"
                      value={newGoal.attention_cost}
                      onChange={(e) => setNewGoal({ ...newGoal, attention_cost: e.target.value })}
                      className="w-full bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                    />
                  </div>
                </div>
              )}

              <div>
                <label className="block text-sm font-medium mb-1">Descripcion</label>
                <textarea
                  value={newGoal.description}
                  onChange={(e) => setNewGoal({ ...newGoal, description: e.target.value })}
                  placeholder="Detalles adicionales..."
                  rows={2}
                  className="w-full bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                />
              </div>
            </div>

            <div className="flex justify-end gap-3 mt-6">
              <button
                onClick={() => setShowGoalModal(false)}
                className="px-4 py-2 text-sm text-[var(--nash-text-muted)] hover:text-[var(--nash-text)] cursor-pointer"
              >
                Cancelar
              </button>
              <button
                onClick={handleCreateGoal}
                disabled={savingGoal || !newGoal.title.trim()}
                className="px-4 py-2 text-sm bg-[var(--nash-accent)] text-white rounded-lg hover:opacity-90 disabled:opacity-50 cursor-pointer disabled:cursor-not-allowed"
              >
                {savingGoal ? 'Creando...' : 'Crear nodo'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Goal Discovery Modal */}
      {showDiscovery && (
        <GoalDiscovery
          domains={domains}
          onClose={() => setShowDiscovery(false)}
          onGoalSaved={() => loadData()}
        />
      )}
    </div>
  );
}
