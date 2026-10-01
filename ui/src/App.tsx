import { useState } from 'react'
import type { FormEvent } from 'react'
import { useQuery } from '@tanstack/react-query'
import './App.css'
import { ProcessFlow } from './ProcessFlow'

type View = 'runs' | 'flow' | 'artifacts'
type Attempt = { attempt_no: number; status: string; error_type?: string | null; error?: string | null; retry_class?: string | null; lease_owner?: string | null; heartbeat_at?: number | null; started_at?: number | null; updated_at?: number | null }
type Run = { job_id: string; design_id: string; ip_family: string; flow_name: string; status: string; parse_status: string; check_status: string; completeness: string; semantic_status: string; provenance_status: string; trust_status: string; artifact_path?: string | null; error?: string | null; updated_at?: number | null; metrics?: Record<string, unknown> | null; attempts: Attempt[] }
type PublicRun = { run_id: string; design: { id: string; ip_family: string }; flow: { name: string }; status: { execution: string; parse: string; check: string; completeness: string; semantic: string; provenance: string; trust: string }; updated_at?: number | null; artifact: { available: boolean }; error?: string | null; attempts?: Attempt[] }

const API_BASE = import.meta.env.VITE_EDA_API_BASE ?? '/api'
const labels: Record<string, string> = {
  QUEUED: '대기 중', RUNNING: '실행 중', SUCCEEDED: '완료', FAILED: '실패', CANCELLED: '취소됨', RETRYABLE_FAILURE: '재시도 가능 실패', ABANDONED: '중단됨', OK: '정상', VALID: '유효', INVALID: '무효', UNKNOWN: '확인 필요', NOT_STARTED: '시작 전', TRUSTED: '신뢰 가능', PASS: '통과', complete: '완전', unknown: '알 수 없음', not_applicable: '해당 없음', not_classified: '분류 전', retryable: '재시도 가능', non_retryable: '재시도하지 않음',
}

async function getRuns(): Promise<PublicRun[]> {
  const response = await fetch(`${API_BASE}/runs?limit=20`)
  if (!response.ok) throw new Error(`목록 조회 요청이 실패했습니다. (${response.status})`)
  const payload = await response.json() as { items: PublicRun[] }
  return payload.items
}

async function getRun(jobId: string): Promise<Run> {
  const response = await fetch(`${API_BASE}/runs/${encodeURIComponent(jobId)}`)
  if (!response.ok) { const body = await response.json().catch(() => ({})) as { error?: string }; throw new Error(body.error ?? `조회 요청이 실패했습니다. (${response.status})`) }
  const payload = await response.json() as PublicRun
  return {
    job_id: payload.run_id, design_id: payload.design.id, ip_family: payload.design.ip_family,
    flow_name: payload.flow.name, status: payload.status.execution, parse_status: payload.status.parse,
    check_status: payload.status.check, completeness: payload.status.completeness,
    semantic_status: payload.status.semantic, provenance_status: payload.status.provenance,
    trust_status: payload.status.trust, updated_at: payload.updated_at,
    artifact_path: payload.artifact.available ? '등록됨' : null, error: payload.error,
    attempts: payload.attempts ?? [],
  }
}
const text = (value?: string | null) => value ? (labels[value] ?? value) : '기록 없음'
const timestamp = (value?: number | null) => value ? new Date(value * 1000).toLocaleString('ko-KR') : '기록 없음'

function Status({ value }: { value?: string | null }) {
  const tone = value === 'SUCCEEDED' || value === 'OK' || value === 'VALID' || value === 'TRUSTED' || value === 'PASS' ? 'good' : value === 'FAILED' || value === 'INVALID' || value === 'CANCELLED' ? 'bad' : 'neutral'
  return <span className={`status ${tone}`}>{text(value)}</span>
}
function Summary({ title, value }: { title: string; value?: string | null }) { return <div className="summary"><span>{title}</span><strong><Status value={value} /></strong></div> }

function App() {
  const [input, setInput] = useState('')
  const [jobId, setJobId] = useState('')
  const [view, setView] = useState<View>('runs')
  const query = useQuery({
    queryKey: ['run', jobId], queryFn: () => getRun(jobId), enabled: Boolean(jobId),
    refetchInterval: jobId ? 3_000 : false, refetchIntervalInBackground: true,
    refetchOnWindowFocus: false,
  })
  const listQuery = useQuery({
    queryKey: ['runs'], queryFn: getRuns, refetchInterval: 3_000,
    refetchIntervalInBackground: true, refetchOnWindowFocus: false,
  })
  const submit = (event: FormEvent) => { event.preventDefault(); setJobId(input.trim()); setView('runs') }
  const selectRun = (runId: string) => { setInput(runId); setJobId(runId); setView('runs') }
  const run = query.data

  return <div className="app-shell">
    <header><div className="brand">EDA <span>분석 운영</span></div><div className="connection"><i />{jobId ? (query.isFetching ? '최신 상태 확인 중' : '자동 갱신 켜짐') : '실행을 선택하세요'}</div></header>
    <div className="workspace">
      <aside className="sidebar" aria-label="운영 메뉴">
        <p className="nav-heading">분석 운영</p>
        <NavButton active={view === 'runs'} onClick={() => setView('runs')} title="실행 현황" description="상태와 결과 확인" />
        <NavButton active={view === 'flow'} onClick={() => setView('flow')} title="처리 과정" description="실행 시도 확인" />
        <NavButton active={view === 'artifacts'} onClick={() => setView('artifacts')} title="결과 파일" description="보고서 등록 여부" />
      </aside>
      <main>
        <Lookup input={input} setInput={setInput} submit={submit} />
        {view === 'runs' && <RunsView jobId={jobId} query={query} run={run} listQuery={listQuery} onSelect={selectRun} />}
        {view === 'flow' && <FlowView jobId={jobId} run={run} />}
        {view === 'artifacts' && <ArtifactsView jobId={jobId} run={run} />}
      </main>
    </div>
  </div>
}

function NavButton({ active, onClick, title, description }: { active: boolean; onClick: () => void; title: string; description: string }) { return <button type="button" className={`nav-button ${active ? 'active' : ''}`} onClick={onClick}><strong>{title}</strong><small>{description}</small></button> }
function Lookup({ input, setInput, submit }: { input: string; setInput: (value: string) => void; submit: (event: FormEvent) => void }) { return <section className="card lookup"><form onSubmit={submit}><label htmlFor="job-id">실행 번호</label><input id="job-id" value={input} onChange={(event) => setInput(event.target.value)} placeholder="예: sta-run-001" /><button type="submit">조회</button></form><p>선택한 실행의 상태를 자동으로 갱신합니다. 화면은 갱신 중에도 현재 내용을 유지합니다.</p></section> }
function Empty({ title, children }: { title: string; children: React.ReactNode }) { return <section className="empty card"><h2>{title}</h2><p>{children}</p></section> }
function RunsView({ jobId, query, run, listQuery, onSelect }: { jobId: string; query: ReturnType<typeof useQuery<Run, Error>>; run?: Run; listQuery: ReturnType<typeof useQuery<PublicRun[], Error>>; onSelect: (runId: string) => void }) {
  const list = <RunList query={listQuery} selectedRunId={jobId} onSelect={onSelect} />
  if (!jobId) return <><PageTitle eyebrow="분석 운영" title="실행 현황" description="저장된 실행 목록에서 선택하거나 실행 번호를 직접 입력해 상세를 조회합니다." />{list}<Empty title="조회할 실행을 선택하세요">목록 항목을 선택하면 실행 상세를 확인할 수 있습니다.</Empty></>
  if (query.isLoading) return <><PageTitle eyebrow="선택한 실행" title="실행 현황" description="실행 상태와 결과 확인을 분리해 봅니다." />{list}<p className="refreshing" aria-live="polite">실행 정보를 불러오는 중입니다.</p></>
  if (query.isError) return <section className="error card"><h2>실행 결과를 불러오지 못했습니다</h2><p>{query.error.message}</p><p className="hint">분석 서비스가 실행 중인지, 실행 번호가 정확한지 확인하세요.</p></section>
  return run ? <><PageTitle eyebrow="선택한 실행" title="실행 현황" description="실행 상태와 결과 확인을 나누어 봅니다." />{list}<RunDetail run={run} refreshing={query.isFetching} /></> : null
}
function RunList({ query, selectedRunId, onSelect }: { query: ReturnType<typeof useQuery<PublicRun[], Error>>; selectedRunId: string; onSelect: (runId: string) => void }) {
  if (query.isLoading) return <p className="refreshing">실행 목록을 불러오는 중입니다.</p>
  if (query.isError) return <section className="card list-error">실행 목록을 불러오지 못했습니다: {query.error.message}</section>
  if (!query.data?.length) return <section className="card list-empty">저장된 실행이 없습니다.</section>
  return <section className="card run-list" aria-label="최근 실행 목록"><div className="list-title"><h2>최근 실행</h2><small aria-live="polite">{query.isFetching ? '갱신 중' : '자동 갱신'}</small></div>{query.data.map((item) => <button key={item.run_id} type="button" className={item.run_id === selectedRunId ? 'selected' : ''} onClick={() => onSelect(item.run_id)} aria-current={item.run_id === selectedRunId ? 'true' : undefined}><div><strong>{item.run_id}</strong><span>{item.design.id} · {item.flow.name}</span></div><Status value={item.status.execution} /></button>)}</section>
}

function FlowView({ jobId, run }: { jobId: string; run?: Run }) { return <><PageTitle eyebrow="운영 화면" title="처리 과정" description="저장된 분석 요청과 실행 시도를 연결해 보여 줍니다." />{!jobId || !run ? <Empty title="실행을 먼저 조회하세요">처리 과정은 선택한 실행의 기록을 바탕으로 보여 줍니다.</Empty> : <section className="card flow-card"><ProcessFlow attempts={run.attempts} runStatus={run.status} statusLabel={text} /><p className="hint">저장된 요청·실행 시도·현재 결과만 표시합니다. 도구 내부 단계나 처리 기록은 임의로 추가하지 않습니다.</p></section>}</> }
function ArtifactsView({ jobId, run }: { jobId: string; run?: Run }) { return <><PageTitle eyebrow="운영 화면" title="결과 파일" description="선택한 실행의 결과 파일 등록 여부를 확인합니다." />{!jobId || !run ? <Empty title="실행을 먼저 조회하세요">결과 파일은 선택한 실행의 결과를 바탕으로 보여 줍니다.</Empty> : <section className="card artifact-card"><h2>실행 {run.job_id}</h2>{run.artifact_path ? <><div className="artifact-row"><span>보고서</span><div><strong>결과 파일이 등록되었습니다</strong><p className="path">보안상 파일 위치는 이 화면에 표시하지 않습니다.</p></div></div><p className="hint">현재는 파일 등록 여부만 확인할 수 있습니다. 내려받기는 권한 확인 기능이 추가된 뒤 제공할 수 있습니다.</p></> : <p className="empty-line">등록된 결과 파일이 없습니다.</p>}</section>}</> }
function PageTitle({ eyebrow, title, description }: { eyebrow: string; title: string; description: string }) { return <div className="page-title"><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p className="intro">{description}</p></div> }
function RunDetail({ run, refreshing }: { run: Run; refreshing: boolean }) { return <><section className="card run-title"><div><div className="eyebrow">선택한 실행 {refreshing && <span className="quiet-refresh">최신 상태 확인 중</span>}</div><h2>{run.job_id}</h2><p>{run.design_id} · {run.ip_family} · {run.flow_name}</p></div><Status value={run.status} /></section><section className="summary-grid"><Summary title="실행 상태" value={run.status} /><Summary title="보고서 읽기" value={run.parse_status} /><Summary title="결과 검사" value={run.check_status} /><Summary title="결과 신뢰도" value={run.trust_status} /></section><section className="content-grid"><section className="card"><div className="section-heading"><div><h2>실행 시도</h2><p>저장된 실행 시도와 실패 원인을 확인합니다.</p></div><small>마지막 변경: {timestamp(run.updated_at)}</small></div>{run.attempts.length === 0 ? <p className="empty-line">저장된 실행 시도가 없습니다.</p> : <ol className="attempts">{run.attempts.map((attempt) => <li key={attempt.attempt_no}><div className="attempt-head"><strong>{attempt.attempt_no}번째 실행</strong><Status value={attempt.status} /></div><dl><div><dt>시작 시각</dt><dd>{timestamp(attempt.started_at)}</dd></div><div><dt>마지막 갱신</dt><dd>{timestamp(attempt.updated_at)}</dd></div><div><dt>재시도 가능 여부</dt><dd>{text(attempt.retry_class)}</dd></div></dl>{attempt.error && <p className="attempt-error"><strong>{text(attempt.error_type)}:</strong> {attempt.error}</p>}</li>)}</ol>}</section><aside className="side-stack"><section className="card"><h2>결과 확인</h2><dl className="facts"><div><dt>내용이 모두 있는지</dt><dd>{text(run.completeness)}</dd></div><div><dt>결과 의미가 맞는지</dt><dd>{text(run.semantic_status)}</dd></div><div><dt>결과 출처를 확인했는지</dt><dd>{text(run.provenance_status)}</dd></div></dl></section>{run.error && <section className="card warning"><h2>실행 오류</h2><p>{run.error}</p></section>}</aside></section></> }
export default App
