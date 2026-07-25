import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  createExpense,
  fetchExpenseCategories,
  fetchExpenses,
  fetchFinanceProfile,
  fetchFinanceSummary,
  type ExpenseCategory,
  type ExpenseEntry,
  type FinanceProfile,
  type FinanceSummary,
} from '../../api';
import { ModuleDiscovery } from '../ModuleDiscovery';

function formatDateTime(ts: string): string {
  const d = new Date(ts.endsWith('Z') ? ts : `${ts}Z`);
  return d.toLocaleString('es-MX', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function parseJsonArray(raw: string | null | undefined): Array<Record<string, unknown>> {
  if (!raw) {
    return [];
  }
  try {
    const parsed: unknown = JSON.parse(raw);
    if (Array.isArray(parsed)) {
      return parsed.filter((item): item is Record<string, unknown> => item != null && typeof item === 'object');
    }
    return [];
  } catch {
    return [];
  }
}

export function Dinero() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [savingExpense, setSavingExpense] = useState(false);

  const [profile, setProfile] = useState<FinanceProfile | null>(null);
  const [categories, setCategories] = useState<ExpenseCategory[]>([]);
  const [expenses, setExpenses] = useState<ExpenseEntry[]>([]);
  const [summary, setSummary] = useState<FinanceSummary>({ total: 0, by_category: [] });
  const [showDiscovery, setShowDiscovery] = useState(false);

  const [description, setDescription] = useState('');
  const [amount, setAmount] = useState('');
  const [categoryCode, setCategoryCode] = useState('');
  const [notes, setNotes] = useState('');
  const [isRecurring, setIsRecurring] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [profileRes, categoriesRes, expensesRes, summaryRes] = await Promise.all([
        fetchFinanceProfile(),
        fetchExpenseCategories(),
        fetchExpenses({ limit: 50 }),
        fetchFinanceSummary(),
      ]);
      setProfile(profileRes.profile || null);
      setCategories(categoriesRes.categories || []);
      setExpenses(expensesRes.expenses || []);
      setSummary(summaryRes.summary || { total: 0, by_category: [] });
    } catch {
      setError('No se pudieron cargar los datos de Dinero.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const currency = profile?.currency || 'PEN';

  const currencyFormatter = useMemo(() => {
    try {
      return new Intl.NumberFormat('es-PE', {
        style: 'currency',
        currency,
        maximumFractionDigits: 2,
      });
    } catch {
      return new Intl.NumberFormat('es-PE', {
        style: 'currency',
        currency: 'PEN',
        maximumFractionDigits: 2,
      });
    }
  }, [currency]);

  const fixedExpenses = profile?.fixed_expenses || parseJsonArray(profile?.fixed_expenses_json);
  const debts = profile?.debts || parseJsonArray(profile?.debts_json);

  const handleSubmitExpense = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!description.trim()) {
      setFormError('Descripcion requerida.');
      return;
    }

    const amountValue = Number(amount);
    if (Number.isNaN(amountValue) || amountValue <= 0) {
      setFormError('Monto invalido.');
      return;
    }

    setSavingExpense(true);
    setFormError(null);

    try {
      const res = await createExpense({
        description: description.trim(),
        amount: amountValue,
        category_code: categoryCode || undefined,
        notes: notes.trim() || undefined,
        is_recurring: isRecurring,
      });

      if (!res.ok) {
        setFormError(res.error || 'No se pudo guardar el gasto.');
        return;
      }

      setDescription('');
      setAmount('');
      setCategoryCode('');
      setNotes('');
      setIsRecurring(false);
      await loadData();
    } catch {
      setFormError('Error guardando gasto.');
    } finally {
      setSavingExpense(false);
    }
  };

  return (
    <>
      <div className="max-w-5xl mx-auto px-4 py-6 space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <h2 className="text-xl font-semibold text-[var(--nash-prussian)]">Dinero</h2>
            <p className="text-sm text-[var(--nash-text-muted)]">
              Tracking rapido de gastos, deudas y flujo mensual.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => setShowDiscovery(true)}
              className="px-3 py-2 rounded-lg bg-[var(--nash-teal-soft)] text-[var(--nash-teal)] border border-[var(--nash-teal)] text-sm font-medium cursor-pointer hover:opacity-90"
            >
              Descubrir Finanzas
            </button>
            <button
              onClick={loadData}
              className="px-3 py-2 rounded-lg border border-[var(--nash-border)] text-sm text-[var(--nash-text-muted)] cursor-pointer hover:text-[var(--nash-text)]"
            >
              Actualizar
            </button>
          </div>
        </div>

        {error && (
          <p className="text-sm text-[var(--nash-warning)]">{error}</p>
        )}

        {loading && (
          <p className="text-sm text-[var(--nash-text-muted)]">Cargando modulo...</p>
        )}

        {!loading && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <section className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded-xl p-5 space-y-5">
              <div>
                <h3 className="font-semibold text-[var(--nash-text)]">Resumen mensual</h3>
                <p className="text-xs text-[var(--nash-text-muted)]">
                  Vista rapida de ingresos, gastos y categorias.
                </p>
              </div>

              <div className="grid grid-cols-2 gap-3 text-sm">
                <div className="bg-[var(--nash-surface-2)] rounded-lg p-3">
                  <p className="text-xs text-[var(--nash-text-muted)]">Ingreso mensual</p>
                  <p className="font-semibold">
                    {profile?.monthly_income != null ? currencyFormatter.format(profile.monthly_income) : '-'}
                  </p>
                </div>
                <div className="bg-[var(--nash-surface-2)] rounded-lg p-3">
                  <p className="text-xs text-[var(--nash-text-muted)]">Gasto total mes</p>
                  <p className="font-semibold">{currencyFormatter.format(summary.total || 0)}</p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3 text-sm">
                <div className="bg-[var(--nash-surface-2)] rounded-lg p-3">
                  <p className="text-xs text-[var(--nash-text-muted)]">Gastos fijos</p>
                  <p className="font-semibold">{fixedExpenses.length}</p>
                </div>
                <div className="bg-[var(--nash-surface-2)] rounded-lg p-3">
                  <p className="text-xs text-[var(--nash-text-muted)]">Deudas activas</p>
                  <p className="font-semibold">{debts.length}</p>
                </div>
              </div>

              <div className="text-xs text-[var(--nash-text-muted)] space-y-1">
                <p>
                  Meta ahorro:{' '}
                  <span className="text-[var(--nash-text)] font-medium">
                    {profile?.savings_goal != null ? currencyFormatter.format(profile.savings_goal) : '-'}
                  </span>
                </p>
                <p>
                  Fondo emergencia:{' '}
                  <span className="text-[var(--nash-text)] font-medium">
                    {profile?.emergency_fund_target != null ? currencyFormatter.format(profile.emergency_fund_target) : '-'}
                  </span>
                </p>
              </div>

              <div className="space-y-2">
                <p className="text-sm font-medium">Categorias del mes</p>
                {summary.by_category.length === 0 && (
                  <p className="text-xs text-[var(--nash-text-muted)]">Aun no hay gastos registrados este mes.</p>
                )}
                {summary.by_category.map((item, idx) => (
                  <div key={`${item.code || 'none'}-${idx}`} className="flex items-center justify-between bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg p-3 text-sm">
                    <span>
                      {item.icon || '•'} {item.name_es || 'Sin categoria'}
                    </span>
                    <span className="font-medium">{currencyFormatter.format(item.total || 0)}</span>
                  </div>
                ))}
              </div>
            </section>

            <section className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded-xl p-5 space-y-5">
              <div>
                <h3 className="font-semibold text-[var(--nash-text)]">Registrar gasto</h3>
                <p className="text-xs text-[var(--nash-text-muted)]">
                  Entrada manual rapida para mantener control.
                </p>
              </div>

              <form onSubmit={handleSubmitExpense} className="space-y-2">
                <input
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Descripcion (ej: Uber al trabajo)"
                  className="w-full bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                />
                <div className="grid grid-cols-2 gap-2">
                  <input
                    value={amount}
                    onChange={(e) => setAmount(e.target.value)}
                    placeholder={`Monto (${currency})`}
                    className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                  />
                  <select
                    value={categoryCode}
                    onChange={(e) => setCategoryCode(e.target.value)}
                    className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                  >
                    <option value="">Sin categoria</option>
                    {categories.map((category) => (
                      <option key={category.code} value={category.code}>
                        {category.icon} {category.name_es}
                      </option>
                    ))}
                  </select>
                </div>

                <input
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Notas (opcional)"
                  className="w-full bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg px-3 py-2 text-sm"
                />

                <label className="flex items-center gap-2 text-sm text-[var(--nash-text-muted)]">
                  <input
                    type="checkbox"
                    checked={isRecurring}
                    onChange={(e) => setIsRecurring(e.target.checked)}
                  />
                  Es gasto recurrente
                </label>

                {formError && <p className="text-xs text-[var(--nash-warning)]">{formError}</p>}

                <button
                  type="submit"
                  disabled={savingExpense}
                  className="px-3 py-2 rounded-lg bg-[var(--nash-accent)] text-white text-sm font-medium hover:opacity-90 disabled:opacity-50 cursor-pointer disabled:cursor-not-allowed"
                >
                  {savingExpense ? 'Guardando...' : 'Guardar gasto'}
                </button>
              </form>

              <div className="space-y-2">
                <p className="text-sm font-medium">Movimientos recientes ({expenses.length})</p>
                {expenses.length === 0 && (
                  <p className="text-xs text-[var(--nash-text-muted)]">Aun no hay movimientos registrados.</p>
                )}
                {expenses.map((expense) => (
                  <div key={expense.id} className="bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded-lg p-3">
                    <div className="flex items-center justify-between text-xs text-[var(--nash-text-muted)]">
                      <span>{expense.category_icon || '•'} {expense.category_name || 'Sin categoria'}</span>
                      <span>{formatDateTime(expense.timestamp)}</span>
                    </div>
                    <p className="text-sm mt-1">{expense.description}</p>
                    <p className="text-sm font-semibold mt-1">{currencyFormatter.format(expense.amount)}</p>
                    {expense.notes && (
                      <p className="text-xs text-[var(--nash-text-muted)] mt-1">{expense.notes}</p>
                    )}
                  </div>
                ))}
              </div>
            </section>
          </div>
        )}
      </div>

      {showDiscovery && (
        <ModuleDiscovery
          module="finance"
          title="Descubrimiento de Finanzas"
          subtitle="Configura ingresos, deudas, gastos fijos y metas de ahorro."
          onClose={() => {
            setShowDiscovery(false);
            loadData();
          }}
          onProfileUpdated={loadData}
        />
      )}
    </>
  );
}
