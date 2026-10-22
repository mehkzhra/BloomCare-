import { t } from './i18n.js';
import { ResourceStatus, useResource } from './resources.jsx';

const validEvidence = data => Array.isArray(data?.candidates) && data?.pe && Array.isArray(data.limitations);
export function TrainingEvidencePanel() {
  const evidence = useResource('/admin/training-evidence', { validate: validEvidence });
  return <div className="stack"><ResourceStatus resource={evidence} />{evidence.data && <>
    <h3>{t('Retraining comparison')}</h3>
    <p className="muted text-sm">{t('Candidates were selected using grouped cross-validation on the training partition. The comparison test is the historical, already published holdout.')}</p>
    <div className="table-scroll"><table className="workspace-table"><thead><tr><th>{t('Candidate')}</th><th>{t('Configurations')}</th><th>{t('Comparison accuracy')}</th><th>{t('Medium recall')}</th><th>{t('Decision')}</th></tr></thead><tbody>{evidence.data.candidates.map(row => <tr key={row.family}><td>{({ random_forest: 'Random Forest', extra_trees: 'Extra Trees', gradient_boosting: 'Gradient Boosting' })[row.family]}</td><td>{row.configurations}</td><td>{(row.accuracy * 100).toFixed(1)}%</td><td>{(row.medium_recall * 100).toFixed(1)}%</td><td>{t(row.gate.active_model_changed ? 'Registered' : 'Not promoted')}</td></tr>)}</tbody></table></div>
    <p className="banner">{t('The tested candidates did not meet all improvement checks. The existing model was retained to avoid a measured regression.')}</p>
    <h3>{t('Legacy PE retraining')}</h3>
    <p className="muted text-sm">{evidence.data.pe.usable_rows} {t('unique rows')} · {evidence.data.pe.exact_duplicates_removed} {t('exact duplicates removed')} · {(evidence.data.pe.test_accuracy * 100).toFixed(1)}% {t('grouped comparison accuracy')}</p>
    <p className="scope-note">{t('The PE source has no systolic readings above 130 mmHg. Its confirmed-outcome definition and HB units are not documented. Retraining cannot fill those data gaps.')}</p>
    <details className="explanation"><summary>{t('Method and limitations')}</summary><ul className="limitations">{evidence.data.limitations.map(line => <li key={line}>{line}</li>)}</ul><code>scripts\retrain-models.cmd</code></details>
  </>}</div>;
}
