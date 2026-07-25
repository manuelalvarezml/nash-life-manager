import { useState, useEffect } from 'react';
import { fetchSelfProfile, updateSelfProfile } from '../../api';
import type { SelfProfile } from '../../api';

const SECTION_LABELS: Record<string, string> = {
  identity: 'Identidad',
  current: 'Situacion Actual',
  family: 'Familia y Origenes',
  education: 'Educacion',
  career: 'Carrera',
  relationships: 'Relaciones',
  health: 'Salud',
  values: 'Valores e Identidad',
  life_story: 'Historia de Vida',
  preferences: 'Preferencias',
  financial: 'Finanzas',
};

const FIELD_LABELS: Record<string, string> = {
  // Identity
  birth_date: 'Fecha de nacimiento',
  birth_place: 'Lugar de nacimiento',
  gender: 'Genero',
  nationality: 'Nacionalidad',
  ethnicities: 'Etnias',
  preferred_name: 'Nombre preferido',
  pronouns: 'Pronombres',
  // Current
  current_city: 'Ciudad actual',
  current_country: 'Pais actual',
  living_situation: 'Situacion de vivienda',
  years_at_location: 'Anos en ubicacion actual',
  timezone: 'Zona horaria',
  // Family
  mother_alive: 'Madre viva',
  mother_age: 'Edad de madre',
  mother_occupation: 'Ocupacion de madre',
  mother_relationship: 'Relacion con madre',
  father_alive: 'Padre vivo',
  father_age: 'Edad de padre',
  father_occupation: 'Ocupacion de padre',
  father_relationship: 'Relacion con padre',
  parents_status: 'Estado de padres',
  childhood_structure: 'Estructura familiar infancia',
  childhood_socioeconomic: 'Nivel socioeconomico infancia',
  childhood_location: 'Ubicacion infancia',
  num_siblings: 'Numero de hermanos',
  birth_order: 'Orden de nacimiento',
  // Education
  highest_education: 'Nivel de educacion mas alto',
  field_of_study: 'Campo de estudio',
  // Career
  current_occupation: 'Ocupacion actual',
  current_industry: 'Industria actual',
  years_in_role: 'Anos en rol actual',
  career_satisfaction: 'Satisfaccion laboral (1-10)',
  // Relationships
  relationship_status: 'Estado de relacion',
  partner_name: 'Nombre de pareja',
  relationship_years: 'Anos de relacion',
  relationship_satisfaction: 'Satisfaccion en relacion (1-10)',
  has_children: 'Tiene hijos',
  num_children: 'Numero de hijos',
  num_past_relationships: 'Relaciones pasadas significativas',
  longest_relationship_years: 'Relacion mas larga (anos)',
  age_first_relationship: 'Edad primera relacion',
  relationship_patterns_reflection: 'Reflexion sobre patrones',
  // Health
  height_cm: 'Altura (cm)',
  weight_kg: 'Peso (kg)',
  in_therapy: 'En terapia actualmente',
  attachment_style: 'Estilo de apego',
  // Values
  core_values_json: 'Valores fundamentales',
  religious_spiritual: 'Religion/Espiritualidad',
  religious_practice: 'Nivel de practica',
  native_language: 'Idioma nativo',
  languages_json: 'Otros idiomas',
  mbti: 'MBTI',
  // Life Story
  life_theme: 'Tema central de vida',
  // Preferences
  communication_style: 'Estilo de comunicacion',
  // Financial
  income_bracket: 'Rango de ingresos',
  owns_home: 'Propietario de vivienda',
  financial_stress: 'Estres financiero (1-10)',
};

const FIELD_TYPES: Record<string, 'text' | 'number' | 'select' | 'textarea' | 'boolean'> = {
  birth_date: 'text',
  mother_alive: 'boolean',
  father_alive: 'boolean',
  has_children: 'boolean',
  in_therapy: 'boolean',
  owns_home: 'boolean',
  num_siblings: 'number',
  num_children: 'number',
  years_at_location: 'number',
  years_in_role: 'number',
  relationship_years: 'number',
  num_past_relationships: 'number',
  longest_relationship_years: 'number',
  age_first_relationship: 'number',
  height_cm: 'number',
  weight_kg: 'number',
  career_satisfaction: 'number',
  relationship_satisfaction: 'number',
  financial_stress: 'number',
  mother_age: 'number',
  father_age: 'number',
  relationship_patterns_reflection: 'textarea',
  life_theme: 'textarea',
};

const SELECT_OPTIONS: Record<string, string[]> = {
  gender: ['masculino', 'femenino', 'no binario', 'otro', 'prefiero no decir'],
  living_situation: ['solo', 'con pareja', 'con familia', 'con roommates', 'otro'],
  mother_relationship: ['cercana', 'distante', 'complicada', 'sin contacto', 'fallecida'],
  father_relationship: ['cercana', 'distante', 'complicada', 'sin contacto', 'fallecido'],
  parents_status: ['casados', 'divorciados', 'separados', 'viudo/a', 'nunca casados'],
  childhood_structure: ['nuclear', 'monoparental', 'extendida', 'reconstituida', 'otro'],
  childhood_socioeconomic: ['bajo', 'medio-bajo', 'medio', 'medio-alto', 'alto'],
  birth_order: ['unico', 'mayor', 'del medio', 'menor'],
  highest_education: ['primaria', 'secundaria', 'preparatoria', 'licenciatura', 'maestria', 'doctorado', 'otro'],
  relationship_status: ['soltero', 'en relacion', 'casado', 'divorciado', 'viudo', 'es complicado'],
  attachment_style: ['seguro', 'ansioso', 'evitativo', 'desorganizado', 'no se'],
  religious_practice: ['no practicante', 'ocasional', 'regular', 'devoto'],
  communication_style: ['directo', 'gentil', 'analitico', 'emocional', 'mixto'],
  income_bracket: ['bajo', 'medio-bajo', 'medio', 'medio-alto', 'alto', 'prefiero no decir'],
};

interface SectionCardProps {
  section: string;
  completeness: number;
  isExpanded: boolean;
  onToggle: () => void;
  profile: SelfProfile;
  onFieldChange: (field: string, value: string | number | null) => void;
  fields: string[];
}

function SectionCard({
  section,
  completeness,
  isExpanded,
  onToggle,
  profile,
  onFieldChange,
  fields,
}: SectionCardProps) {
  const completenessPercent = Math.round(completeness * 100);

  return (
    <div className="bg-[var(--nash-surface)] border border-[var(--nash-border)] rounded-lg overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-[var(--nash-surface-2)] transition-colors cursor-pointer"
      >
        <div className="flex items-center gap-3">
          <span className="text-sm font-medium text-[var(--nash-text)]">
            {SECTION_LABELS[section] || section}
          </span>
        </div>
        <div className="flex items-center gap-3">
          <div className="w-20 h-2 bg-[var(--nash-surface-2)] rounded-full overflow-hidden">
            <div
              className="h-full bg-[var(--nash-accent)] transition-all duration-300"
              style={{ width: `${completenessPercent}%` }}
            />
          </div>
          <span className="text-xs text-[var(--nash-text-muted)] w-10 text-right">
            {completenessPercent}%
          </span>
          <span className="text-[var(--nash-text-muted)]">
            {isExpanded ? '-' : '+'}
          </span>
        </div>
      </button>

      {isExpanded && (
        <div className="px-4 py-4 border-t border-[var(--nash-border)] space-y-4">
          {fields.map((field) => {
            const label = FIELD_LABELS[field] || field;
            const fieldType = FIELD_TYPES[field] || 'text';
            const value = profile[field as keyof SelfProfile];
            const options = SELECT_OPTIONS[field];

            // Skip JSON fields for now (complex editing)
            if (field.endsWith('_json')) {
              return null;
            }

            return (
              <div key={field} className="space-y-1">
                <label className="text-xs text-[var(--nash-text-muted)] block">
                  {label}
                </label>

                {fieldType === 'boolean' ? (
                  <select
                    value={value === 1 ? 'si' : value === 0 ? 'no' : ''}
                    onChange={(e) => {
                      const v = e.target.value;
                      onFieldChange(field, v === 'si' ? 1 : v === 'no' ? 0 : null);
                    }}
                    className="w-full bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded px-3 py-2 text-sm text-[var(--nash-text)]"
                  >
                    <option value="">-</option>
                    <option value="si">Si</option>
                    <option value="no">No</option>
                  </select>
                ) : options ? (
                  <select
                    value={(value as string) || ''}
                    onChange={(e) => onFieldChange(field, e.target.value || null)}
                    className="w-full bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded px-3 py-2 text-sm text-[var(--nash-text)]"
                  >
                    <option value="">-</option>
                    {options.map((opt) => (
                      <option key={opt} value={opt}>
                        {opt}
                      </option>
                    ))}
                  </select>
                ) : fieldType === 'textarea' ? (
                  <textarea
                    value={(value as string) || ''}
                    onChange={(e) => onFieldChange(field, e.target.value || null)}
                    rows={3}
                    className="w-full bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded px-3 py-2 text-sm text-[var(--nash-text)] resize-none"
                    placeholder={`Escribe tu ${label.toLowerCase()}...`}
                  />
                ) : fieldType === 'number' ? (
                  <input
                    type="number"
                    value={value !== null && value !== undefined ? String(value) : ''}
                    onChange={(e) => {
                      const v = e.target.value;
                      onFieldChange(field, v ? Number(v) : null);
                    }}
                    className="w-full bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded px-3 py-2 text-sm text-[var(--nash-text)]"
                  />
                ) : (
                  <input
                    type="text"
                    value={(value as string) || ''}
                    onChange={(e) => onFieldChange(field, e.target.value || null)}
                    className="w-full bg-[var(--nash-bg)] border border-[var(--nash-border)] rounded px-3 py-2 text-sm text-[var(--nash-text)]"
                    placeholder={field === 'birth_date' ? 'YYYY-MM-DD' : ''}
                  />
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export function SobreMi() {
  const [profile, setProfile] = useState<SelfProfile | null>(null);
  const [sections, setSections] = useState<Record<string, string[]>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [expandedSection, setExpandedSection] = useState<string | null>(null);
  const [pendingChanges, setPendingChanges] = useState<Partial<SelfProfile>>({});

  const loadProfile = async () => {
    setLoading(true);
    try {
      const data = await fetchSelfProfile();
      setProfile(data.profile || {});

      // Fetch sections
      const res = await fetch('/api/profile/self/sections');
      const sectionsData = await res.json();
      setSections(sectionsData.sections || {});
    } catch (e) {
      console.error('Error loading profile:', e);
    }
    setLoading(false);
  };

  useEffect(() => {
    loadProfile();
  }, []);

  const handleFieldChange = (field: string, value: string | number | null) => {
    setProfile((prev) => (prev ? { ...prev, [field]: value } : { [field]: value }));
    setPendingChanges((prev) => ({ ...prev, [field]: value }));
  };

  const saveChanges = async () => {
    if (Object.keys(pendingChanges).length === 0) return;

    setSaving(true);
    try {
      const result = await updateSelfProfile(pendingChanges);
      setProfile(result.profile);
      setPendingChanges({});
    } catch (e) {
      console.error('Error saving profile:', e);
    }
    setSaving(false);
  };

  const overallCompleteness = profile?.completeness_score ?? 0;
  const sectionCompleteness = profile?.section_completeness ?? {};
  const hasPendingChanges = Object.keys(pendingChanges).length > 0;

  return (
    <div className="max-w-3xl mx-auto px-4 py-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">Sobre Mi</h2>
          <p className="text-sm text-[var(--nash-text-muted)] mt-1">
            Datos biograficos que Nash usa como contexto para darte mejor consejo.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-right">
            <p className="text-2xl font-bold text-[var(--nash-accent)]">
              {Math.round(overallCompleteness * 100)}%
            </p>
            <p className="text-xs text-[var(--nash-text-muted)]">completo</p>
          </div>
          {hasPendingChanges && (
            <button
              onClick={saveChanges}
              disabled={saving}
              className="px-4 py-2 bg-[var(--nash-accent)] text-white rounded-lg text-sm font-medium hover:bg-[var(--nash-accent)]/90 disabled:opacity-50 cursor-pointer"
            >
              {saving ? 'Guardando...' : 'Guardar'}
            </button>
          )}
        </div>
      </div>

      {/* Progress bar */}
      <div className="h-2 bg-[var(--nash-surface-2)] rounded-full overflow-hidden">
        <div
          className="h-full bg-[var(--nash-accent)] transition-all duration-500"
          style={{ width: `${overallCompleteness * 100}%` }}
        />
      </div>

      {/* Info box */}
      <div className="bg-[var(--nash-surface-2)] border border-[var(--nash-border)] rounded-xl p-4 text-sm text-[var(--nash-text-muted)]">
        <p className="text-[var(--nash-text)] font-medium text-xs uppercase tracking-wide mb-2">
          Por que llenar esto?
        </p>
        <p className="leading-relaxed">
          Esta informacion le da a Nash contexto estable sobre ti — cosas que no cambian frecuentemente.
          Mientras mas llenes, mejor puede personalizar sus preguntas y consejos. Todo se guarda localmente.
        </p>
      </div>

      {loading && <p className="text-sm text-[var(--nash-text-muted)]">Cargando...</p>}

      {/* Section cards */}
      {!loading && profile && (
        <div className="space-y-3">
          {Object.keys(sections).map((section) => (
            <SectionCard
              key={section}
              section={section}
              completeness={sectionCompleteness[section] ?? 0}
              isExpanded={expandedSection === section}
              onToggle={() => setExpandedSection(expandedSection === section ? null : section)}
              profile={profile}
              onFieldChange={handleFieldChange}
              fields={sections[section] || []}
            />
          ))}
        </div>
      )}
    </div>
  );
}
