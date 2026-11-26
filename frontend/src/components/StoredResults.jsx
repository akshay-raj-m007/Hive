import { useCallback, useEffect, useState } from 'react'
import { API_URL } from '../lib/analytics.js'
import ResultView from './ResultView.jsx'

const PAGE = 50

function when(iso) {
  return iso ? new Date(iso).toLocaleString() : '—'
}

export default function StoredResults({ adminKey, onUnauthorized }) {
  const [summary, setSummary] = useState(null)
  const [rows, setRows] = useState([])
  const [filter, setFilter] = useState('')
  const [more, setMore] = useState(false)
  const [error, setError] = useState(null)
  const [open, setOpen] = useState(null) // full stored result
  const [showAnswers, setShowAnswers] = useState(false)

  const api = useCallback(
    async (path, opts = {}) => {
      const r = await fetch(`${API_URL}${path}`, { ...opts, headers: { 'X-Admin-Key': adminKey } })
      if (r.status === 401) {
        onUnauthorized()
        throw new Error('unauthorized')
      }
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      return r.json()
    },
    [adminKey, onUnauthorized],
  )

  const load = useCallback(
    async (offset = 0) => {
      try {
        const q = `/api/admin/results?limit=${PAGE}&offset=${offset}${filter ? `&test_id=${filter}` : ''}`
        const [s, list] = await Promise.all([api('/api/admin/results/summary'), api(q)])
        setSummary(s)
        setRows((prev) => (offset ? [...prev, ...list] : list))
        setMore(list.length === PAGE)
        setError(null)
      } catch (e) {
        if (e.message !== 'unauthorized') setError('Could not load stored results.')
      }
    },
    [api, filter],
  )

  useEffect(() => {
    load(0)
  }, [load])

  const openResult = async (id) => {
    try {
      setShowAnswers(false)
      setOpen(await api(`/api/admin/results/${id}`))
      scrollTo({ top: 0 })
    } catch {
      setError('Could not open that result.')
    }
  }

  const remove = async (id) => {
    if (!confirm('Delete this stored result permanently?')) return
    await api(`/api/admin/results/${id}`, { method: 'DELETE' })
    setOpen(null)
    load(0)
  }

  if (open) {
    const r = open.response
    return (
      <div className="stored-detail">
        <div className="stored-meta panel">
          <div>
            <p className="eyebrow">Stored result #{open.id}</p>
            <p className="muted small">
              {when(open.created_at)} · visitor <span className="mono">{open.distinct_id.slice(-12)}</span>
              {open.city || open.country ? ` · ${[open.city, open.country].filter(Boolean).join(', ')}` : ''}
              {open.ai_used ? ' · AI wording used' : ''}
            </p>
          </div>
          <div className="stored-actions">
            <button className="btn ghost" onClick={() => setShowAnswers((s) => !s)}>{showAnswers ? 'Hide' : 'Show'} raw answers</button>
            <button className="btn ghost danger" onClick={() => remove(open.id)}>Delete</button>
          </div>
        </div>
        {showAnswers && (
          <div className="panel">
            <h3>Raw answers</h3>
            <dl className="kv">
              {Object.entries(open.answers).map(([k, v]) => (
                <div key={k} style={{ display: 'contents' }}><dt>{k}</dt><dd>{String(v)}</dd></div>
              ))}
            </dl>
          </div>
        )}
        <ResultView data={r} readOnly onExit={() => setOpen(null)} />
      </div>
    )
  }

  return (
    <>
      {error && <div className="alert">{error}</div>}
      {summary && (
        <>
          <section className="tiles">
            <div className="tile"><span className="tile-value">{summary.total}</span><span className="tile-label">Results stored</span></div>
            <div className="tile"><span className="tile-value">{summary.per_test.length}</span><span className="tile-label">Tests taken</span></div>
            <div className="tile">
              <span className="tile-value small-value">{summary.storage === 'postgresql' ? 'PostgreSQL' : 'SQLite'}</span>
              <span className="tile-label">{summary.storage === 'postgresql' ? 'Permanent storage' : 'Local file (resets on Render)'}</span>
            </div>
          </section>
          <div className="chips filter-chips">
            <button className={`chip ${filter === '' ? 'on' : ''}`} onClick={() => setFilter('')}>All tests <small>{summary.total}</small></button>
            {summary.per_test.map((t) => (
              <button key={t.test_id} className={`chip ${filter === t.test_id ? 'on' : ''}`} onClick={() => setFilter(t.test_id)}>
                {t.title} <small>{t.results}</small>
              </button>
            ))}
          </div>
        </>
      )}
      <section className="panel">
        <h3>Stored results</h3>
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>When</th><th>Test</th><th>Result</th><th>Visitor</th><th>Place</th><th>AI</th></tr>
            </thead>
            <tbody>
              {rows.map((x) => (
                <tr key={x.id} className="clickable" onClick={() => openResult(x.id)}>
                  <td>{when(x.created_at)}</td>
                  <td>{x.test_title}</td>
                  <td className="wrap">{x.headline}</td>
                  <td className="mono">{x.distinct_id.slice(-8)}</td>
                  <td>{[x.city, x.country].filter(Boolean).join(', ') || '—'}</td>
                  <td>{x.ai_used ? 'yes' : '—'}</td>
                </tr>
              ))}
              {!rows.length && <tr><td colSpan={6} className="muted">No results stored yet.</td></tr>}
            </tbody>
          </table>
        </div>
        {more && <button className="btn ghost" onClick={() => load(rows.length)}>Load more</button>}
      </section>
    </>
  )
}
